import copy
from decimal import Decimal as D
import json
import unittest
from research.phase6.queue_aware_unhedged_timing_result import ROOT,saved,verify


class UnhedgedTimingResultTest(unittest.TestCase):
    def test_conditional_clock_and_exact_source_ack_reproduced(self):
        r=saved();self.assertEqual(r['actualPairPolicyChecks'],21)
        self.assertEqual(r['conditionalCancelRequestMs'],1792269759315)
        self.assertEqual(r['conditionalCancelDueMs'],1792269759565)
        self.assertEqual(r['conditionalCancelAck']['at'],1792269759566)
        self.assertEqual(r['sourcePostFillCounterpartObservations'],79)
        self.assertTrue(r['postFillCounterpartExecutionUnknown']);self.assertFalse(r['netPnlRecomputed'])

    def test_fake_ack_and_unsuppressed_financial_scope_rejected(self):
        e=json.loads((ROOT/'evidence.json').read_text());r=json.loads((ROOT/'report.json').read_text(),parse_float=D)
        a=json.loads((ROOT/'artifact-manifest.json').read_text())
        bad=copy.deepcopy(r);bad['actualCancelAck']['at']-=1
        with self.assertRaisesRegex(ValueError,'ack differs'):verify(e,bad,a)
        bad=copy.deepcopy(r);bad['allTradeVolumeSuppressed']=False
        with self.assertRaisesRegex(ValueError,'scope'):verify(e,bad,a)


if __name__=='__main__':unittest.main()
