import copy,json,unittest

from research.phase6.post659_receipt_pool import build as parent_build
from research.phase6.post661_receipt_pool import build,identities,verify_native,ROOT,ORIGIN


class Post661ReceiptPoolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.parent=parent_build();cls.pool=build(cls.parent)

    def test_preserves661_adds_two_receipts(self):
        self.assertEqual([b for b in self.pool['bindings'] if b.get('origin')!=ORIGIN],self.parent['bindings']);added=[b for b in self.pool['bindings'] if b.get('origin')==ORIGIN]
        self.assertEqual([(b['seq'],b['eventIndex']) for b in added],[(9982,0),(83262,0)]);self.assertEqual([[m['matchType'] for m in b['matches']] for b in added],[['DIRECT','MINT','MINT','MINT','MINT'],['MINT','MINT','DIRECT','MINT','MINT']]);self.assertTrue(all(len(set(b['pair']))==2 and b['pairSource']=='FIXED_RECEIPT_GROUP_COMPLEMENT' for b in added));self.assertTrue(self.pool['multiMarketBindings']);self.assertEqual(self.pool['routeComponentCounts'],{'DIRECT':361,'MINT':1196,'MERGE':17})

    def test_exact663_identities_and_components(self):
        self.assertEqual(len(identities(self.pool,self.parent)['observations']),663);self.assertEqual(self.pool['expectedComponentCount'],1574)

    def test_native_result_when_retained(self):
        if not (ROOT/'native-proof.json').exists():self.skipTest('CI proof pending')
        s=json.loads((ROOT/'summary.json').read_text());p=json.loads((ROOT/'native-proof.json').read_text());self.assertEqual(verify_native(p,s)['componentTuples'],1574);bad=copy.deepcopy(p);bad['pool']['consumedBindings']=662
        with self.assertRaises(ValueError):verify_native(bad,s)


if __name__=='__main__':unittest.main()
