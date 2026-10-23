import copy
import json
from pathlib import Path
import tempfile
import unittest
from research.phase6.preactivation_build import materialize,SESSION,MATCHER,LABELS
from research.phase6.preactivation_result import verify,verify_inputs

ROOT=Path('research/experiments/preactivation-20261020')


class TemporalProofTest(unittest.TestCase):
    def test_freeze_and_generated_only(self):
        verify_inputs()
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'generated';result=materialize(out)
            self.assertFalse(result['activationQueueFeeRiskParametersChanged'])
            self.assertEqual(result['defaultCoreFilesModified'],0)
            self.assertIn('equals("OPEN")',(out/SESSION).read_text())
            self.assertIn('order.activation<=at',(out/MATCHER).read_text())
            self.assertIn('PRE_ACTIVATION0',(out/LABELS).read_text())

    def test_retained_bounded_proof(self):
        self.assertEqual(verify(ROOT)['temporalGuards'],23)

    def test_tampering_rejected(self):
        original=json.loads((ROOT/'preactivation-proof.json').read_bytes())
        for key,value in [('pendingDifferentials',5143),('rejectionGuards',[]),('queueMultiplierUnchanged',1),('fullMatchingStateEquivalent',True),('marketNetPnlRecomputed',True),('liveAllowed',True)]:
            with self.subTest(key=key),tempfile.TemporaryDirectory() as tmp:
                p=copy.deepcopy(original);p[key]=value;root=Path(tmp)
                (root/'preactivation-proof.json').write_text(json.dumps(p));(root/'preactivation-session-proof.json').write_bytes((ROOT/'preactivation-session-proof.json').read_bytes())
                with self.assertRaises(ValueError):verify(root)
