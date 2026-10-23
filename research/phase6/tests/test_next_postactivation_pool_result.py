import copy,tempfile,unittest
from pathlib import Path
from research.phase6.next_postactivation_pool_result import ROOT,verify
class NextPoolResultTest(unittest.TestCase):
 def test_retained_native647(self):
  r=verify();self.assertEqual((r['originalIdentities'],r['componentTuples']),(647,1536));self.assertFalse(r['marketNetPnlRecomputed'])
 def test_corruption_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'bad.zip';p.write_bytes((ROOT/'ci-artifact.zip').read_bytes()+b'x')
   with self.assertRaises(ValueError):verify(p)
