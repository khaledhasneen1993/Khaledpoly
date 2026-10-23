from pathlib import Path
import tempfile
import unittest

from research.phase6.post657_pool_replay_result import ROOT,verify


class Post657PoolReplayResultTest(unittest.TestCase):
    def test_retained_exact659_result(self):
        r=verify();self.assertEqual(r['modelFills'],0);self.assertFalse(r['completeAccountComparisonPerformed']);self.assertEqual(r['results']['candidate']['queueAbsorbed'],'9.55');self.assertEqual(r['results']['candidate']['actualQueues'],['1172.75','180'])

    def test_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.zip';p.write_bytes((ROOT/'ci-artifact.zip').read_bytes()+b'x')
            with self.assertRaises(ValueError):verify(p)


if __name__=='__main__':unittest.main()
