"""Event scenario routes through the existing review/risk system, never LIVE."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'research'/'phase3'/'tests'))
from test_research import fixture, BASE
from research.phase5.paper_strategy_adapter import event_proposal, cex_signal_to_event_probability
from research.phase6.external_strategy import ExternalStrategyReview


def event(category='politics'):
    e={'marketId':'gamma-1','conditionId':'0x'+'a'*64,'category':category,
       'openMs':BASE-10000,'closeMs':BASE+900000,
       'marketReceivedMs':BASE-100,'resolutionRisk':False,
       'negativeRisk':False,'assumedFeeBps':'10','assumedSlippageBps':'10',
       'outcomes':[{'id':'a','bestAsk':'.60','forecastProbability':'.80',
                    'forecastReceivedMs':BASE-100},
                   {'id':'b','bestAsk':'.60','forecastProbability':'.20',
                    'forecastReceivedMs':BASE-100}]}
    if category=='politics':
        e.update(resolutionStatus='UNDISPUTED_OPEN',resolutionRulesObserved=True)
    else:
        e.update(sportsStatus='SCHEDULED',scheduledStartMs=BASE+50000)
    return e


def snapshot():
    snap=fixture()
    snap['markets'][0]['condition']='0x'+'a'*64
    return snap


class PaperEventAdapterTest(unittest.TestCase):
    def test_binary_politics_scenario_still_submits_no_orders(self):
        obs=snapshot()
        result=event_proposal(obs,event(),at_ms=BASE)
        self.assertEqual(result['status'],'PAPER_SCENARIO_ONLY')
        envelope=result['envelope']
        self.assertEqual(len(envelope['proposals']),1)
        self.assertEqual(envelope['proposals'][0]['legs'][0]['token'],'a')
        self.assertEqual(ExternalStrategyReview().review(
            obs,envelope,at_ms=BASE)['admittedResearchCandidates'],1)
        self.assertFalse(result['settlementIndependentlyVerified'])
        self.assertFalse(result['liveAllowed'])

    def test_sports_stale_score_or_terminal_blocks_scenario(self):
        obs=snapshot()
        e=event('sports')
        e.update(sportsStatus='LIVE',isInPlay=True,scoreReceivedMs=BASE-9000)
        self.assertIn('SPORTS_SCORE_STALE',event_proposal(obs,e,at_ms=BASE)['reason'])
        e.update(sportsStatus='FINAL')
        self.assertIn('SPORTS_TERMINAL',event_proposal(obs,e,at_ms=BASE)['reason'])

    def test_cannot_turn_multioutcome_or_negative_risk_into_binary_orders(self):
        e=event()
        e['negativeRisk']=True
        self.assertIn('NEGATIVE_RISK',event_proposal(snapshot(),e,at_ms=BASE)['reason'])
        e['negativeRisk']=False
        e['outcomes'].append({'id':'third','bestAsk':'.1','forecastProbability':'.0',
                             'forecastReceivedMs':BASE-100})
        self.assertIn('MULTI_OUTCOME',event_proposal(snapshot(),e,at_ms=BASE)['reason'])

    def test_outcome_mismatch_or_unknown_condition_abstains(self):
        e=event()
        e['outcomes'][1]['id']='forged'
        self.assertEqual(event_proposal(snapshot(),e,at_ms=BASE)['reason'],
                         'UNVERIFIED_BINARY_OUTCOME_MEMBERSHIP')
        e=event()
        e['conditionId']='0x'+'b'*64
        self.assertEqual(event_proposal(snapshot(),e,at_ms=BASE)['reason'],
                         'NO_EXACT_JAVA_CONDITION')

    def test_stale_book_no_passive_price_and_high_threshold_abstain(self):
        obs=snapshot()
        obs['books']['a']['bids'][0]['price']='.59'
        self.assertEqual(event_proposal(obs,event(),at_ms=BASE)['reason'],
                         'NO_CAUSAL_PASSIVE_CANDIDATE')
        self.assertEqual(event_proposal(snapshot(),event(),at_ms=BASE,
                        minimum_edge='.9')['reason'],'NO_CAUSAL_PASSIVE_CANDIDATE')

    def test_cex_trend_is_not_outcome_probability(self):
        output=cex_signal_to_event_probability({'momentumDirection':'UP'})
        self.assertIsNone(output['conditionalOutcomeProbability'])
        self.assertEqual(output['status'],'ABSTAIN')
        self.assertFalse(output['paperOrdersEnabled'])

if __name__=='__main__':
    unittest.main()
