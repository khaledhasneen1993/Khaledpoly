from decimal import Decimal as D
import unittest
from research.phase6.queue_aware_resting import policy


class RestingPolicyTest(unittest.TestCase):
    def setUp(self):
        self.book=dict(bids=[dict(price=D('.48'),size=D('100'))],asks=[dict(price=D('.55'),size=D('100'))])
        self.cfg=dict(minimumEdge='.01',mergeCost='.01',orderShares='5')
        self.market=dict(endMs=200000,tick=D('.01'),minSize=D('5'))

    def run_policy(self,prices,at=1000,vol=D(0)):
        return policy(self.book,self.book,vol,at,self.market,self.cfg,prices,D(5),0)

    def test_reserved_quantity_not_new_entry_size_and_net_cost(self):
        self.assertEqual(self.run_policy([D('.48'),D('.40')])['reason'],'RESTING')
        self.assertEqual(self.run_policy([D('.49'),D('.49')])['reason'],'RESTING_NET_EDGE')

    def test_invalid_maker_price_and_volatility_risk(self):
        self.assertEqual(self.run_policy([D('.55'),D('.40')])['reason'],'RESTING_PRICE_INVALID')
        self.assertEqual(self.run_policy([D('.48'),D('.40')],vol=D('.3'))['reason'],'RESTING_NET_EDGE')

    def test_no_unvalidated_or_early_reprice(self):
        self.book['bids'][0]['price']=D('.45')
        self.assertEqual(self.run_policy([D('.40'),D('.40')],at=1999)['reason'],'RESTING')
        self.assertEqual(self.run_policy([D('.40'),D('.40')],at=2000)['reason'],'REPRICE_VALIDATED_PAIR')


if __name__=='__main__':unittest.main()
