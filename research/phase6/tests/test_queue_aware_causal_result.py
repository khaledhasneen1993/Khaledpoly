import copy
from decimal import Decimal as D
import json
import unittest
from research.phase6.queue_aware_causal_result import QROOT,load,verify


class QueueAwareCausalResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.context,cls.bindings,cls.report=load()

    def test_independent_source_and_conserved_allocation_reproduction_not_profit(self):
        r=verify(self.context,self.bindings,self.report)
        self.assertEqual(r,json.loads((QROOT/'causal-result/verification.json').read_text()))
        self.assertEqual(r['originalLabelsConsumed'],39);self.assertEqual(r['uniqueActualComponents'],121)
        self.assertEqual(D(r['initialQueueAhead']),160);self.assertEqual(D(r['conditionalAllocatedShares']),5)
        self.assertEqual(D(r['queueAbsorbed']),160);self.assertEqual(r['conditionalFillTimes'],[1792269754123])
        self.assertFalse(r['netPnlRecomputed']);self.assertFalse(r['independentPaperQualificationAllowed'])

    def test_extra_conditional_fill_and_fake_queue_are_rejected(self):
        changed=copy.deepcopy(self.report);changed['conditionalModelFills'][0]['size']=D(6)
        with self.assertRaisesRegex(ValueError,'allocations differ'):verify(self.context,self.bindings,changed)
        changed=copy.deepcopy(self.report);changed['diagnostics'][0]['initialQueueAhead']=D(0)
        with self.assertRaisesRegex(ValueError,'queue/post-only'):verify(self.context,self.bindings,changed)


if __name__=='__main__':unittest.main()
