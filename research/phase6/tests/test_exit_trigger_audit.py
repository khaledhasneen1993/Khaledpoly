import base64
import copy
import gzip
import json
import unittest
from research.phase6.exit_trigger_audit import ROOT, selection_and_frames, validate_bindings, summarize


class ExitTriggerAuditTest(unittest.TestCase):
    def test_exact_original_bindings(self):
        selection, pair = selection_and_frames()
        self.assertEqual([x['sample']['size'] for x in selection['transactions']], ['13', '5'])
        self.assertEqual(len(pair), 2)

    def test_changed_raw_normalized_and_fill_fail_closed(self):
        selection, _ = selection_and_frames()
        frames = json.loads(gzip.decompress(base64.b64decode((ROOT / 'original-frames.json.gz.b64').read_bytes())))
        with open('research/experiments/settlement-replay-20261018/candidate-report.original.json') as f:
            account = json.load(f)
        for kind in ('raw', 'normalized', 'execution'):
            changed = copy.deepcopy(frames); report = copy.deepcopy(account)
            if kind == 'raw': changed[0]['raw']['arrivalMs'] += 1
            elif kind == 'normalized': changed[0]['normalized']['data']['events'][0]['data']['size'] = '99'
            else: next(x for x in report['executions'] if x['at'] == selection['expectedExecutions'][0]['at'])['size'] = 99
            with self.assertRaises(ValueError): validate_bindings(selection, changed, report)

    def test_only_same_price_own_side_direct_volume_is_counted(self):
        selection, _ = selection_and_frames(); token = selection['cohorts'][0]['orderDiagnostic']['token']
        components = [dict(route='DIRECT', makerToken=token, makerSide='SELL', makerPrice='.47', sharesRaw=3000000),
                      dict(route='DIRECT', makerToken=token, makerSide='SELL', makerPrice='.46', sharesRaw=2000000),
                      dict(route='MINT', makerToken='other', makerSide='BUY', makerPrice='.53', sharesRaw=8000000)]
        group = dict(exchange='venue', groupLogIndex=7, components=components, routeSharesRaw={'DIRECT':5000000,'MINT':8000000})
        report = dict(results=[dict(transactionHash='tx',routeConservation=dict(uniqueConservedGroup=True, matchingGroups=[group]),
                    matches=[dict(exchange='venue',ordersMatchedLogIndex=7,maker=dict(feeRaw=0),taker=dict(feeRaw=42))])])
        result = summarize(report, selection)
        self.assertEqual(result['observations'][0]['ownSideSamePriceDirectSharesRaw'],3000000)
        self.assertEqual(result['observations'][0]['takerFeeRaw'],42)
        self.assertFalse(result['queueAllocationProven']); self.assertEqual(result['fillsCreated'],0)
        report['results'][0]['routeConservation']['uniqueConservedGroup'] = False
        with self.assertRaises(ValueError): summarize(report, selection)
