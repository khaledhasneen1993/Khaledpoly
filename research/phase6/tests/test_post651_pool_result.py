from pathlib import Path
import tempfile
import unittest

from research.phase6.post651_pool_result import ROOT,verify


class Post651PoolResultTest(unittest.TestCase):
    def test_retained_native653(self):
        r=verify();self.assertEqual((r['originalIdentities'],r['componentTuples']),(653,1553));self.assertEqual(r['priorBindingsPreserved'],651);self.assertFalse(r['marketNetPnlRecomputed'])

    def test_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.zip';p.write_bytes((ROOT/'ci-artifact.zip').read_bytes()+b'x')
            with self.assertRaises(ValueError):verify(p)


if __name__=='__main__':unittest.main()
