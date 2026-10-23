from pathlib import Path
import tempfile
import unittest

from research.phase6.post657_pool_result import ROOT,verify


class Post657PoolResultTest(unittest.TestCase):
    def test_retained_native659(self):
        r=verify();self.assertEqual((r['originalIdentities'],r['componentTuples']),(659,1562));self.assertEqual(r['priorBindingsPreserved'],657);self.assertFalse(r['marketNetPnlRecomputed'])

    def test_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.zip';p.write_bytes((ROOT/'ci-artifact.zip').read_bytes()+b'x')
            with self.assertRaises(ValueError):verify(p)


if __name__=='__main__':unittest.main()
