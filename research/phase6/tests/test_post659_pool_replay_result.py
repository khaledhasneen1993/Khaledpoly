from pathlib import Path
import tempfile
import unittest

from research.phase6.post659_pool_replay_result import ROOT,verify


class Post659PoolReplayResultTest(unittest.TestCase):
    def test_retained_exact661_result(self):
        r=verify();self.assertEqual((r['nextReceiptTargets']['candidate']['seq'],r['nextReceiptTargets']['baseline']['seq']),(9982,83262));self.assertEqual(r['modelFills'],0);self.assertFalse(r['completeAccountComparisonPerformed'])

    def test_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.zip';p.write_bytes((ROOT/'ci-artifact.zip').read_bytes()+b'x')
            with self.assertRaises(ValueError):verify(p)


if __name__=='__main__':unittest.main()
