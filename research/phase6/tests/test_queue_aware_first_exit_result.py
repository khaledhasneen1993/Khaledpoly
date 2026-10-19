import copy
from decimal import Decimal as D
import json
import unittest
from unittest.mock import patch
from research.phase6.queue_aware_first_exit_result import ROOT,verify
from research.phase6.queue_aware_recovery_exit import prepare


class FirstExitResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=prepare();cls.report=json.loads((ROOT/'report.json').read_text(),parse_float=D)
        cls.artifact=json.loads((ROOT/'artifact-manifest.json').read_text())

    def check(self,report):
        with patch('research.phase6.queue_aware_first_exit_result.prepare',return_value=self.seed):return verify(report,self.artifact)

    def test_all14_lifecycles_and_439_groups_fok_fees_and_conditional_loss(self):
        r=self.check(self.report);self.assertEqual(r['makerOrders'],14);self.assertEqual(r['makerFills'],0)
        self.assertEqual(r['consumedOriginalGroups'],439);self.assertEqual(r['uniqueActualComponents'],1013)
        self.assertEqual(D(r['conditionalRoundTripNetAfterCosts']),D('-.03747'))
        self.assertEqual(D(r['conditionalExitFee']),D('.08747'));self.assertFalse(r['candidateAccountSimulated'])

    def test_fake_lower_fee_or_queue_cannot_improve_result(self):
        bad=copy.deepcopy(self.report);bad['modelExitAllocations'][0]['result']['fee']=D(0)
        with self.assertRaisesRegex(ValueError,'FOK allocation/stop/fees'):self.check(bad)
        bad=copy.deepcopy(self.report);bad['diagnostics'][1]['initialQueueAhead']=D(0)
        with self.assertRaisesRegex(ValueError,'queue/cancel'):self.check(bad)

    def test_full_account_or_live_scope_escalation_fails(self):
        for key in ['candidateAccountSimulated','netPnlRecomputed','independentPaperQualificationAllowed','liveAllowed']:
            bad=copy.deepcopy(self.report);bad[key]=True
            with self.assertRaisesRegex(ValueError,'scope'):self.check(bad)


if __name__=='__main__':unittest.main()
