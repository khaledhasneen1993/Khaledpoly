import io
import json
import unittest
from research.phase6.opportunity_census import census, validate_reference


class OpportunityCensusTest(unittest.TestCase):
    def run_tape(self, gap=False, complete=True, before_trade=()):
        events = [('RESEARCH_META', {'condition': 'm', 'first': 'a', 'second': 'b', 'tick': '.01',
                                    'minSize': '1', 'accepting': True, 'startMs': 0, 'endMs': 900000, 'observedMs': 0})]
        for token, bid in (('a', '.4'), ('b', '.55')):
            events.append(('RESEARCH_BOOK', {'token': token, 'sourceMs': 0, 'bids': [{'price': bid, 'size': '100'}],
                                             'asks': [{'price': '.8', 'size': '100'}]}))
        if gap: events.append(('RESEARCH_GAP', {'token': 'a', 'reason': 'test'}))
        events.extend(before_trade)
        events.append(('RESEARCH_TRADE', {'token': 'a', 'sourceMs': 10, 'side': 'SELL', 'price': '.4', 'size': '1000'}))
        if complete: events.append(('RUN_END', {'complete': True}))
        rows = [dict(schema=1, seq=i+1, runId='r', arrivalMs=10 if kind in ('RESEARCH_TRADE','RUN_END') else 0,
                     kind=kind, data=data) for i,(kind,data) in enumerate(events)]
        stream = io.BytesIO(b''.join((json.dumps(row)+'\n').encode() for row in rows))
        return census(stream, dict(maxBookAgeMs=2000, metadataMaxAgeMs=60000, orderShares='5', mergeCost='.01', minimumEdge='.01'))

    def test_quote_alignment_is_necessary_not_a_fill_or_profit(self):
        result = self.run_tape()
        self.assertEqual(result['policyCounts']['0'], {'NECESSARY_CONDITIONS_ONLY': 1})
        self.assertEqual(result['policyCounts']['1'], {'QUOTE_NOT_AT_PRINT': 1})
        self.assertFalse(result['fillsInferred']); self.assertFalse(result['pnlInferred'])
        self.assertEqual(result['decision'], 'NO_GO')

    def test_gap_blocks_census_and_missing_end_fails(self):
        self.assertEqual(self.run_tape(gap=True)['policyCounts']['0'], {'DEPTH_UNAVAILABLE': 1})
        with self.assertRaises(ValueError): self.run_tape(complete=False)

    def test_official_resolution_field_and_temporary_market_unavailability(self):
        for event in (('RESEARCH_RESOLUTION', {'condition_id': 'm'}),
                      ('RESEARCH_MARKET_UNAVAILABLE', {'condition': 'm'})):
            result = self.run_tape(before_trade=[event])
            self.assertEqual(result['policyCounts']['0'], {'NO_FRESH_ACTIVE_BINARY_MARKET': 1})

    def test_recorded_tick_changes_update_the_quote_grid(self):
        result = self.run_tape(before_trade=[('RESEARCH_TICK_SIZE', {'token': 'a', 'tick': '.03', 'sourceMs': 0})])
        self.assertEqual(result['policyCounts']['0'], {'QUOTE_NOT_AT_PRINT': 1})

    def test_complement_buy_is_only_a_candidate_and_duplicate_routes_are_flagged(self):
        buy = ('RESEARCH_TRADE', {'token': 'b', 'sourceMs': 10, 'side': 'BUY', 'price': '.6', 'size': '1000'})
        result = self.run_tape(before_trade=[buy])
        self.assertEqual(result['complementBuyCandidateCounts']['0'], {'NECESSARY_CONDITIONS_ONLY': 1})
        self.assertEqual(result['routeFingerprintOverlaps']['0'], 1)
        self.assertTrue(result['complementPrintIsNotProofOfMint'])
        self.assertFalse(result['fillsInferred'])
        result = self.run_tape(gap=True, before_trade=[buy])
        self.assertEqual(result['complementBuyCandidateCounts']['0'], {'DEPTH_UNAVAILABLE': 1})

    def test_reference_rejects_different_source_or_changed_direct_counts(self):
        result = self.run_tape()
        validate_reference(result,result['logicalTapeSha256'],1,0)
        with self.assertRaises(ValueError): validate_reference(result,'0'*64,1,0)
        with self.assertRaises(ValueError): validate_reference(result,result['logicalTapeSha256'],2,0)

    def test_candidate_keeps_recorded_transaction_fingerprint_without_filling(self):
        tx='0x'+'a'*64
        buy=('RESEARCH_TRADE',{'token':'b','sourceMs':10,'side':'BUY','price':'.6','size':'1',
                              'tradeId':json.dumps({'transaction_hash':tx,'asset_id':'b'})})
        result=self.run_tape(before_trade=[buy])
        example=next(row for row in result['examples'] if row['route']=='COMPLEMENT_BUY_CANDIDATE')
        self.assertEqual(example['transactionHash'],tx)
        self.assertEqual(example['firstToken'],'a');self.assertEqual(example['secondToken'],'b')
        self.assertFalse(result['examplesTruncated']); self.assertFalse(result['fillsInferred'])
