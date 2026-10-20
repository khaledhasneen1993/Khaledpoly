import copy
import json
import unittest
from research.phase6.no_order_result import ROOT,verify

class NoOrderResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.proof=json.loads((ROOT/'no-order-proof.json').read_text())

    def test_actual_components_and_synthetic_differential_scope(self):
        p=verify(self.proof);self.assertEqual(p['matcherCases'],2572);self.assertEqual(p['guardRejections'],12)
        self.assertFalse(p['runtimeOptimizationAuthorized']);self.assertTrue(p['original628StillUnresolved'])

    def test_no_runtime_profit_or_full_equivalence_promotion(self):
        for k in ('runtimeOptimizationImplemented','unknownObservationsSkipped','fullMatchingStateEquivalent','sessionLevelEquivalenceProven','marketNetPnlRecomputed','liveAllowed'):
            p=copy.deepcopy(self.proof);p[k]=True
            with self.assertRaisesRegex(ValueError,'authorize'):verify(p)

    def test_counterexamples_and_all_private_state_must_be_retained(self):
        for k in ('allOtherPrivateMatchingFieldsCompared','repeatedComponentFutureDivergenceDetected','legacyPublicPrintBookkeepingDivergenceDetected'):
            p=copy.deepcopy(self.proof);p[k]=False
            with self.assertRaisesRegex(ValueError,'counterexample'):verify(p)
        p=copy.deepcopy(self.proof);p['excludedMatchingFields'].append('orders')
        with self.assertRaisesRegex(ValueError,'bounded'):verify(p)

    def test_source_counts_and_unsafe_guard_cannot_drift(self):
        p=copy.deepcopy(self.proof);p['sourceIdentitiesSha256']='0'*64
        with self.assertRaisesRegex(ValueError,'source'):verify(p)
        p=copy.deepcopy(self.proof);p['guardRejections'].remove('PENDING_FOK')
        with self.assertRaisesRegex(ValueError,'guard'):verify(p)
        p=copy.deepcopy(self.proof);p['separateSyntheticSessionDifferential']['futureEntryAndActivationEqual']=False
        with self.assertRaisesRegex(ValueError,'session/ledger'):verify(p)

if __name__=='__main__':unittest.main()
