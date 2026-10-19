import copy
import tempfile
import unittest
from research.phase6.queue_aware_postfill_receipts import selection,summarize,collect,known


class PostfillReceiptsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.spec=selection()

    def test_all79_original_post_fill_observations_not_price_selected(self):
        s=self.spec;self.assertEqual(len(s['transactions']),79)
        self.assertEqual(s['maxNewReceiptRequests'],79);self.assertEqual(s['targetQuote']['price'],'0.4')
        self.assertTrue(all(s['firstModelAllocationMs']<t['arrivalMs']<=s['fixedHorizonMs'] for t in s['transactions']))
        self.assertFalse(set(t['transactionHash'] for t in s['transactions'])&set(known()))

    def test_unknown_is_not_zero_and_request_expansion_rejected(self):
        with self.assertRaisesRegex(ValueError,'unknown is not zero'):summarize(self.spec,{})
        bad=copy.deepcopy(self.spec);bad['maxNewReceiptRequests']=80;calls=[]
        with tempfile.TemporaryDirectory() as out:
            with self.assertRaisesRegex(ValueError,'frozen79'):collect(bad,out,read=lambda *a:calls.append(a),pause=lambda _:None)
        self.assertEqual(calls,[])


if __name__=='__main__':unittest.main()
