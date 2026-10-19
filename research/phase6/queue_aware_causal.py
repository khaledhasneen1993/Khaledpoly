"""Freeze/extract one QW0 necessary-leg optimistic causal probe, not an account."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from research.phase3.polybot_sdk.tapes import open_tape
from research.phase6.dq3_last_activation import extract
from research.phase6.dq3_bottleneck_receipts import traffic
from research.phase6.queue_aware_cached_traffic import QROOT,cached_evidence
from research.phase6.receipt_audit import corroborate
from research.phase6.route_coverage_audit import routes


def selection_and_bindings(evidence=None):
    result=json.loads((QROOT/'cached-traffic.json').read_text())
    supported=[s for s in result['states'] if s['completeActualPriceCompatibleSharesRaw']>0]
    if len(supported)!=1 or supported[0]['originalSequence']!=243583:raise ValueError('Require single frozen supported start')
    screen=json.loads((QROOT/'state-screen.json').read_text());w=next(w for w in screen['states'] if w['originalSequence']==243583)
    proposal=w['proposal'];old=next(s for s in traffic()['states'] if s['selection']['originalSequence']==243583)
    state=dict(old['selection']);state['quotes']=[dict(q,price=proposal[k]) for q,k in zip(state['quotes'],['firstBid','secondBid'])]
    state['targetQuote']=state['quotes'][0];state['terminalMs']=old['terminalMs']
    pair={q['token'] for q in state['quotes']};e=cached_evidence() if evidence is None else evidence
    rows=[];identities=set();txs=set()
    for o in old['observations']:
        if o['targetToken']!=state['targetQuote']['token']:continue
        sample=o['sample'];tx=sample['transaction_hash']
        if tx not in e or tx in txs:raise ValueError('Missing/duplicate complete source receipt')
        txs.add(tx);raw=e[tx]['data'];decoded=corroborate(sample,raw['receipt'],raw['block'],e[tx]['topics'])
        route=routes(decoded,pair)
        if not route['uniqueConservedGroup']:raise ValueError('Ambiguous actual route')
        group=route['matchingGroups'][0];parts=[]
        for part in group['components']:
            identity=f"{group['exchange']}:{tx}:{group['groupLogIndex']}:{part['makerLogIndex']}"
            if identity in identities:raise ValueError('Duplicate conserved component')
            identities.add(identity)
            if (part['makerToken'] not in pair or part['makerSide'] not in ('BUY','SELL')
                    or type(part['sharesRaw']) is not int or type(part['collateralRaw']) is not int
                    or not 0<part['collateralRaw']<part['sharesRaw']):raise ValueError('Invalid conserved integer portion')
            parts.append(dict(identity=identity,token=part['makerToken'],buy=part['makerSide']=='BUY',
                sharesRaw=part['sharesRaw'],collateralRaw=part['collateralRaw']))
        rows.append(dict(seq=o['normalizedSeq'],eventIndex=o['eventIndex'],at=o['arrivalMs'],
            sourceMs=int(sample['timestamp']),sample=sample,transactionHash=tx,parts=parts))
    if len(rows)!=39 or len(txs)!=39:raise ValueError('Complete39 target-leg observations required')
    manifest=dict(scope='QW0_ISOLATED_TARGET_LEG_CONSERVED_ACTUAL_COMPONENTS_NOT_ACCOUNT',
        state=state,pair=sorted(pair),bindings=rows,restingRiskCancellationOmitted=True,
        counterpartExecutionOmitted=True,netPnlRecomputed=False,liveAllowed=False)
    spec=dict(startMs=state['submitMs']-2000,endMs=old['terminalMs'],maxBookAgeMs=2000,
        sourceRows=6163831,logicalTapeSha256='cd850df52d7f9994526603130f2942008f8f49ba80495d82b70dea66f0dc6d8b',states=[state])
    return spec,manifest


def validate_terminal(context,spec):
    terminal=spec['states'][0]['terminalMs'];pair={q['token'] for q in spec['states'][0]['quotes']}
    def scoped(d):
        tokens=set(d.get('tokens',[]))|({d['token']} if 'token' in d else set())
        return not tokens or bool(tokens&pair)
    gaps=[event for rec in context['records'] if rec['input']['arrivalMs']==terminal
          for event in rec['input']['data'].get('events',[]) if event['kind']=='GAP'
          and event['data'].get('reason')=='invalid_depth' and scoped(event['data'])]
    gaps.extend(rec for rec in context['records'] if rec['input']['arrivalMs']==terminal
        and rec['input']['kind']=='RESEARCH_GAP' and rec['input']['data'].get('reason')=='invalid_depth'
        and scoped(rec['input']['data']))
    if not gaps:raise ValueError('Frozen original scoped terminal GAP missing')


def run(input_root,output):
    f=json.loads(Path('research/phase6/queue-aware-causal-freeze.json').read_text())
    for path,sha in f['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Changed frozen QW0 causal input '+path)
    spec,manifest=selection_and_bindings()
    if spec!=f['spec'] or manifest!=json.loads((QROOT/'causal-bindings.json').read_text()):
        raise ValueError('Changed frozen quote/actual component manifest')
    tapes=[*Path(input_root).rglob('events.jsonl.gz'),*Path(input_root).rglob('events.jsonl')]
    if len(tapes)!=1:raise ValueError('Require one complete original tape')
    with open_tape(tapes[0]) as stream:context=extract(stream,spec,max_bytes=128000000)
    validate_terminal(context,spec)
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    with (out/'context.json.gz').open('xb') as target:
        with gzip.GzipFile(fileobj=target,mode='wb',mtime=0) as gz:gz.write((json.dumps(context,separators=(',',':'))+'\n').encode())
    (out/'bindings.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:v for k,v in context.items() if k!='records'}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input-root',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.input_root,a.output)
