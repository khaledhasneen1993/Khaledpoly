import json
from pathlib import Path
import unittest
from research.phase6.export_exit_window_labels import export


class CompleteWindowLabelsTest(unittest.TestCase):
    def test_all_nine_exit_observations_no_subset_or_aggregate_credit(self):
        labels=export();old=json.loads(Path('research/experiments/settlement-lab0-20261018/replay-labels.json').read_text())
        seven=json.loads(Path('research/experiments/exit-covered-replay-20261018/replay-labels.json').read_text())
        self.assertEqual(labels['bindings'][:5],old['bindings'])
        self.assertEqual(labels['bindings'][:7],seven['bindings'])
        self.assertEqual(len(labels['bindings']),14)
        self.assertEqual(labels['bindings'][7]['at'],1792269695159)
        self.assertEqual({m['matchType'] for b in labels['bindings'][6:] for m in b['matches']},{'MINT'})
        self.assertEqual(labels['bindings'][-1]['at'],1792269696270)
        self.assertTrue(labels['partialLabels']);self.assertFalse(labels['liveAllowed'])
