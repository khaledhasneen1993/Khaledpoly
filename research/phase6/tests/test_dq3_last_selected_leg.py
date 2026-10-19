import json
import unittest
from research.phase6.dq3_last_selected_leg import ROOT,previous_evidence,next_selection,coverage


class LastSelectedLegTest(unittest.TestCase):
    def test_exact_previous_coverage_and_remaining_scope(self):
        evidence=previous_evidence();self.assertEqual(len(evidence),49)
        self.assertEqual(sum(l['complete'] for l in coverage(evidence)['legs']),10)
        s=next_selection(evidence)
        self.assertEqual(s,json.loads((ROOT/'last-selected-leg.json').read_text()))
        self.assertEqual(s['state']['originalSequence'],299650);self.assertEqual(s['targetQuote']['price'],'0.49')
        self.assertEqual(s['maxNewReceiptRequests'],19);self.assertEqual(len(s['transactions']),19)
        txs={t['transactionHash'] for t in s['transactions']}
        self.assertEqual(len(txs),19);self.assertFalse(txs&set(evidence))
        self.assertFalse(s['actualOrderOrObservedActivationClaimed'])


if __name__=='__main__':unittest.main()
