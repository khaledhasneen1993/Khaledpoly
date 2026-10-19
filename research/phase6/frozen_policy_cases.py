"""Same immutable DEVELOPMENT witnesses and synthetic guards, no strategy performance trial."""
import argparse
import copy
from decimal import Decimal as D
import json
from pathlib import Path
from research.phase6.entry_witness_result import load
from research.phase6.queue_aware_quote_lab import propose
from research.phase6.tests.test_depth_quote_lab import DepthQuoteLabTest


def prepare():
    cfg=json.loads(Path('research/phase2/research-config.json').read_text())
    witnesses=json.loads(load()['report.json'],parse_float=D)['entryDecisionWitnesses']
    if len(witnesses)!=34:raise ValueError('Require unchanged34 development witnesses')
    cases=[dict(kind='ORIGINAL_DEVELOPMENT_WITNESS',witness=w,config=cfg,expected=propose(w,cfg)) for w in witnesses]
    w,c=DepthQuoteLabTest().fixture();c={**cfg,**c};c['queueMultiplier']='2'
    for mutation in ['base','queue_objective','small','loss_cap','stale','pending','cash','thin_level']:
        x=copy.deepcopy(w)
        if mutation=='queue_objective':
            for b in [x['firstBook'],x['secondBook']]:b['bids'][1]['size']='80';b['bids'][2]['size']='50'
        elif mutation=='small':x['quantity']='.5';x['firstBook']['bids'][0]['size']='5'
        elif mutation=='loss_cap':x['exitLossAvailable']='2'
        elif mutation=='stale':x['firstBook']['sourceMs']=-2000
        elif mutation=='pending':x['openOrderIds']=['resting']
        elif mutation=='cash':x['availableCash']='1'
        elif mutation=='thin_level':x['firstBook']['bids'][2]['size']='49.99'
        cases.append(dict(kind='SYNTHETIC_'+mutation,witness=x,config=c,expected=propose(x,c)))
    exits=[]
    for overdue in [False,True]:
        for ask in ['.48','.49','.51']:
            for bid in ['.49','.50','.51']:
                basis=D('.48');buy=D('.01949');sell=D('.01749');minimum=D('.01')
                complete=1-basis-D(ask)-buy;value=D(bid)-basis-sell
                action=('COMPLETE' if complete>=minimum and complete>=value else ('RISK_COMPLETE' if complete>=value else 'RISK_SELL') if overdue else 'WAIT')
                if not overdue and max(complete,value)>=minimum:action='COMPLETE' if complete>=value else 'TAKER_SELL'
                exits.append(dict(basis=basis,ask=ask,bid=bid,buyFee=buy,sellFee=sell,minimum=minimum,overdue=overdue,
                    expected=dict(action=action,completeValue=complete,sellValue=value)))
    return dict(scope='FROZEN_RULE_PARITY_NOT_ACCOUNT',quotes=cases,exits=exits,marketFillsCreated=0,netPnlRecomputed=False,liveAllowed=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();r=prepare();path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(r,indent=2,default=str)+'\n')
