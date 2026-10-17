"""Per-venue CEX signal ablation with known causal provenance."""
from pathlib import Path
import sys
import unittest
from decimal import Decimal as D

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from research.phase5.cex_signals import SignalState, parse_sample
from research.phase3.polybot_sdk.features import fingerprint

START=1800000000000

def public(venue='binance-spot',n=5,at=START,delay=100,side=True,price_step=1):
    payload=[]
    for i in range(n):
        rec={'a':i+1,'p':str(100+i*price_step),'q':'1','T':at+i*10}
        if side:
            rec['m']=False
        payload.append(rec)
    if venue=='bybit-spot':
        payload={'retCode':0,'result':{'category':'spot','list':[
            {'execId':str(i+1),'symbol':'BTCUSDT','price':str(100+i*price_step),
             'size':'1','time':str(at+i*10),**({'side':'Buy'} if side else {})}
            for i in range(n)]}}
    return {'venue':venue,'symbol':'BTCUSDT','polledMs':at+delay,
            'receivedMs':at+delay,'status':'SAMPLED_PUBLIC_TRADES',
            'payload':payload,'payloadSha256':fingerprint(payload)}

class CexSignalTest(unittest.TestCase):
    def test_momentum_and_flow_are_independent_research_signals(self):
        result=SignalState(lookback=5,min_bps=10).event(public())
        self.assertEqual(result['status'],'RESEARCH_SIGNALS_UNQUALIFIED')
        self.assertEqual(result['momentumDirection'],'UP')
        self.assertEqual(result['aggressiveFlow'],'BUY')
        self.assertFalse(result['predictionQualified'])
        self.assertFalse(result['executionEnabled'])

    def test_bybit_uses_own_recorded_side_not_binance_proxy(self):
        result=SignalState(lookback=5,min_bps=10).event(public('bybit-spot',price_step=-1))
        self.assertEqual(result['momentumDirection'],'DOWN')
        self.assertEqual(result['aggressiveFlow'],'BUY')
        self.assertFalse(result['fillEvidence'])

    def test_unavailable_side_abstains_only_flow(self):
        result=SignalState().event(public(side=False))
        self.assertEqual(result['status'],'RESEARCH_SIGNALS_UNQUALIFIED')
        self.assertEqual(result['aggressiveFlow'],'ABSTAIN_MISSING_SIDE')

    def test_future_trade_or_corrupted_payload_rejected(self):
        row=public()
        row['receivedMs']=START-1
        with self.assertRaisesRegex(ValueError,'receipt|time'):
            SignalState().event(row)
        row=public()
        row['payload'][0]['p']='50000'
        with self.assertRaisesRegex(ValueError,'Unverifiable'):
            SignalState().event(row)

    def test_stale_and_source_gap_never_preserve_signal(self):
        state=SignalState()
        self.assertEqual(state.event(public())['status'],'RESEARCH_SIGNALS_UNQUALIFIED')
        gap={'status':'HTTP_BACKOFF','polledMs':START+300,'venue':'binance-spot','symbol':'BTCUSDT'}
        self.assertEqual(state.event(gap)['status'],'ABSTAIN_SOURCE_GAP')
        tiny=public(n=1,at=START+400)
        self.assertEqual(state.event(tiny)['status'],'ABSTAIN_INSUFFICIENT_PRINTS')
        stale=public(at=START-5000,delay=5100)
        state2=SignalState()
        self.assertEqual(state2.event(stale)['status'],'ABSTAIN_STALE_SOURCE')

    def test_repeated_poll_does_not_produce_lookahead_prints(self):
        row=public(n=3)
        state=SignalState()
        self.assertEqual(state.event(row)['status'],'ABSTAIN_INSUFFICIENT_PRINTS')
        self.assertEqual(state.event(dict(row,polledMs=START+200,receivedMs=START+200))['status'],
                         'ABSTAIN_INSUFFICIENT_PRINTS')

    def test_bybit_unknown_side_does_not_invent_trade_aggressor(self):
        result=SignalState().event(public('bybit-spot',side=False))
        self.assertEqual(result['aggressiveFlow'],'ABSTAIN_MISSING_SIDE')

if __name__=='__main__':
    unittest.main()
