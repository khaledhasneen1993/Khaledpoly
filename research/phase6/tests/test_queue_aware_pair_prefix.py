import unittest
from research.phase6.queue_aware_pair_prefix import prepare


class PairPrefixTest(unittest.TestCase):
    def test_complete_disjoint_both_leg_source_bound_prefix(self):
        context,m,e=prepare()
        self.assertEqual(len(m['bindings']),40)
        self.assertEqual(len({b['transactionHash'] for b in m['bindings']}),40)
        self.assertEqual(len(e['checks']),15)
        self.assertFalse(m['counterpartExecutionOmitted']);self.assertFalse(m['restingRiskCancellationOmitted'])
        self.assertTrue(all(b['at']<=m['fixedHorizonMs'] for b in m['bindings']))
        ids=[p['identity'] for b in m['bindings'] for p in b['parts']]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertFalse(e['candidateAccountSimulated']);self.assertFalse(e['netPnlRecomputed'])


if __name__=='__main__':unittest.main()
