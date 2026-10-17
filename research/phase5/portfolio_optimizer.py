"""Exact small-universe correlated portfolio candidate optimizer (research only).

Optimize declared PAPER scenario expected value under *joint* worst-case
scenario risk, group concentration and cash. No fabricated probabilities,
fills, execution fee schedules or assumptions of independent positions.
"""
from decimal import Decimal

from research.phase3.polybot_sdk.model import number

MAX_CANDIDATES=12
MAX_SCENARIOS=128


def optimize(candidates, *, buying_power_usd, group_cap_usd,
             maximum_joint_loss_usd, max_positions=4,
             existing_group_exposure=None, existing_scenario_pnl=None):
    if (not isinstance(candidates,list) or not 1<=len(candidates)<=MAX_CANDIDATES
            or type(max_positions) is not int or not 1<=max_positions<=MAX_CANDIDATES):
        raise ValueError('Bounded hypothesis universe required')
    buying_power=number(buying_power_usd)
    group_cap=number(group_cap_usd)
    risk_cap=number(maximum_joint_loss_usd)
    if buying_power<0 or group_cap<=0 or risk_cap<=0:
        raise ValueError('Invalid budget or scenario risk caps')
    baseline=existing_group_exposure if existing_group_exposure is not None else {}
    if not isinstance(baseline,dict):
        raise ValueError('Invalid existing portfolio group inventory')
    group_basis={}
    for key,value in baseline.items():
        if not isinstance(key,str) or not key:
            raise ValueError('Missing correlated settlement group')
        exposure=number(value)
        if not 0<=exposure<=group_cap:
            raise ValueError('Existing group already violates admission cap')
        group_basis[key]=exposure

    source_ids=None
    normalized=[]
    known=set()
    for row in candidates:
        if not isinstance(row,dict) or set(row)!={'id','groupId','acquisitionCostUsd',
                                                 'expectedNetPnlUsd','pnlByScenarioUsd',
                                                 'provenance'}:
            raise ValueError('Undeclared portfolio optimizer input')
        identity,group=row['id'],row['groupId']
        if (not isinstance(identity,str) or not identity or len(identity)>128
                or identity in known or not isinstance(group,str) or not group or len(group)>128):
            raise ValueError('Invalid or duplicated opportunity identity')
        known.add(identity)
        if row['provenance']!='PAPER_SCENARIO':
            raise ValueError('Unverified live or mixed scenario source')
        cost=number(row['acquisitionCostUsd'])
        forecast=number(row['expectedNetPnlUsd'])
        if not 0<cost<=Decimal('1e12') or abs(forecast)>cost*Decimal(10):
            raise ValueError('Unbounded exposure or expected outcome')
        pnl=row['pnlByScenarioUsd']
        if not isinstance(pnl,dict) or not 2<=len(pnl)<=MAX_SCENARIOS:
            raise ValueError('Insufficient joint scenario evidence')
        if any(not isinstance(x,str) or not x for x in pnl):
            raise ValueError('Invalid scenario identity')
        if source_ids is None:
            source_ids=set(pnl)
        if set(pnl)!=source_ids:
            raise ValueError('Unaligned joint scenario vectors')
        cases={sid:number(value) for sid,value in pnl.items()}
        if any(value < -cost or value>cost*Decimal(10) for value in cases.values()):
            raise ValueError('Impossible or unbounded scenario net payoff')
        normalized.append({'id':identity,'group':group,'cost':cost,
                           'expected':forecast,'cases':cases})
    order=sorted(normalized,key=lambda row:row['id'])
    scenario_ids=sorted(source_ids)
    explored=0
    best_value=Decimal(0)
    best_ids=()
    best_loss=Decimal(0)
    best_cash=Decimal(0)
    if existing_scenario_pnl is not None and set(existing_scenario_pnl)!=set(scenario_ids):
        raise ValueError('Existing portfolio needs the same joint scenarios')
    initial_cases=tuple(number(existing_scenario_pnl[sid]) if existing_scenario_pnl is not None else Decimal(0) for sid in scenario_ids)
    if max(Decimal(0),-min(initial_cases))>risk_cap:
        raise ValueError('Existing portfolio already exceeds joint risk cap')

    def search(index,chosen,forecast,total_cost,groups,realized):
        nonlocal explored,best_ids,best_value,best_loss,best_cash
        if index==len(order):
            explored+=1
            worst=max(Decimal(0),-min(realized))
            if worst<=risk_cap:
                selection=tuple(sorted(chosen))
                if (forecast>best_value
                        or forecast==best_value and selection<best_ids):
                    best_value,best_ids,best_loss,best_cash=forecast,selection,worst,total_cost
            return
        # All admissible candidate subsets are enumerated; no fractional
        # optimization, unspecified correlations, or local-greedy selection.
        search(index+1,chosen,forecast,total_cost,groups,realized)
        item=order[index]
        if len(chosen)>=max_positions or total_cost+item['cost']>buying_power:
            return
        exposure=groups.get(item['group'],Decimal(0))+item['cost']
        if exposure>group_cap:
            return
        next_groups=dict(groups)
        next_groups[item['group']]=exposure
        updated=tuple(value+item['cases'][sid] for value,sid in zip(realized,scenario_ids))
        search(index+1,chosen+[item['id']],forecast+item['expected'],
               total_cost+item['cost'],next_groups,updated)
    best_loss=max(Decimal(0),-min(initial_cases))
    search(0,[],Decimal(0),Decimal(0),dict(group_basis),initial_cases)
    return {'schema':1,'scope':'PAPER_SCENARIO_EXACT_SMALL_PORTFOLIO_OPTIMIZER',
            'candidateCount':len(order),'evaluatedLeafSubsets':explored,
            'jointScenarioCount':len(scenario_ids),
            'selectedCandidateIds':list(best_ids),
            'assumedExpectedNetPnlUsd':str(best_value),
            'grossNewAcquisitionUsd':str(best_cash),
            'worstAssumedJointLossUsd':str(best_loss),
            'groupPolicy':'EXACT_CORRELATED_SETTLEMENT_GROUP',
            'optimizationExactForInputScenarios':True,
            'probabilitiesAndJointPayoffsIndependentlyVerified':False,
            'oracleTerminalOutcomesVerified':False,
            'strategyQualified':False,'ordersSubmitted':0,
            'liveAllowed':False,'decision':'NO_GO'}
