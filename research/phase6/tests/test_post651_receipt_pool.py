import copy,json,unittest

from research.phase6.post649_receipt_pool import build as parent_build
from research.phase6.post651_receipt_pool import build,identities,verify_native,ROOT,ORIGIN


class Post651ReceiptPoolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.pool=build();cls.parent=parent_build()

    def test_preserves651_adds_two_conditions(self):
        self.assertEqual([b for b in self.pool['bindings'] if b.get('origin')!=ORIGIN],self.parent['bindings']);added=[b for b in self.pool['bindings'] if b.get('origin')==ORIGIN]
        self.assertEqual([(b['seq'],b['eventIndex']) for b in added],[(9305,0),(83144,0)]);self.assertEqual([[m['matchType'] for m in b['matches']] for b in added],[['MINT'],['MINT']*2]);self.assertEqual(len({b['condition'] for b in added}),2);self.assertTrue(all(len(set(b['pair']))==2 and b['pairSource']=='FIXED_RECEIPT_GROUP_COMPLEMENT' for b in added));self.assertTrue(self.pool['multiMarketBindings']);self.assertEqual(len(self.pool['bindingMarketPairs']),2);self.assertEqual(self.pool['routeComponentCounts'],{'DIRECT':359,'MINT':1177,'MERGE':17})

    def test_exact653_identities_and_components(self):
        self.assertEqual(len(identities(self.pool)['observations']),653);self.assertEqual(self.pool['expectedComponentCount'],1553)

    def test_native_result_when_retained(self):
        if not (ROOT/'native-proof.json').exists():self.skipTest('CI proof pending')
        s=json.loads((ROOT/'summary.json').read_text());p=json.loads((ROOT/'native-proof.json').read_text());self.assertEqual(verify_native(p,s)['componentTuples'],1553);bad=copy.deepcopy(p);bad['pool']['consumedBindings']=652
        with self.assertRaises(ValueError):verify_native(bad,s)


if __name__=='__main__':unittest.main()
