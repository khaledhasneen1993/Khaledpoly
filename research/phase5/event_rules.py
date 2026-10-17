"""Category-aware hypothetical event fair-value screen, never an order.

Input probabilities, fees, sports scores and Politics settlement flags are
claims needing independent verification. Missing/stale/ambiguous inputs ABSTAIN.
"""
import argparse
import hashlib
from decimal import Decimal
from pathlib import Path
import re

from research.phase3.polybot_sdk.model import decode, dumps, integer, number
from research.phase3.polybot_sdk.runtime import private_write


def screen(market, decision_ms, uncertainty_margin='0.02'):
    now = integer(decision_ms)
    margin = number(uncertainty_margin)
    if not 0 < margin < 1:
        raise ValueError('Invalid uncertainty buffer')
    result = {'schema':1,'scope':'UNVERIFIED_CATEGORY_EVENT_RESEARCH',
              'decisionMs':now,'status':'ABSTAIN','reason':None,'scenarioEdges':[],
              'probabilityCalibrated':False,'oracleIndependentlyVerified':False,
              'newsImpactVerified':False,'venueFillVerified':False,
              'riskApproved':False,'executionEnabled':False,'liveAllowed':False}
    def abstain(reason):
        result['reason']=reason
        return result
    if not isinstance(market, dict) or market.get('category') not in ('politics','sports'):
        return abstain('UNSUPPORTED_CATEGORY')
    if not isinstance(market.get('marketId'),str) or not market['marketId'].strip():
        return abstain('MISSING_MARKET_ID')
    condition=market.get('conditionId')
    if not isinstance(condition,str) or not re.fullmatch(r'0x[0-9a-fA-F]{64}',condition):
        return abstain('AMBIGUOUS_CONDITION')
    try:
        recorded=integer(market['marketReceivedMs'])
        opened=integer(market['openMs'])
        closes=integer(market['closeMs'])
    except (ValueError,KeyError,TypeError):
        return abstain('MISSING_CAUSAL_MARKET_TIMES')
    if not 0 < opened <= recorded <= now < closes or now-recorded > 60000:
        return abstain('CLOSED_OR_STALE_MARKET')
    if market.get('resolutionRisk') is not False:
        return abstain('UNKNOWN_OR_DISPUTED_RESOLUTION')
    if market.get('negativeRisk') is True and market.get('negativeRiskGroupComplete') is not True:
        return abstain('NEGATIVE_RISK_MEMBERSHIP_UNVERIFIED')
    if market.get('category') == 'politics':
        if market.get('resolutionStatus') != 'UNDISPUTED_OPEN':
            return abstain('POLITICS_ORACLE_OR_DISPUTE_UNCLEAR')
        if market.get('resolutionRulesObserved') is not True:
            return abstain('POLITICS_RESOLUTION_RULES_MISSING')
    else:
        status=market.get('sportsStatus')
        if status == 'SCHEDULED':
            try:
                starts=integer(market['scheduledStartMs'])
            except (KeyError,TypeError,ValueError):
                return abstain('SPORTS_SCHEDULE_UNKNOWN')
            if not now < starts <= closes:
                return abstain('SPORTS_SCHEDULE_INCONSISTENT')
        elif status == 'LIVE':
            if market.get('isInPlay') is not True:
                return abstain('SPORTS_IN_PLAY_UNCONFIRMED')
            try:
                score_at=integer(market['scoreReceivedMs'])
            except (KeyError,TypeError,ValueError):
                return abstain('SPORTS_SCORE_UNKNOWN')
            if score_at>now or now-score_at>2000 or score_at<opened:
                return abstain('SPORTS_SCORE_STALE')
        else:
            return abstain('SPORTS_TERMINAL_OR_STATUS_UNKNOWN')
    news=market.get('news')
    if news is not None:
        if not isinstance(news,dict) or news.get('eventMatched') is not True:
            return abstain('NEWS_ENTITY_NOT_MATCHED')
        try:
            published=integer(news['publishedMs'])
            available=integer(news['receivedMs'])
        except (KeyError,ValueError,TypeError):
            return abstain('NEWS_CAUSAL_CLOCK_UNKNOWN')
        if not 0 < published <= available <= now or now-available>300000:
            return abstain('NEWS_UNAVAILABLE_OR_STALE')

    outcomes=market.get('outcomes')
    if not isinstance(outcomes,list) or not 2<=len(outcomes)<=256:
        return abstain('UNKNOWN_OUTCOME_UNIVERSE')
    if len(outcomes)>2 and market.get('outcomeUniverseComplete') is not True:
        return abstain('MULTI_OUTCOME_MEMBERSHIP_UNVERIFIED')
    try:
        fees=number(market['assumedFeeBps'])
        slip=number(market['assumedSlippageBps'])
        if not 0<=fees<=10000 or not 0<=slip<=10000:
            return abstain('INVALID_SCENARIO_COST')
    except (KeyError,ValueError,TypeError):
        return abstain('SCENARIO_COST_MISSING')
    seen=set()
    assumptions=[]
    total=Decimal(0)
    for outcome in outcomes:
        if not isinstance(outcome,dict) or not isinstance(outcome.get('id'),str) or not outcome['id']:
            return abstain('MISSING_OUTCOME_IDENTITY')
        if outcome['id'] in seen:
            return abstain('DUPLICATE_OUTCOME_IDENTITY')
        seen.add(outcome['id'])
        try:
            px=number(outcome['bestAsk'])
            prob=number(outcome['forecastProbability'])
            available=integer(outcome['forecastReceivedMs'])
        except (KeyError,ValueError,TypeError):
            return abstain('INVALID_FORECAST_OR_ASK')
        if not 0<px<1 or not 0<=prob<=1 or available>now or available<opened or now-available>5000:
            return abstain('FORECAST_NOT_AVAILABLE_AT_DECISION')
        assumptions.append((outcome['id'],px,prob))
        total+=prob
    if abs(total-1)>Decimal('.005'):
        return abstain('INCOHERENT_PROBABILITIES')
    scenario=[]
    for identity,px,prob in assumptions:
        edge=prob-px-px*(fees+slip)/10000-margin
        scenario.append({'outcomeId':identity,'assumedProbability':str(prob),
                         'quotedAsk':str(px),'scenarioNetEdgePerShareUsd':str(edge),
                         'scenarioPositive':edge>0})
    result.update({'status':'RESEARCH_SCREEN_ONLY','reason':'UNVERIFIED_PROBABILITIES_AND_FILL',
                   'scenarioEdges':scenario,'decision':'NO_GO'})
    return result


def main():
    p=argparse.ArgumentParser(description='Offline Politics/Sports and multi-outcome scenario screen')
    p.add_argument('record',help='Single explicitly captured event/forecast JSON')
    p.add_argument('--decision-ms',type=int,required=True)
    p.add_argument('--output',required=True)
    opt=p.parse_args()
    data=decode(Path(opt.record).read_text(encoding='utf-8'))
    result=screen(data,opt.decision_ms)
    result['inputSha256']=hashlib.sha256(dumps(data).encode()).hexdigest()
    private_write(opt.output,result)
    print(dumps(result))


if __name__=='__main__':
    main()
