"""Strict future-time CEX price observations, no assumed maker fills."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from research.phase5.cex_forward import forward_test
from research.phase3.polybot_sdk.features import fingerprint

T=1800000000000
def spot(at,ids,price,venue='binance-spot'):
    payload=[{'a':n,'p':str(price+n),'q':'1','T':at+n*10,'m':False} for n in ids]
    if venue=='bybit-spot':
        payload={'retCode':0,'result':{'category':'spot','list':[
            {'execId':str(n),'price':str(price+n),'size':'1','time':str(at+n*10),
             'symbol':'BTCUSDT','side':'Sell'} for n in ids]}}
    return {'status':'SAMPLED_PUBLIC_TRADES','venue':venue,'symbol':'BTCUSDT',
            'polledMs':at+100,'receivedMs':at+100,
            'payload':payload,'payloadSha256':fingerprint(payload)}

class CexForwardTest(unittest.TestCase):
    def test_forward_print_can_label_direction_not_fill(self):
        # Signal at T+100 from momentum UP/flow BUY, future observation at
        # T+2100 (after a 1000ms horizon) is available causally.
        one=spot(T,list(range(1,6)),100)
        two=spot(T+2000,list(range(10,15)),110)
        output=forward_test([one,two],horizon_ms=1000,max_label_delay_ms=2000,
                            fee_bps='1',slippage_bps='1',min_labeled=1)
        row=output['perVenueStrategy']['binance-spot/BTCUSDT/momentum']
        self.assertEqual(row['labeledNonoverlapping'],1)
        self.assertTrue(row['minimumHeldoutLabelsMet'])
        self.assertFalse(row['orderFillsObserved'])
        self.assertFalse(output['netTradeProfitabilityProven'])
        self.assertEqual(output['decision'],'NO_GO')

    def test_disconnect_censors_not_a_loss(self):
        one=spot(T,list(range(1,6)),100)
        failed={'venue':'binance-spot','symbol':'BTCUSDT','status':'HTTP_BACKOFF',
                'polledMs':T+1100}
        result=forward_test([one,failed],horizon_ms=1000,max_label_delay_ms=2000)
        row=result['perVenueStrategy']['binance-spot/BTCUSDT/momentum']
        self.assertEqual(row['labeledNonoverlapping'],0)
        self.assertEqual(row['censoredGap'],1)
        self.assertIsNone(row['meanAssumedNetBasisPoints'])

    def test_data_without_causal_future_print_is_censored(self):
        one=spot(T,list(range(1,6)),100)
        two=spot(T+5000,list(range(10,15)),110)
        result=forward_test([one,two],horizon_ms=1000,max_label_delay_ms=2000)
        row=result['perVenueStrategy']['binance-spot/BTCUSDT/momentum']
        self.assertEqual(row['labeledNonoverlapping'],0)
        self.assertEqual(row['censoredPrice'],1)

    def test_no_cross_venue_future_price_substitution(self):
        one=spot(T,list(range(1,6)),100)
        two=spot(T+2000,list(range(10,15)),110,venue='bybit-spot')
        result=forward_test([one,two],horizon_ms=1000,max_label_delay_ms=2000)
        self.assertEqual(result['perVenueStrategy']['binance-spot/BTCUSDT/momentum']['labeledNonoverlapping'],0)
        self.assertFalse(result['liveAllowed'])

if __name__=='__main__':
    unittest.main()
