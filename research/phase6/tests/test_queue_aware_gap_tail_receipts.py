import copy
import json
import tempfile
import unittest
from research.phase6.queue_aware_gap_tail_receipts import QROOT,selection,summarize,collect


class GapTailSelectionTest(unittest.TestCase):
    def test_all14_original_tail_groups_and_unchanged_hedge_quote(self):
        s=selection();self.assertEqual(len(s['transactions']),14);self.assertEqual(s['maxNewReceiptRequests'],14)
        self.assertEqual(s,json.loads((QROOT/'gap-tail-selection.json').read_text()))
        self.assertEqual(s['hypotheticalUnchangedHedgeQuote']['price'],'0.51')
        self.assertTrue(all(s['afterCancelAckExclusiveMs']<t['arrivalMs']<s['fixedHorizonMs'] for t in s['transactions']))
        self.assertFalse(s['netPnlRecomputed'])

    def test_unknown_is_not_zero_and_broad_request_rejected_before_rpc(self):
        s=selection()
        with self.assertRaisesRegex(ValueError,'unknown is not zero'):summarize(s,{})
        bad=copy.deepcopy(s);bad['maxNewReceiptRequests']=15;calls=[]
        with tempfile.TemporaryDirectory() as out:
            with self.assertRaisesRegex(ValueError,'frozen14'):collect(bad,out,read=lambda *args:calls.append(args),pause=lambda _:None)
        self.assertEqual(calls,[])


if __name__=='__main__':unittest.main()
