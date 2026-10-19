import copy
import json
import unittest
from unittest.mock import patch
from decimal import Decimal as D
from research.phase6.queue_aware_active_reduction_result import ROOT,verify
from research.phase6.queue_aware_reduction_context import prepare


class ActiveReductionResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs=prepare();cls.report=json.loads((ROOT/'report.json').read_text(),parse_float=D)
        cls.artifact=json.loads((ROOT/'artifact-manifest.json').read_text())

    def check(self,report):
        with patch('research.phase6.queue_aware_active_reduction_result.prepare',return_value=self.inputs):
            return verify(report,self.artifact)

    def test_three_original_queues_source_clock_and_360_components(self):
        r=self.check(self.report)
        self.assertEqual([a['initialQueue'] for a in r['activationEvidence']],['160','30','313.16'])
        self.assertEqual(r['uniqueActualComponents'],360)
        self.assertEqual(D(r['modelReductionFilledShares']),0);self.assertEqual(D(r['remainingUnhedgedShares']),5)
        self.assertEqual([D(p['queueAbsorbed']) for p in r['actualPriceCompatibleSellComponents']],[0,13])
        self.assertLess(r['actualPriceCompatibleSellComponents'][0]['sourceMs'],r['activationEvidence'][2]['at'])
        self.assertFalse(r['candidateAccountSimulated']);self.assertFalse(r['netPnlRecomputed'])

    def test_forged_queue_and_fake_fill_fail(self):
        bad=copy.deepcopy(self.report);bad['diagnostics'][2]['initialQueueAhead']=D('13')
        with self.assertRaisesRegex(ValueError,'queue/activation differs'):self.check(bad)
        bad=copy.deepcopy(self.report);bad['modelAllocations'].append(dict(id='qw0-gap-reduction',token=bad['diagnostics'][2]['token'],buy=False,price=D('.51'),size=D(5),at=1792269760853))
        with self.assertRaisesRegex(ValueError,'allocations differ'):self.check(bad)

    def test_financial_or_complete_scope_escalation_fails(self):
        for key in ['netPnlRecomputed','candidateAccountSimulated','liveAllowed','independentPaperQualificationAllowed']:
            bad=copy.deepcopy(self.report);bad[key]=True
            with self.assertRaisesRegex(ValueError,'scope'):self.check(bad)


if __name__=='__main__':unittest.main()
