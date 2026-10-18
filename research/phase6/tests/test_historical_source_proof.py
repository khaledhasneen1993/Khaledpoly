import json
from pathlib import Path
import tempfile
import unittest
from research.phase6.historical_source_proof import ARCHIVE,verify_historical_sources


class HistoricalSourceProofTest(unittest.TestCase):
    def test_exact_original_sources_preserved_for_both_completed_controls(self):
        for name in ('settlement-replay-freeze.json','exit-covered-replay-freeze.json'):
            verify_historical_sources(json.loads((Path('research/phase6')/name).read_text()))

    def test_no_fallback_for_changed_acceptance_or_unrelated_code(self):
        for name in ('research/phase2/acceptance.json','research/phase6/export_settlement_labels.py'):
            with self.assertRaisesRegex(ValueError,'hash differs'):
                verify_historical_sources(dict(filesSha256={name:'0'*64}))

    def test_changed_pinned_source_archive_cannot_bypass_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'changed.b64';raw=ARCHIVE.read_bytes()
            path.write_bytes((b'A' if raw[:1]!=b'A' else b'B')+raw[1:])
            with self.assertRaisesRegex(ValueError,'archive changed'):
                verify_historical_sources(dict(filesSha256={}),path)
