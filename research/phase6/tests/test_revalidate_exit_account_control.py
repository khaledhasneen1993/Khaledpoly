from pathlib import Path
import tempfile
import unittest
from research.phase6.revalidate_exit_account_control import ROOT, revalidate


class AccountControlArchiveTest(unittest.TestCase):
    def test_original_account_audits_provenance_and_conservation(self):
        report = revalidate()
        self.assertEqual(report['finalFillDelayMs'],90)
        for mode in ('baseline','candidate'):
            variant = report['variants'][mode]
            self.assertEqual(variant['netRealizedPnl'],-.85)
            self.assertEqual(variant['cash'],499.15)
            self.assertEqual(variant['fills'],3)
            self.assertEqual(variant['residualExpiryWorstCaseNotional'],0)
        self.assertEqual(report['networkRequests'],0)
        self.assertEqual(report['accountReruns'],0)
        self.assertFalse(report['independentPaperQualificationAllowed'])

    def test_tampered_original_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'tampered.b64'; raw = (ROOT / 'artifact.zip.b64').read_bytes()
            path.write_bytes((b'A' if raw[:1] != b'A' else b'B')+raw[1:])
            with self.assertRaisesRegex(ValueError,'hash changed'): revalidate(path)
