import copy,json,tempfile,unittest
from pathlib import Path

from research.phase6.next_postactivation_receipt_pool import build as parent_build
from research.phase6.post647_receipt_pool import build,identities,verify_native,ROOT,ORIGIN


class Post647ReceiptPoolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.pool=build();cls.parent=parent_build()

    def test_preserves647_adds_two(self):
        self.assertEqual([b for b in self.pool['bindings'] if b.get('origin')!=ORIGIN],self.parent['bindings']);added=[b for b in self.pool['bindings'] if b.get('origin')==ORIGIN]
        self.assertEqual([(b['seq'],b['eventIndex']) for b in added],[(9082,0),(83030,0)]);self.assertEqual([[m['matchType'] for m in b['matches']] for b in added],[['DIRECT','DIRECT'],['MINT','MINT']]);self.assertEqual(self.pool['routeComponentCounts'],{'DIRECT':359,'MINT':1164,'MERGE':17})

    def test_exact649_identities_and_components(self):
        self.assertEqual(len(identities(self.pool)['observations']),649);self.assertEqual(self.pool['expectedComponentCount'],1540)

    def test_native_result_when_retained(self):
        if not (ROOT/'native-proof.json').exists():self.skipTest('CI proof pending')
        s=json.loads((ROOT/'summary.json').read_text());p=json.loads((ROOT/'native-proof.json').read_text());self.assertEqual(verify_native(p,s)['componentTuples'],1540);bad=copy.deepcopy(p);bad['pool']['consumedBindings']=648
        with self.assertRaises(ValueError):verify_native(bad,s)


if __name__=='__main__':unittest.main()
