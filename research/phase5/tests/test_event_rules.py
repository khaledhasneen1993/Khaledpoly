"""Politics, Sports, news, and partial multi-outcome abstentions."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from research.phase5.event_rules import screen

NOW=1800000000000
def base(category='politics'):
    market={'marketId':'a','conditionId':'0x'+'a'*64,'category':category,
            'openMs':NOW-100000,'closeMs':NOW+200000,
            'marketReceivedMs':NOW-500,'resolutionRisk':False,
            'negativeRisk':False,'assumedFeeBps':'100','assumedSlippageBps':'10',
            'outcomes':[{'id':'yes','bestAsk':'.55','forecastProbability':'.65',
                         'forecastReceivedMs':NOW-1000},
                        {'id':'no','bestAsk':'.42','forecastProbability':'.35',
                         'forecastReceivedMs':NOW-1000}]}
    if category=='politics':
        market.update(resolutionStatus='UNDISPUTED_OPEN',resolutionRulesObserved=True)
    else:
        market.update(sportsStatus='SCHEDULED',scheduledStartMs=NOW+100000)
    return market

class EventScreenTest(unittest.TestCase):
    def test_politics_scenario_is_unqualified_even_with_positive_edge(self):
        out=screen(base(),NOW)
        self.assertEqual(out['status'],'RESEARCH_SCREEN_ONLY')
        self.assertTrue(out['scenarioEdges'][0]['scenarioPositive'])
        self.assertFalse(out['oracleIndependentlyVerified'])
        self.assertFalse(out['probabilityCalibrated'])
        self.assertFalse(out['executionEnabled'])
        self.assertEqual(out['decision'],'NO_GO')

    def test_sports_stale_score_and_terminal_status_abstain(self):
        event=base('sports')
        event.update(sportsStatus='LIVE',isInPlay=True,scoreReceivedMs=NOW-7000)
        self.assertEqual(screen(event,NOW)['reason'],'SPORTS_SCORE_STALE')
        event['sportsStatus']='FINAL'
        self.assertEqual(screen(event,NOW)['reason'],'SPORTS_TERMINAL_OR_STATUS_UNKNOWN')

    def test_negative_risk_and_multi_outcome_not_falsely_completed(self):
        event=base()
        event['negativeRisk']=True
        self.assertEqual(screen(event,NOW)['reason'],'NEGATIVE_RISK_MEMBERSHIP_UNVERIFIED')
        event.update(negativeRiskGroupComplete=True)
        event['outcomes']=[{'id':str(i),'bestAsk':'.32','forecastProbability':str(1/3),
                            'forecastReceivedMs':NOW-100} for i in range(3)]
        self.assertEqual(screen(event,NOW)['reason'],'MULTI_OUTCOME_MEMBERSHIP_UNVERIFIED')
        event['outcomeUniverseComplete']=True
        self.assertEqual(screen(event,NOW)['status'],'RESEARCH_SCREEN_ONLY')

    def test_news_future_clock_dispute_and_missing_cost_abstain(self):
        event=base()
        event['news']={'eventMatched':True,'publishedMs':NOW+1,'receivedMs':NOW+1}
        self.assertEqual(screen(event,NOW)['reason'],'NEWS_UNAVAILABLE_OR_STALE')
        event['news']=None
        event['resolutionRisk']=True
        self.assertEqual(screen(event,NOW)['reason'],'UNKNOWN_OR_DISPUTED_RESOLUTION')
        event['resolutionRisk']=False
        del event['assumedFeeBps']
        self.assertEqual(screen(event,NOW)['reason'],'SCENARIO_COST_MISSING')

    def test_inconsistent_probability_or_duplicate_market_outcome_fails(self):
        event=base()
        event['outcomes'][1]['forecastProbability']='.45'
        self.assertEqual(screen(event,NOW)['reason'],'INCOHERENT_PROBABILITIES')
        event['outcomes'][1]['forecastProbability']='.35'
        event['outcomes'][1]['id']='yes'
        self.assertEqual(screen(event,NOW)['reason'],'DUPLICATE_OUTCOME_IDENTITY')

if __name__=='__main__':
    unittest.main()
