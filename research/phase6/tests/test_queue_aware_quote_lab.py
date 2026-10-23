import copy
from decimal import Decimal as D
import unittest
from research.phase6.queue_aware_quote_lab import propose
from research.phase6.tests import test_depth_quote_lab as fixture_module


class QueueAwareQuoteTest(unittest.TestCase):
    def fixture(self):
        w,c=fixture_module.DepthQuoteLabTest().fixture();c['queueMultiplier']='2';return w,c

    def test_structural_reserve_no_quantity_increase_and_deterministic_tie(self):
        w,c=self.fixture();r=propose(w,c)
        self.assertEqual(r['requiredEdge'],D('.04'));self.assertEqual(r['thinPremiumReserve'],D('.01'))
        self.assertEqual(r['quantity'],D(5));self.assertEqual((r['firstBid'],r['secondBid']),(D('.48'),D('.47')))
        self.assertEqual(r,propose(w,c));self.assertGreaterEqual(r['netEdgeTotal'],r['requiredEdge']*r['quantity'])
        self.assertFalse(r['queuePriorityOrFillProven'])

    def test_queue_objective_precedes_price_and_minimum_participation_retained(self):
        w,c=self.fixture()
        for b in [w['firstBook'],w['secondBook']]:
            b['bids'][1]['size']='80';b['bids'][2]['size']='50'
        r=propose(w,c);self.assertEqual((r['firstBid'],r['secondBid']),(D('.47'),D('.47')))
        self.assertEqual(r['firstDisplayedQueueProxy'],100);self.assertEqual(r['secondDisplayedQueueProxy'],100)
        w['firstBook']['bids'][2]['size']='49.99'
        self.assertNotEqual(propose(w,c)['firstBid'],D('.47'))

    def test_original_size_risk_and_source_guards_never_relaxed(self):
        w,c=self.fixture();w['quantity']='.5';w['firstBook']['bids'][0]['size']='5'
        self.assertIsNone(propose(w,c))
        for changes in [dict(exitLossAvailable='2'),dict(openOrderIds=['resting']),dict(availableCash='1')]:
            w,c=self.fixture();w.update(changes);self.assertIsNone(propose(w,c))
        w,c=self.fixture();w['firstBook']['sourceMs']=-2000;self.assertIsNone(propose(w,c))

    def test_buffer_cannot_be_lowered_by_deep_depth_and_no_future_input_mutation(self):
        w,c=self.fixture();before=copy.deepcopy(w)
        self.assertEqual(propose(w,c)['thinPremiumReserve'],D('.01'));self.assertEqual(w,before)
        for b in [w['firstBook'],w['secondBook']]:b['bids'][2]['size']='100000'
        self.assertEqual(propose(w,c)['thinPremiumReserve'],D('.01'))
        c['queueMultiplier']='.5'
        with self.assertRaisesRegex(ValueError,'relax'):propose(w,c)


if __name__=='__main__':unittest.main()
