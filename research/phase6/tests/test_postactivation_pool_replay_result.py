import copy
from pathlib import Path
import tempfile
import unittest
from research.phase6.postactivation_pool_replay_result import verify,ROOT


class PostActivationPoolReplayResultTest(unittest.TestCase):
    def test_retained_failure_is_not_pnl_and_has_two_exact_next_targets(self):
        r=verify();self.assertEqual(set(r['nextReceiptTargets']),{'baseline','candidate'})
        self.assertEqual(r['results']['baseline']['knownReceiptBindingsConsumed'],3)
        self.assertEqual(r['results']['candidate']['knownReceiptBindingsConsumed'],2)
        self.assertEqual(r['modelFills'],0);self.assertFalse(r['marketNetPnlRecomputed'])

    def test_changed_archive_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.zip';p.write_bytes((ROOT/'ci-artifact.zip').read_bytes()[:-1])
            with self.assertRaisesRegex(ValueError,'artifact'):verify(p)


if __name__=='__main__':unittest.main()
