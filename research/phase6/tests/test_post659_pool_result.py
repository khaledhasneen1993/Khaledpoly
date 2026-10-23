from pathlib import Path
import tempfile
import unittest

from research.phase6.post659_pool_result import ROOT,verify


class Post659PoolResultTest(unittest.TestCase):
    def test_retained_native661(self):
        r=verify();self.assertEqual((r['originalIdentities'],r['componentTuples']),(661,1564));self.assertEqual(r['priorBindingsPreserved'],659);self.assertFalse(r['marketNetPnlRecomputed'])

    def test_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.zip';p.write_bytes((ROOT/'ci-artifact.zip').read_bytes()+b'x')
            with self.assertRaises(ValueError):verify(p)


if __name__=='__main__':unittest.main()
