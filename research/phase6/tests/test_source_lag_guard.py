import copy
import json
from pathlib import Path
import tempfile
import unittest
from research.phase6.source_lag_guard_build import materialize,SESSION,MATCHER,LABELS
from research.phase6.source_lag_guard_result import ROOT,verify,verify_inputs


class SourceLagGuardTest(unittest.TestCase):
    def test_frozen_generated_only(self):
        verify_inputs()
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'generated';r=materialize(out)
            self.assertEqual(r['defaultCoreFilesModified'],0);self.assertFalse(r['activationQueueFeeRiskParametersChanged'])
            self.assertIn('source>order.activated',(out/MATCHER).read_text());self.assertIn('at<now||externalMode',(out/SESSION).read_text());self.assertIn('SOURCE_LAG0',(out/LABELS).read_text())

    def test_atomic_and_original_preimage_synthetic_evidence(self):
        r=verify(json.loads((ROOT/'source-lag-guard-proof.json').read_bytes()));self.assertEqual(r['rejectionGuards'],29)

    def test_incomplete_or_promoted_proof_rejected(self):
        p=json.loads((ROOT/'source-lag-guard-proof.json').read_bytes())
        for k,v in [('rejectionGuards',[]),('nativePredicateCorrespondenceCases',1928),('integrationChecks',[]),('frontierEnvelopes',[]),('fourMonitorsHeldThroughCallback',False),('marketNetPnlRecomputed',True),('originalTapeReplayed',True),('liveAllowed',True)]:
            with self.subTest(key=k):
                changed=copy.deepcopy(p);changed[k]=v
                with self.assertRaises(ValueError):verify(changed)
