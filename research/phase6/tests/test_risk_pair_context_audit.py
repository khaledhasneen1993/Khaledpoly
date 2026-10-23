import copy
import json
import unittest
from research.phase6.risk_pair_context_audit import DIAGNOSTIC, ROOT, analyze, load_context, summarize_routes
from research.phase6.route_coverage_audit import validate_selection


class RiskPairContextTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = load_context()
        cls.orders = json.loads(DIAGNOSTIC.read_text())
        cls.proof, cls.selection = analyze(cls.context, cls.orders)

    def test_original_books_and_actual_activation(self):
        p = self.proof
        self.assertEqual(p['sourceClockSkewMs'], 0)
        self.assertEqual(list(p['sourceAgeAtSubmitMs'].values()), [85, 85])
        self.assertEqual([v['seq'] for v in p['booksAtSubmit'].values()], [173337, 173339])
        self.assertTrue(all(v['originalEventType'] == 'book' for v in p['booksAtSubmit'].values()))
        self.assertEqual(p['activeMs'], 254)
        self.assertEqual([g['seq'] for g in p['terminalGaps']], [173753, 173753])
        self.assertTrue(all(r['arrivalMs']-p['terminalMs'] == 4 for r in p['firstFullSnapshotAfterCancel']))
        self.assertFalse(p['fillsInferred'])

    def test_only_post_observed_activation_selected(self):
        self.assertEqual(self.selection, json.loads((ROOT/'selection.json').read_text()))
        self.assertEqual([x['normalizedSeq'] for x in self.selection['transactions']], [173610, 173728])
        trades = self.proof['publicTradesDuringArrivalActiveInterval']
        self.assertEqual([t['classification'] for t in trades], ['SOURCE_BEFORE_OBSERVED_ACTIVATION']*2+['RECEIPT_REQUIRED']*2)
        # The second rejected observation equals activationDueMs, not activatedMs.
        self.assertEqual(int(trades[1]['sample']['timestamp']), self.orders['makerExecutionDiagnostics'][0]['activationDueMs'])
        changed = copy.deepcopy(self.selection)
        changed['transactions'][0]['sample']['timestamp'] = str(self.orders['makerExecutionDiagnostics'][0]['activationDueMs'])
        with self.assertRaisesRegex(ValueError, 'lifecycle'):
            validate_selection(changed, set(self.proof['booksAtSubmit']))

    def test_raw_and_normalized_tampering_rejected(self):
        changed = copy.deepcopy(self.context)
        changed['frames'][0]['raw']['data']['text'] += ' '
        with self.assertRaisesRegex(ValueError, 'hash/binding'):
            analyze(changed, self.orders)
        changed = copy.deepcopy(self.context)
        frame = next(x for x in changed['frames'] if x['normalized']['seq'] == 173337)
        frame['normalized']['data']['events'][0]['data']['bids'][0]['size'] = '999'
        with self.assertRaisesRegex(ValueError, 'projection mismatch'):
            analyze(changed, self.orders)

    def test_component_prices_not_one_minus_public_price(self):
        rows = []
        for item in self.selection['transactions']:
            order = item['targetOrder']
            # Mixed MINT component prices straddle each own bid. Public weighted
            # price must not erase the small compatible component or credit all.
            parts = [dict(makerToken=order['token'], makerSide='BUY', collateralRaw=100000,
                          sharesRaw=1000000, makerPrice='.1', route='MINT'),
                     dict(makerToken=order['token'], makerSide='BUY', collateralRaw=900000,
                          sharesRaw=1000000, makerPrice='.9', route='MINT')]
            group = dict(components=parts, routeSharesRaw={'MINT':2000000})
            rows.append(dict(sample=item['sample'], routeConservation=dict(uniqueConservedGroup=True, matchingGroups=[group])))
        report = dict(complete=True, requested=2, results=rows)
        result = summarize_routes(report, self.selection)
        self.assertEqual([r['targetBuyAtOrBelowOwnBidSharesRaw'] for r in result['results']], [1000000, 1000000])
        self.assertEqual(result['fillsCreated'], 0)
        self.assertFalse(result['netPnlRecomputed'])
        bad = copy.deepcopy(report); bad['results'][1] = bad['results'][0]
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            summarize_routes(bad, self.selection)
        report['complete'] = False
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            summarize_routes(report, self.selection)


if __name__ == '__main__':
    unittest.main()
