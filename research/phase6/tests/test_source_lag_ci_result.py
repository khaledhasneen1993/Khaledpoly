from pathlib import Path
import tempfile
import unittest
from research.phase6.source_lag_ci_result import load


class SourceLagNativeResultTest(unittest.TestCase):
    def test_retained_java21_proof(self):
        r=load();self.assertEqual(r['verifiedMembers'],13);self.assertFalse(r['newRuntimeShortcutEnabled'])

    def test_changed_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'fake.zip';path.write_bytes(b'not the native proof')
            with self.assertRaises(ValueError):load(path)
