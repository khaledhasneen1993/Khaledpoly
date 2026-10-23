import unittest
from research.phase6.queue_aware_through_gap import prepare


class ThroughGapPreparationTest(unittest.TestCase):
    def test_actual_empty_frames_do_not_advance_post_ack_strategy_callback(self):
        from research.phase6.queue_aware_causal_result import load
        context,_,_=load();rows={r['input']['seq']:r['input'] for r in context['records']}
        for seq,at in [(259279,1792269759565),(259281,1792269759566)]:
            self.assertEqual(rows[seq]['arrivalMs'],at)
            self.assertEqual(rows[seq]['kind'],'RESEARCH_FRAME');self.assertEqual(rows[seq]['data']['events'],[])
        self.assertEqual(rows[259283]['arrivalMs'],1792269759566)
        self.assertEqual([e['kind'] for e in rows[259283]['data']['events']],['BOOK','BOOK'])

    def test_complete148_disjoint_groups_and_unmodified_gap(self):
        c,m,e=prepare();self.assertEqual(len(m['bindings']),148)
        self.assertEqual(m['bReceiptsThroughMs'],1792269759566);self.assertEqual(m['horizonMs'],1792269760873)
        self.assertFalse(m['counterpartExecutionOmitted']);self.assertFalse(m['restingRiskCancellationOmitted'])
        ids=[p['identity'] for b in m['bindings'] for p in b['parts']]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertTrue(e['timing']['accountRiskAndOtherMarketsOmitted'])


if __name__=='__main__':unittest.main()
