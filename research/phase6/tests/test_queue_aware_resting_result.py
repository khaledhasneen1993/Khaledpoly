import copy
from decimal import Decimal as D
import json
import unittest
from research.phase6.queue_aware_resting_result import ROOT,saved,verify


class RestingResultTest(unittest.TestCase):
    def test_complete_source_callback_and_conditional_allocation_reproduction(self):
        r=saved()
        self.assertEqual(r['actualPairPolicyChecks'],15)
        self.assertEqual(r['consumedTargetBindings'],10)
        self.assertEqual(len(r['matchedOriginalWitnessSequences']),5)
        self.assertEqual(D(r['conditionalTargetShares']),5)
        self.assertFalse(r['netPnlRecomputed']);self.assertTrue(r['counterpartExecutionUnknown'])

    def test_changed_resting_check_and_fake_financial_scope_rejected(self):
        e=json.loads((ROOT/'evidence.json').read_text());r=json.loads((ROOT/'report.json').read_text(),parse_float=D)
        a=json.loads((ROOT/'artifact-manifest.json').read_text())
        bad=copy.deepcopy(e);bad['checks'][0]['volatility']='0'
        with self.assertRaisesRegex(ValueError,'reconstruction'):verify(bad,r,a)
        bad=copy.deepcopy(r);bad['counterpartExecutionOmitted']=False
        with self.assertRaisesRegex(ValueError,'scope'):verify(e,bad,a)


if __name__=='__main__':unittest.main()
