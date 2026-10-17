"""Engineering candidate cannot be conflated with external market acceptance."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from research.phase6.software_gate import inventory, REQUIRED


class CandidateGateTest(unittest.TestCase):
    def test_present_real_source_is_no_go_outside_ci(self):
        result=inventory(ROOT)
        self.assertEqual(result['missing'],[])
        self.assertTrue(result['engineeringArtifactsPresent'])
        self.assertFalse(result['softwareReviewCandidate'])
        self.assertEqual(result['decision'],'NO_GO')
        self.assertFalse(result['realMoneyExecutionPermitted'])
        self.assertFalse(result['sevenFullUtcDaysMarketCaptureVerified'])

    def test_missing_root_cannot_claim_software_complete(self):
        with tempfile.TemporaryDirectory() as folder:
            r=inventory(folder,ci_context=True,expected_revision='bogus')
            self.assertEqual(len(r['missing']),len(REQUIRED))
            self.assertFalse(r['softwareReviewCandidate'])
            self.assertFalse(r['liveAllowed'])

    def test_fake_revision_or_synthetic_ci_flag_never_enables_live(self):
        with patch('research.phase6.software_gate.subprocess.run') as git:
            git.return_value.stdout='expected-revision\\n'
            r=inventory(ROOT,ci_context=True,expected_revision='different-revision')
        self.assertFalse(r['softwareReviewCandidate'])
        self.assertFalse(r['liveAllowed'])
        self.assertEqual(r['decision'],'NO_GO')

if __name__=='__main__':
    unittest.main()
