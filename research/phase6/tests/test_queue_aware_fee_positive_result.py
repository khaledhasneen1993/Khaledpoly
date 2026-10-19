import copy
from decimal import Decimal as D
import json
import unittest
from unittest.mock import patch
from research.phase6.queue_aware_fee_positive_result import ROOT,verify,saved
from research.phase6.queue_aware_fee_positive_exit import prepare
from research.phase6.queue_aware_exit_comparison import identical_inputs,compare
from research.phase6.queue_aware_recovery_exit import prepare as baseline


class FeePositiveResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=prepare();cls.report=json.loads((ROOT/'report.json').read_text(),parse_float=D)
        cls.artifact=json.loads((ROOT/'artifact-manifest.json').read_text())

    def check(self,report,artifact=None):
        with patch('research.phase6.queue_aware_fee_positive_result.prepare',return_value=self.seed):
            return verify(report,self.artifact if artifact is None else artifact)

    def test_exact_original_decision_fok_fee_and_net(self):
        r=self.check(self.report)
        self.assertEqual(r['makerOrders'],0);self.assertEqual(r['makerFills'],0)
        self.assertEqual(r['consumedOriginalGroups'],6);self.assertEqual(r['uniqueActualComponents'],11)
        self.assertEqual(r['exitAt'],1792269761319);self.assertEqual(r['exitOriginalSequence'],261117)
        self.assertEqual(D(r['conditionalExitFee']),D('.08736'))
        self.assertEqual(D(r['conditionalRoundTripNetAfterCosts']),D('.11264'))
        self.assertFalse(r['candidateAccountSimulated'])

    def test_fake_fee_price_clock_source_or_decision_rejected(self):
        for key,value in [('fee',D(0)),('notional',D('2.65'))]:
            bad=copy.deepcopy(self.report);bad['modelExitAllocations'][0]['result'][key]=value
            with self.assertRaisesRegex(ValueError,'FOK allocation/stop/fees'):self.check(bad)
        for key,value in [('at',1792269761318),('seq',261116)]:
            bad=copy.deepcopy(self.report);bad['modelExitAllocations'][0][key]=value
            with self.assertRaisesRegex(ValueError,'FOK allocation/stop/fees'):self.check(bad)
        bad=copy.deepcopy(self.report);bad['decisions'][0]['choice']['action']='WAIT'
        with self.assertRaisesRegex(ValueError,'decision trajectory'):self.check(bad)
        bad=copy.deepcopy(self.report);bad['modelExitAllocations'][0]['result']['legs'][0]['price']=D('.53')
        with self.assertRaisesRegex(ValueError,'FOK allocation/stop/fees'):self.check(bad)

    def test_scope_cannot_be_promoted_and_input_hash_cannot_drift(self):
        for key in ['candidateAccountSimulated','netPnlRecomputed','independentPaperQualificationAllowed','liveAllowed']:
            bad=copy.deepcopy(self.report);bad[key]=True
            with self.assertRaisesRegex(ValueError,'scope'):self.check(bad)
        a=copy.deepcopy(self.artifact);a['members']['input.json']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'frozen first exit input'):self.check(self.report,a)

    def test_native_report_integrity(self):
        actual=ROOT/'report.json'
        original=actual.read_bytes()
        def read_bytes(path):return original+b' ' if path==actual else bytes()
        with patch('pathlib.Path.read_bytes',read_bytes):
            with self.assertRaisesRegex(ValueError,'Changed native first exit report'):saved()

    def test_comparison_rejects_cost_state_source_or_new_parameters(self):
        base=baseline();candidate=prepare();identical_inputs(base,candidate)
        for key in ['initialQuantity','initialBasisPerShare','horizonMs']:
            bad=copy.deepcopy(candidate);bad[key]='changed'
            with self.assertRaisesRegex(ValueError,'source, state or costs differ'):identical_inputs(base,bad)
        bad=copy.deepcopy(candidate);bad['config']['minimumEdge']='0'
        with self.assertRaisesRegex(ValueError,'source, state or costs differ'):identical_inputs(base,bad)
        bad=copy.deepcopy(candidate);bad['extraFittedThreshold']='0.001'
        with self.assertRaisesRegex(ValueError,'input surface'):identical_inputs(base,bad)

    def test_saved_comparison_remains_no_go(self):
        r=compare();self.assertEqual(r['conditionalNetImprovement'],'0.15011')
        self.assertEqual(r['readiness'],'NO_GO');self.assertIsNone(r['fullAccountPnl'])
        self.assertFalse(r['independentPaperQualificationAllowed']);self.assertFalse(r['liveAllowed'])


if __name__=='__main__':unittest.main()
