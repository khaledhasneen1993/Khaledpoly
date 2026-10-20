import copy,json,tempfile,unittest
from pathlib import Path
from research.phase6.postactivation_receipt_pool import build as parent_build
from research.phase6.next_postactivation_receipt_pool import build,identities,verify_native,ROOT,ORIGIN
class NextPoolTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.pool=build();cls.parent=parent_build()
 def test_preserves645_adds_two(self):
  self.assertEqual([b for b in self.pool['bindings'] if b.get('origin')!=ORIGIN],self.parent['bindings']);added=[b for b in self.pool['bindings'] if b.get('origin')==ORIGIN];self.assertEqual([(b['seq'],b['eventIndex']) for b in added],[(9060,0),(82986,0)]);self.assertEqual([b['matches'][0]['matchType'] for b in added],['DIRECT','DIRECT']);self.assertEqual(self.pool['routeComponentCounts'],{'DIRECT':357,'MINT':1162,'MERGE':17})
 def test_exact647_identities(self):self.assertEqual(len(identities(self.pool)['observations']),647)
 def test_native_result_when_retained(self):
  if not (ROOT/'native-proof.json').exists():self.skipTest('CI proof pending')
  s=json.loads((ROOT/'summary.json').read_text());p=json.loads((ROOT/'native-proof.json').read_text());self.assertEqual(verify_native(p,s)['componentTuples'],1536);bad=copy.deepcopy(p);bad['pool']['consumedBindings']=646
  with self.assertRaises(ValueError):verify_native(bad,s)
