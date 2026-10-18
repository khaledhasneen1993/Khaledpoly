"""Frozen independent quote-state traffic UPPER BOUNDS, never orders or fills."""
import argparse
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
from research.phase3.polybot_sdk.tapes import open_tape


def collect(stream,selection,spec):
    states={s['id']:dict(selection=s,anchorSeen=False,terminalMs=s['endMs'],terminalReason='FIXED_UPPER_BOUND_CAP',observations=[]) for s in selection}
    if len(states)!=len(selection) or not 1<=len(states)<=20:raise ValueError('Require <=20 unique frozen quote states')
    for s in selection:
        if (len(s['quotes'])!=2 or len({q['token'] for q in s['quotes']})!=2
                or not 0<s['endMs']-s['submitMs']<=30000 or s['activationDueMs']!=s['submitMs']+spec['activationMs']):
            raise ValueError('Invalid bounded quote-state scope')
    digest=hashlib.sha256();seq=0;last=-1;run=None;ended=False;declared=False;pending=None;previous_frame=-1
    def cancel(at,data,reason,condition=None):
        scope=set(data.get('tokens',[]))
        if data.get('token'):scope.add(data['token'])
        for state in states.values():
            s=state['selection'];pair={q['token'] for q in s['quotes']}
            if (state['anchorSeen'] and at<state['terminalMs']
                    and (condition is None or condition==s['condition']) and (not scope or scope&pair)):
                state.update(terminalMs=at,terminalReason=reason)
    for line in stream:
        if len(line)>16*1024*1024 or not line.endswith(b'\n'):raise ValueError('Incomplete/oversized tape row')
        digest.update(line);row=json.loads(line);seq+=1;at=row['arrivalMs'];kind=row['kind'];data=row['data']
        if row['schema']!=1 or row['seq']!=seq or at<last or ended or run is not None and run!=row['runId']:
            raise ValueError('Wrong tape chronology/schema/run')
        run=row['runId'];last=at
        if kind=='DATASET_CONFIG':
            if declared or data.get('format')!='normalized-public-v2':raise ValueError('Require original framed recording')
            declared=True
        if kind=='RAW_MARKET':
            if pending is not None or data['frameId']<=previous_frame:raise ValueError('Wrong RAW boundary')
            pending=row
        elif kind=='RESEARCH_FRAME':
            if not declared or pending is None or data['frameId']!=pending['data']['frameId']:raise ValueError('Unbound normalized frame')
            previous_frame=data['frameId']
            for index,event in enumerate(data['events']):
                d=event['data']
                if event['kind']=='GAP':cancel(at,d,'ORIGINAL_GAP:'+d.get('reason','unknown'))
                if event['kind']!='TRADE':continue
                source=d['sourceMs']
                if not 0<=at-source<=spec['maxBookAgeMs']:continue
                for state in states.values():
                    s=state['selection']
                    if not(state['anchorSeen'] and s['activationDueMs']<=source<=at<state['terminalMs']):continue
                    for quote in s['quotes']:
                        direct=d['side']=='SELL' and d['token']==quote['token']
                        complement=d['side']=='BUY' and d['token'] in {q['token'] for q in s['quotes']} and d['token']!=quote['token']
                        if not(direct or complement):continue
                        sample=json.loads(d['tradeId']);original=json.loads(pending['data']['text'])
                        nodes=original if isinstance(original,list) else [original]
                        if (sample not in nodes or sample.get('event_type')!='last_trade_price'
                                or sample['asset_id']!=d['token'] or sample['side']!=d['side']
                                or int(sample['timestamp'])!=source or any(D(sample[k])!=D(str(d[k])) for k in ('price','size'))):
                            raise ValueError('Original public trade identity differs')
                        state['observations'].append(dict(normalizedSeq=seq,eventIndex=index,arrivalMs=at,
                            sample=sample,targetToken=quote['token'],targetBid=quote['price'],
                            publicPriceEqualsQuote=D(str(d['price']))==D(quote['price']),
                            classification='SAME_TOKEN_SELL_REQUIRES_RECEIPT_COMPONENT_PRICES' if direct else 'OPPOSITE_BUY_REQUIRES_RECEIPT_COMPONENT_PRICES'))
                        if len(state['observations'])>200:raise ValueError('Observation cap exceeded; never truncate')
            pending=None
        elif kind in ('RESEARCH_GAP','RESEARCH_FEED_ERROR'):cancel(at,data,kind)
        elif kind=='RESEARCH_RESOLUTION':cancel(at,{},'RESOLUTION',data['condition_id'])
        elif kind=='RESEARCH_MARKET_UNAVAILABLE' or kind=='RESEARCH_META' and not data.get('accepting',True):
            cancel(at,{},'MARKET_UNAVAILABLE',data['condition'])
        # Actual decisions can follow FRAME, META or another RESEARCH input.
        # Activate anchors only AFTER processing that whole source row.
        for state in states.values():
            s=state['selection']
            if seq==s['originalSequence']:
                if not kind.startswith('RESEARCH_') or at!=s['submitMs'] or state['anchorSeen']:
                    raise ValueError('Frozen decision anchor differs')
                state['anchorSeen']=True
        if kind=='RUN_END':
            ended=data.get('complete') is True
            if not ended:raise ValueError('Unclean recording')
    if not ended or pending is not None or not declared or seq!=spec['sourceRows'] or digest.hexdigest()!=spec['logicalTapeSha256']:
        raise ValueError('Wrong/incomplete original tape')
    if not all(s['anchorSeen'] for s in states.values()):raise ValueError('Missing frozen decision anchor')
    results=list(states.values());observations=[o for s in results for o in s['observations']]
    return dict(scope='SELECTED_DQ3_QUOTE_TRAFFIC_UPPER_BOUND_NOT_EXECUTION',sourceRows=seq,
        logicalTapeSha256=digest.hexdigest(),states=results,observationCount=len(observations),
        uniqueTransactionHashes=sorted({o['sample']['transaction_hash'] for o in observations if o['sample'].get('transaction_hash')}),
        activationIsRelaxedDueTimeUpperBoundNotObserved=True,actualQueueOrCandidateTrajectorySimulated=False,
        actualRestingEdgeCancellationOmitted=True,maxBookAgeAppliedToPrintOnly=True,
        fillsCreated=0,netPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False,
        decision='NO_GO_RECEIPT_ROUTE_AND_CAUSAL_QUEUE_NOT_PROVEN' if observations else 'REJECT_SELECTED_START_STATES_NO_NECESSARY_TRAFFIC')


def main():
    p=argparse.ArgumentParser();p.add_argument('--input-root',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    f=json.loads(Path('research/phase6/depth-quote-traffic-freeze.json').read_text())
    for name,d in f['filesSha256'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=d:raise ValueError('Frozen traffic source changed: '+name)
    tapes=[*Path(a.input_root).rglob('events.jsonl.gz'),*Path(a.input_root).rglob('events.jsonl')]
    if len(tapes)!=1:raise ValueError('Require one original tape')
    with open_tape(tapes[0]) as stream:r=collect(stream,json.loads(Path(f['selection']).read_text()),f['spec'])
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({k:v for k,v in r.items() if k!='states'}),flush=True)


if __name__=='__main__':main()
