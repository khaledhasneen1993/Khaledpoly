import json
import unittest
from research.phase6.export_exit_covered_labels import export, OLD_LABELS


class ExitCoveredLabelsTest(unittest.TestCase):
    def test_seven_exact_bindings_preserve_previous_five(self):
        labels = export(); old = json.loads(OLD_LABELS.read_text())
        self.assertEqual(labels['bindings'][:5],old['bindings'])
        self.assertEqual(len(labels['bindings']),7)
        self.assertEqual(labels['bindings'][5]['seq'],153844)
        self.assertEqual(labels['bindings'][6]['seq'],153978)
        self.assertEqual({m['matchType'] for m in labels['bindings'][5]['matches']},{'DIRECT'})
        self.assertEqual({m['matchType'] for m in labels['bindings'][6]['matches']},{'MINT'})
        self.assertTrue(labels['partialLabels']); self.assertFalse(labels['liveAllowed'])
