from pathlib import Path
import tempfile
import unittest

from research.phase6.post655_pool_result import ROOT,verify


class Post655PoolResultTest(unittest.TestCase):
    def test_retained_native657(self):
        r=verify();self.assertEqual((r['originalIdentities'],r['componentTuples']),(657,1559));self.assertEqual(r['priorBindingsPreserved'],655);self.assertFalse(r['marketNetPnlRecomputed'])

    def test_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.zip';p.write_bytes((ROOT/'ci-artifact.zip').read_bytes()+b'x')
            with self.assertRaises(ValueError):verify(p)


if __name__=='__main__':unittest.main()
