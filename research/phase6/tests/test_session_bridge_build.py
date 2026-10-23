import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from research.phase6.session_bridge_build import FREEZE,SESSION,check_sources,materialize


class SessionBridgeBuildTest(unittest.TestCase):
    def test_exact_isolated_patch_preserves_all_default_core_sources(self):
        spec=json.loads(FREEZE.read_text());before={p:Path(p).read_bytes() for p in spec['coreSourcesSha256']}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'build';result=materialize(root)
            source=(root/SESSION).read_text()
            self.assertEqual(result['coreSources'],94);self.assertEqual(result['defaultCoreFilesModified'],0)
            self.assertIn('OfflineSessionLabels settlementLabels',source)
            self.assertIn('MIXED_BINDING_BRIDGE0) suspend()',source)
            self.assertIn('frozenQw0AndFeePositivePoliciesIntegrated',source)
        self.assertTrue(all(Path(p).read_bytes()==raw for p,raw in before.items()))

    def test_existing_or_in_repository_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileExistsError):materialize(tmp)
        with self.assertRaisesRegex(ValueError,'outside the repository'):materialize('research/output/unsafe-bridge-build')

    def test_changed_source_membership_or_digest_is_rejected(self):
        spec=json.loads(FREEZE.read_text());bad=copy.deepcopy(spec);bad['coreSourcesSha256'].pop(str(SESSION))
        with self.assertRaisesRegex(ValueError,'membership changed'):check_sources(bad)
        bad=copy.deepcopy(spec);bad['coreSourcesSha256'][str(SESSION)]='0'*64
        with self.assertRaisesRegex(ValueError,'Frozen bridge input changed'):check_sources(bad)

    def test_changed_research_patch_cannot_be_silently_used(self):
        spec=json.loads(FREEZE.read_text());bad=copy.deepcopy(spec);bad['buildInputsSha256']['research/phase6/mixed-session-bridge.patch']='0'*64
        with self.assertRaisesRegex(ValueError,'Frozen bridge input changed'):check_sources(bad)


if __name__=='__main__':unittest.main()
