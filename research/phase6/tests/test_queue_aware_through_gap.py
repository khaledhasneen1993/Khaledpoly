import unittest
from research.phase6.queue_aware_through_gap import prepare


class ThroughGapPreparationTest(unittest.TestCase):
    def test_complete148_disjoint_groups_and_unmodified_gap(self):
        c,m,e=prepare();self.assertEqual(len(m['bindings']),148)
        self.assertEqual(m['bReceiptsThroughMs'],1792269759566);self.assertEqual(m['horizonMs'],1792269760873)
        self.assertFalse(m['counterpartExecutionOmitted']);self.assertFalse(m['restingRiskCancellationOmitted'])
        ids=[p['identity'] for b in m['bindings'] for p in b['parts']]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertTrue(e['timing']['accountRiskAndOtherMarketsOmitted'])


if __name__=='__main__':unittest.main()
