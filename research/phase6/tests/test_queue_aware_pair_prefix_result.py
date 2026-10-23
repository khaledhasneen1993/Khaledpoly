import copy
from decimal import Decimal as D
import json
import unittest
from research.phase6.queue_aware_pair_prefix_result import ROOT,saved,verify


class PairPrefixResultTest(unittest.TestCase):
    def test_independent_both_queue_and_conserved_allocation_reproduction(self):
        r=saved();self.assertEqual(r['completeOriginalBindings'],40)
        self.assertEqual(r['actualActivationQueues'],['160','30'])
        self.assertEqual(r['actualRestingChecks'],15);self.assertEqual(r['uniqueActualComponents'],108)
        self.assertEqual(sorted(D(x) for x in r['allocatedSharesByToken'].values()),[0,5])
        self.assertFalse(r['netPnlRecomputed']);self.assertFalse(r['candidateAccountSimulated'])

    def test_fake_counterpart_queue_and_financial_scope_rejected(self):
        r=json.loads((ROOT/'report.json').read_text(),parse_float=D);a=json.loads((ROOT/'artifact-manifest.json').read_text())
        bad=copy.deepcopy(r);bad['diagnostics'][1]['initialQueueAhead']=0
        with self.assertRaisesRegex(ValueError,'activation queue'):verify(bad,a)
        bad=copy.deepcopy(r);bad['candidateAccountSimulated']=True
        with self.assertRaisesRegex(ValueError,'scope'):verify(bad,a)


if __name__=='__main__':unittest.main()
