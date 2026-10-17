"""Strict PAPER-only event scenario -> external strategy envelope adapter.

Versioned research inputs remain unverified probabilities. No other-venue CEX
trend may be silently translated into a Polymarket outcome probability.
Multi-outcome/negative-risk flows have no proven Java binary admission route:
they ABSTAIN rather than being treated as two-outcome orders.
"""
from decimal import Decimal
import re

from research.phase3.polybot_sdk.model import number, integer, validate
from research.phase5.event_rules import screen


def event_proposal(snapshot, event, *, at_ms=None, minimum_edge='0.015',
                   strategy_id='event-research'):
    snap=validate(snapshot,at_ms)
    now=integer(snap['generatedMs'])
    min_edge=number(minimum_edge)
    if not 0 < min_edge < 1 or not re.fullmatch(r'[a-z0-9-]{1,64}',strategy_id):
        raise ValueError('Invalid fixed strategy research threshold')
    base={'schema':1,'scope':'PHASE5_UNQUALIFIED_EVENT_PAPER_ADAPTER',
          'status':'ABSTAIN','reason':None,
          'eventCategory':event.get('category') if isinstance(event,dict) else None,
          'strategyId':strategy_id,'snapshotSequence':integer(snap['sequence']),
          'snapshotSessionId':snap['sessionId'],'envelope':None,
          'CEXCrossVenueOutcomeMappingVerified':False,
          'forecastCalibrated':False,'venueFillsObserved':False,
          'settlementIndependentlyVerified':False,'liveAllowed':False,
          'executionEnabled':False,'decision':'NO_GO'}
    def reject(reason):
        base['reason']=reason
        return base
    if not isinstance(event,dict):
        return reject('INVALID_EVENT')
    if event.get('negativeRisk') is True:
        return reject('NEGATIVE_RISK_BINARY_JAVA_ADMISSION_UNSUPPORTED')
    if not isinstance(event.get('outcomes'),list) or len(event['outcomes'])!=2:
        return reject('MULTI_OUTCOME_BINARY_JAVA_ADMISSION_UNSUPPORTED')
    conditional=screen(event,now)
    if conditional['status']!='RESEARCH_SCREEN_ONLY':
        return reject('CATEGORY_RULE_'+str(conditional['reason']))
    matches=[m for m in snap['markets'] if m['condition']==event['conditionId']]
    if len(matches)!=1:
        return reject('NO_EXACT_JAVA_CONDITION')
    market=matches[0]
    if market.get('negativeRisk') is True:
        return reject('NEGATIVE_RISK_BINARY_JAVA_ADMISSION_UNSUPPORTED')
    if integer(market['endMs'])!=integer(event['closeMs']):
        return reject('INCONSISTENT_RESOLUTION_TIME')
    ids={x['id'] for x in event['outcomes']}
    if ids!={market['first'],market['second']}:
        return reject('UNVERIFIED_BINARY_OUTCOME_MEMBERSHIP')
    # Never compare a real CEX short-term price signal with a Polymarket
    # Politics/Sports outcome without a verified explicit prediction model.
    rows=[]
    for scenario in conditional['scenarioEdges']:
        token=scenario['outcomeId']
        book=snap['books'].get(token)
        if not market['accepting'] or book is None or book['depthTruncated']:
            continue
        if not book['bids'] or not book['asks']:
            continue
        if now-integer(book['sourceMs'])>=integer(snap['maxBookAgeMs']):
            continue
        tick=number(market['tick'])
        price=number(book['bids'][0]['price'])+tick
        if price>=number(book['asks'][0]['price']) or not 0<price<1:
            continue
        edge=(number(scenario['assumedProbability'])-price
              -price*(number(event['assumedFeeBps'])+number(event['assumedSlippageBps']))/10000
              -Decimal('.02'))
        if edge<min_edge:
            continue
        expiry=min(now+250,integer(book['sourceMs'])+integer(snap['maxBookAgeMs']),
                   integer(market['endMs']))
        if expiry<=now:
            continue
        rows.append((edge,token,{'condition':market['condition'],'token':token,
                                 'buy':True,'price':str(price),
                                 'size':str(number(market['minSize'])),
                                 'expiresMs':expiry}))
    if not rows:
        return reject('NO_CAUSAL_PASSIVE_CANDIDATE')
    # The central allocator and Java PAPER ledger still make all final
    # decisions. Highest unverified scenario edge is only a toy heuristic.
    edge,token,leg=sorted(rows,key=lambda row:(-row[0],row[1]))[0]
    envelope={'schema':1,'version':'1.0','strategyId':strategy_id,
              'sessionId':snap['sessionId'],'accountId':snap['account']['id'],
              'snapshotSequence':integer(snap['sequence']),'observedMs':now,
              'proposals':[{'id':strategy_id+':'+token,
                            'edge':str(edge),'legs':[leg]}]}
    base.update(status='PAPER_SCENARIO_ONLY',reason='UNVERIFIED_INPUT_PROBABILITY',
                envelope=envelope)
    return base


def cex_signal_to_event_probability(signal):
    """No implicit venue->event mapping. A dedicated verified model is needed."""
    return {'schema':1,'scope':'PHASE5_CEX_TO_EVENT_LINK',
            'status':'ABSTAIN','reason':'NO_INDEPENDENT_CEX_TO_EVENT_FORECAST_MODEL',
            'sourceVerified':False,'conditionalOutcomeProbability':None,
            'paperOrdersEnabled':False,'liveAllowed':False,'decision':'NO_GO'}
