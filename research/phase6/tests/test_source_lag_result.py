import copy
import json
import unittest
from research.phase6.source_lag_result import ROOT,verify,verify_inputs,original_frontier_context


class SourceLagProofTest(unittest.TestCase):
    def test_frozen_sources(self):verify_inputs()

    def test_retained_proof(self):
        result=verify(json.loads((ROOT/'source-lag-proof.json').read_bytes()))
        self.assertFalse(result['newRuntimeShortcutEnabled'])

    def test_incomplete_or_promoted_evidence_rejected(self):
        proof=json.loads((ROOT/'source-lag-proof.json').read_bytes())
        for key,value in [('contexts',[]),('proofPredicateRejections',[]),('matcherDifferentials',5143),('syntheticFutureFillEvents',112),('counterexamples',{}),('activationMsUnchanged',249),('queueMultiplierUnchanged',1),('fullMatchingStateEquivalent',True),('newAtomicSessionGuardImplemented',True),('newRuntimeShortcutEnabled',True),('originalTapeReplayed',True),('marketNetPnlRecomputed',True),('liveAllowed',True)]:
            with self.subTest(key=key):
                changed=copy.deepcopy(proof);changed[key]=value
                with self.assertRaises(ValueError):verify(changed)

    def test_previous_original_frontier_remains_blocked(self):
        r=original_frontier_context()
        self.assertEqual(r['results']['candidate']['actualInitialQueues'],[1182.3,180])
        self.assertTrue(r['results']['candidate']['runtimeShortcutStillBlocked'])
