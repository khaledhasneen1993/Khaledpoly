import copy
import unittest
from decimal import Decimal as D
from research.phase6.depth_quote_lab import propose


class DepthQuoteLabTest(unittest.TestCase):
    def fixture(self):
        cfg=dict(orderShares='5',mergeCost='.01',redemptionCost='.01',portfolioBudget='100',maxBookAgeMs=2000,metadataMaxAgeMs=60000)
        book=dict(sourceMs=1000,bids=[dict(price='.49',size='100'),dict(price='.48',size='100'),dict(price='.47',size='100')],asks=[dict(price='.51',size='100')])
        w=dict(at=1000,quantity='5',market=dict(startMs=0,endMs=10000,observedMs=1000,minSize='5',tick='.01',accepting=True),
            firstBook=copy.deepcopy(book),secondBook=copy.deepcopy(book),requiredEdge='.03',exitLossAvailable='2.5',
            entryStopped=False,ledgerHalted=False,resolved=False,openOrderIds=[],imbalance=0,
            lastFirstTakerSource=None,lastSecondTakerSource=None,availableCash='500',gross=0)
        return w,cfg

    def test_maximum_combined_displayed_price_preserves_all_budgets(self):
        w,c=self.fixture();r=propose(w,c)
        self.assertEqual(r['quantity'],D('5'));self.assertEqual(r['firstBid']+r['secondBid'],D('.96'))
        self.assertGreaterEqual(r['netEdgeTotal'],r['quantity']*r['requiredEdge'])
        self.assertLessEqual(r['worstUnpairedLoss'],D('2.5'))
        self.assertFalse(r['queuePriorityOrFillProven'])
        self.assertEqual(r,propose(w,c))

    def test_no_increased_size_or_lowered_dynamic_threshold(self):
        w,c=self.fixture();w['quantity']='.5';w['firstBook']['bids'][0]['size']='5'
        self.assertIsNone(propose(w,c))
        w,c=self.fixture();w['requiredEdge']='.1';self.assertIsNone(propose(w,c))
        w,c=self.fixture();w['exitLossAvailable']='2';self.assertIsNone(propose(w,c))
        w,c=self.fixture();w['firstBook']['bids'][0]['size']='60';w['quantity']='6'
        with self.assertRaisesRegex(ValueError,'increase'):propose(w,c)

    def test_actual_quote_depth_and_freshness_are_required(self):
        w,c=self.fixture();w['firstBook']=None;self.assertIsNone(propose(w,c))
        w,c=self.fixture();w['firstBook']['sourceMs']=-2000;self.assertIsNone(propose(w,c))
        w,c=self.fixture();w['openOrderIds']=['resting'];self.assertIsNone(propose(w,c))
        w,c=self.fixture()
        for b in (w['firstBook'],w['secondBook']):
            b['bids'][1]['size']='1';b['bids'][2]['size']='1'
        self.assertIsNone(propose(w,c))


if __name__=='__main__':unittest.main()
