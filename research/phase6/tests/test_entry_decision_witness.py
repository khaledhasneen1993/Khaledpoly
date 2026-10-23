import copy
import unittest
from research.phase6.entry_decision_witness import golden, verify_report


class EntryDecisionWitnessReportTest(unittest.TestCase):
    def fixture(self):
        ref=golden();report=copy.deepcopy(ref)
        report['entryDecisionWitnesses']=[dict(condition='c',at=100,nextDecisionMs=350,actualDecisionReasonDelta={'NET_EDGE':1})]
        return ref,report,[dict(condition='c',startMs=0,endMs=200)]

    def test_all_original_account_fields_must_reproduce(self):
        ref,report,windows=self.fixture();r=verify_report(report,ref,windows)
        self.assertEqual(r['netRealizedPnl'],0);self.assertEqual(r['fills'],0)
        for key in ('feesAndSettlementCosts','fills','submittedOrders','decisionReasons','makerExecutionDiagnostics','settlementExperiment'):
            bad=copy.deepcopy(report);bad[key]='tampered'
            with self.assertRaisesRegex(ValueError,'changed original fields'):
                verify_report(bad,ref,windows)

    def test_no_missing_or_outside_window_witnesses(self):
        ref,report,windows=self.fixture()
        for rows in ([],[dict(report['entryDecisionWitnesses'][0],at=201)],
                     [dict(report['entryDecisionWitnesses'][0],nextDecisionMs=100)]):
            bad=dict(report,entryDecisionWitnesses=rows)
            with self.assertRaises(ValueError):verify_report(bad,ref,windows)


if __name__=='__main__':unittest.main()
