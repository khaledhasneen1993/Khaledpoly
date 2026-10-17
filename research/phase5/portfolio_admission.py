"""Joint-scenario selection -> one atomic PAPER proposal; no independent-outcome assumption."""
import argparse
from decimal import Decimal as D
import hashlib
from pathlib import Path
from research.phase3.polybot_sdk.model import validate,number,dumps,decode
from research.phase3.polybot_sdk.advanced import allocate
from research.phase5.portfolio_optimizer import optimize
from research.phase6.external_strategy import ExternalStrategyReview
from research.phase3.polybot_sdk.runtime import private_write


def plan(snapshot,candidates,scenarios,groups,*,at_ms=None,group_cap='25',gross_cap='100',risk_cap='25',max_positions=4):
    snap=validate(snapshot,at_ms)
    if not isinstance(groups,dict) or not isinstance(scenarios,dict) or not 2<=len(scenarios)<=128:
        raise ValueError('Explicit aligned joint scenarios and correlation groups required')
    if not candidates or len(candidates)>12 or len({p['id'] for p in candidates})!=len(candidates):
        raise ValueError('Bounded unique candidate universe required')
    known={t:m['condition'] for m in snap['markets'] for t in (m['first'],m['second'])}
    if set(groups)!=set(known.values()) or any(not isinstance(v,str) or not v for v in groups.values()):
        raise ValueError('Every known market needs an explicit correlation group')
    basis={t:number(h['basis']) for t,h in snap['account']['holdings'].items()}
    for o in snap['account']['orders'].values():
        if o['buy']: basis[o['token']]=basis.get(o['token'],D(0))+number(o['price'])*number(o['remaining'])
    tokens=set(basis)
    normalized=[]
    for proposal in candidates:
        if not proposal['legs'] or any(leg['buy'] is not True for leg in proposal['legs']):
            raise ValueError('Optimizer handles new buy entries; central engine handles exits')
        conditions={leg['condition'] for leg in proposal['legs']}
        if len(conditions)!=1 or not conditions<=set(groups): raise ValueError('One market per candidate')
        tokens.update(leg['token'] for leg in proposal['legs'])
    if not tokens<=set(known): raise ValueError('Unclassified held or candidate token')
    for sid,returns in scenarios.items():
        if not isinstance(sid,str) or not sid or not isinstance(returns,dict) or set(returns)!=tokens:
            raise ValueError('Joint scenario must cover all existing and proposed exposure')
        if any(not -1<=number(v)<=10 for v in returns.values()): raise ValueError('Unbounded scenario return')
    existing_groups={}
    for token,value in basis.items():
        group=groups[known[token]]; existing_groups[group]=existing_groups.get(group,D(0))+value
    for proposal in candidates:
        cost=sum((number(l['price'])*number(l['size']) for l in proposal['legs']),D(0))
        normalized.append({'id':proposal['id'],'groupId':groups[proposal['legs'][0]['condition']],
            'acquisitionCostUsd':str(cost),'expectedNetPnlUsd':str(number(proposal['edge'])*min(number(l['size']) for l in proposal['legs'])),
            'pnlByScenarioUsd':{sid:str(sum((number(l['price'])*number(l['size'])*number(returns[l['token']]) for l in proposal['legs']),D(0))) for sid,returns in scenarios.items()},'provenance':'PAPER_SCENARIO'})
    budget=min(number(snap['account']['availableCash']),number(gross_cap)-sum(basis.values(),D(0)))
    if budget<0: raise ValueError('Existing gross exposure exceeds admission cap')
    selected=optimize(normalized,buying_power_usd=budget,group_cap_usd=min(number(group_cap),D(25)),maximum_joint_loss_usd=risk_cap,max_positions=max_positions,
        existing_group_exposure=existing_groups,existing_scenario_pnl={sid:sum((v*number(returns[t]) for t,v in basis.items()),D(0)) for sid,returns in scenarios.items()})
    chosen=[p for p in candidates if p['id'] in selected['selectedCandidateIds']]
    checked=allocate(snap,chosen,groups=groups,per_group=min(number(group_cap),D(25)),gross_limit=min(number(gross_cap),D(100)))
    envelope=None
    if chosen and len(checked['admitted'])==len(chosen):
        legs=[leg for p in chosen for leg in p['legs']]
        if len(legs)>16: raise ValueError('Selected portfolio exceeds atomic Java leg bound')
        weight=sum((min(number(l['size']) for l in p['legs']) for p in chosen),D(0))
        edge=sum((number(p['edge'])*min(number(l['size']) for l in p['legs']) for p in chosen),D(0))/weight
        identity=hashlib.sha256(dumps({'candidates':chosen,'scenarios':scenarios,'groups':groups}).encode()).hexdigest()[:40]
        envelope={'schema':1,'version':'1.0','strategyId':'joint-portfolio','sessionId':snap['sessionId'],'accountId':snap['account']['id'],
            'snapshotSequence':snap['sequence'],'observedMs':snap['generatedMs'],'proposals':[{'id':identity,'edge':str(edge),'legs':legs}]}
        reviewed=ExternalStrategyReview(per_group=min(number(group_cap),D(25)),gross_limit=min(number(gross_cap),D(100))).review(snap,envelope,at_ms=at_ms)
        if reviewed['admittedResearchCandidates']!=1: envelope=None
    return {'scope':'JOINT_SCENARIO_ATOMIC_PAPER_PORTFOLIO_PLAN','selection':selected,'envelope':envelope,'assumptionsSha256':hashlib.sha256(dumps(scenarios).encode()).hexdigest(),
        'existingPortfolioRiskIncluded':True,'jointScenariosIndependentlyVerified':False,'liveAllowed':False,'decision':'NO_GO'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--candidates',required=True);p.add_argument('--scenarios',required=True);p.add_argument('--groups',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();r=plan(*(decode(Path(getattr(a,k)).read_text()) for k in ('snapshot','candidates','scenarios','groups')));private_write(a.output,r);print(dumps(r))
if __name__=='__main__': main()
