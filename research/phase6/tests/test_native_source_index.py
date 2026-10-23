import copy
import json
import unittest
from research.phase6.native_source_index import ROOT, verify


class NativeSourceIndexResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof = json.loads((ROOT/'native-index-proof.json').read_bytes())

    def test_all643_parity_is_not_full_original_execution(self):
        result = verify(self.proof)
        self.assertEqual(result['originalIndexIdentities'], 16317)
        self.assertEqual(result['actualPreimagesMatched'], 643)
        self.assertEqual(result['rejectionGuards'], 23)
        self.assertTrue(result['original628ExecutionStillUnresolved'])

    def test_reject_scope_promotion(self):
        for field in ('runtimeOptimizationImplemented', 'atomicSessionGuardImplemented',
                      'originalTapeReplayed', 'modelFillsCreated', 'marketNetPnlRecomputed',
                      'fullAccountReplayAuthorized', 'independentPaperQualificationAllowed', 'liveAllowed'):
            proof = copy.deepcopy(self.proof); proof[field] = True
            with self.assertRaisesRegex(ValueError, 'authorize'):
                verify(proof)

    def test_reject_changed_source_or_incomplete_guards(self):
        for field, value in [('indexLogicalSha256', '0'*64), ('sourceIdentitiesSha256', '0'*64),
                             ('originalIdentities', 16316), ('actualRawPreimagesMatched', 642)]:
            proof = copy.deepcopy(self.proof); proof[field] = value
            with self.assertRaisesRegex(ValueError, 'source/counts'):
                verify(proof)
        for field in ('allRejectionsPoisonConsumption', 'fullModeFirstOriginal97Matched', 'fullModeMissing628Rejected'):
            proof = copy.deepcopy(self.proof); proof[field] = False
            with self.assertRaisesRegex(ValueError, 'guards'):
                verify(proof)
        proof = copy.deepcopy(self.proof); proof['rejectionGuards'].pop()
        with self.assertRaisesRegex(ValueError, 'guards'):
            verify(proof)

    def test_subset_does_not_certify_full_replay_or_routes(self):
        for field, value in [('completeOriginalConsumption', True), ('runtimeSkipAuthorized', True),
                             ('settlementRoutesValidatedByIndex', True), ('failed', True),
                             ('subsetPreimageTestOnly', False), ('consumedOriginalPreimages', 16317)]:
            proof = copy.deepcopy(self.proof); proof['preimageSubsetBeforeRejectedFinalization'][field] = value
            with self.assertRaisesRegex(ValueError, 'Subset'):
                verify(proof)


if __name__ == '__main__':
    unittest.main()
