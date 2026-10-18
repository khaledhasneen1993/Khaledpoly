import hashlib
import json
from pathlib import Path
import unittest
from research.phase6.export_settlement_labels import export
from research.phase6.historical_source_proof import verify_historical_sources


class ExportSettlementLabelsTest(unittest.TestCase):
    def test_frozen_java_bindings_reproduce_without_network_or_selection_changes(self):
        expected=json.loads(Path('research/experiments/settlement-lab0-20261018/replay-labels.json').read_text())
        self.assertEqual(export(),expected)
        self.assertEqual(len(expected['bindings']),5)
        self.assertTrue(expected['partialLabels'])
        self.assertFalse(expected['liveAllowed'])

    def test_original_sources_and_current_config_acceptance_hashes_match(self):
        freeze=json.loads(Path('research/phase6/settlement-replay-freeze.json').read_text())
        verify_historical_sources(freeze)
        self.assertFalse(freeze['independentPaperQualificationAllowed'])
