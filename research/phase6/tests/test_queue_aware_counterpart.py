import copy
import tempfile
import unittest
from research.phase6.queue_aware_counterpart import selection,summarize,collect


class CounterpartSelectionTest(unittest.TestCase):
    def test_only_complete30_original_pre_first_fill_counterpart_observations(self):
        s=selection()
        self.assertEqual(len(s['transactions']),30);self.assertEqual(s['maxNewReceiptRequests'],30)
        self.assertEqual(s['targetQuote']['price'],'0.4');self.assertEqual(s['fixedHorizonMs'],1792269754123)
        self.assertEqual(s['remainingCounterpartObservationsAfterHorizon'],93)
        self.assertEqual(len({t['transactionHash'] for t in s['transactions']}),30)
        self.assertTrue(all(t['arrivalMs']<=s['fixedHorizonMs'] for t in s['transactions']))
        self.assertFalse(s['netPnlRecomputed'])

    def test_missing_receipt_is_unknown_never_zero(self):
        with self.assertRaisesRegex(ValueError,'unknown is not zero'):summarize(selection(),{})

    def test_resume_selection_change_and_broad_budget_fail_before_rpc(self):
        s=selection();calls=[]
        def read(method,params):calls.append(method);return '0x89'
        with tempfile.TemporaryDirectory() as out:
            bad=copy.deepcopy(s);bad['maxNewReceiptRequests']=31
            with self.assertRaisesRegex(ValueError,'frozen30'):collect(bad,out,read=read,pause=lambda _:None)
            with self.assertRaisesRegex(ValueError,'Selection changed'):collect(s,out,read=read,pause=lambda _:None)
        self.assertEqual(calls,[])


if __name__=='__main__':unittest.main()
