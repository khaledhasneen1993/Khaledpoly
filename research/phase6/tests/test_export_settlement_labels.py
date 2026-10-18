import hashlib
import json
from pathlib import Path
import unittest
from research.phase6.export_settlement_labels import export


class ExportSettlementLabelsTest(unittest.TestCase):
    def test_frozen_java_bindings_reproduce_without_network_or_selection_changes(self):
        expected=json.loads(Path('research/experiments/settlement-lab0-20261018/replay-labels.json').read_text())
        self.assertEqual(export(),expected)
        self.assertEqual(len(expected['bindings']),5)
        self.assertTrue(expected['partialLabels'])
        self.assertFalse(expected['liveAllowed'])

    def test_predeclared_source_config_and_acceptance_hashes_match(self):
        freeze=json.loads(Path('research/phase6/settlement-replay-freeze.json').read_text())
        for path,digest in freeze['filesSha256'].items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(),digest,path)
        self.assertFalse(freeze['independentPaperQualificationAllowed'])
