from pathlib import Path
import tempfile
import unittest

from research.phase6.post653_pool_result import ROOT,verify


class Post653PoolResultTest(unittest.TestCase):
    def test_retained_native655(self):
        r=verify();self.assertEqual((r['originalIdentities'],r['componentTuples']),(655,1557));self.assertEqual(r['priorBindingsPreserved'],653);self.assertFalse(r['marketNetPnlRecomputed'])

    def test_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.zip';p.write_bytes((ROOT/'ci-artifact.zip').read_bytes()+b'x')
            with self.assertRaises(ValueError):verify(p)


if __name__=='__main__':unittest.main()
