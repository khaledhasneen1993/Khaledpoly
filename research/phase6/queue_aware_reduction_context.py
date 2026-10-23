"""Complete162 source-bound conserved groups; preparation only, NOT an execution gate."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from research.phase6.queue_aware_through_gap import prepare as prior
from research.phase6.queue_aware_gap_tail_result import load,verify


def prepare():
    context,manifest,evidence=prior();spec,receipts,summary=load();verification=verify(spec,receipts,summary)
    bindings=list(manifest['bindings'])
    for r in summary['results']:
        bindings.append(dict(seq=r['normalizedSeq'],eventIndex=r['eventIndex'],at=r['arrivalMs'],sourceMs=int(r['sample']['timestamp']),
            sample=r['sample'],transactionHash=r['transactionHash'],parts=r['parts']))
    bindings.sort(key=lambda b:(b['seq'],b['eventIndex']));labels={(b['seq'],b['eventIndex']):b for b in bindings}
    if len(bindings)!=162 or len(labels)!=162:raise ValueError('Require all162 disjoint original groups')
    ids=[p['identity'] for b in bindings for p in b['parts']]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate actual component across complete cohorts')
    pair=set(manifest['pair']);seen=set()
    for rec in context['records']:
        row=rec['input'];at=row['arrivalMs']
        events=row['data']['events'] if row['kind']=='RESEARCH_FRAME' else [dict(kind=row['kind'][9:],data=row['data'])]
        for ix,event in enumerate(events):
            data=event['data'];key=(row['seq'],ix)
            if key in labels:
                b=labels[key]
                if event['kind']!='TRADE' or at!=b['at'] or data['sourceMs']!=b['sourceMs'] or json.loads(data['tradeId'])!=b['sample']:raise ValueError('Changed complete162 original source binding')
                seen.add(key)
            elif event['kind']=='TRADE' and data['token'] in pair and manifest['state']['activationDueMs']<=data['sourceMs'] and at<manifest['horizonMs']:
                raise ValueError('Unknown pair observation before first GAP')
    if seen!=set(labels):raise ValueError('Incomplete complete162 source consumption')
    return context,{**manifest,'scope':'COMPLETE162_ACTIVE_REDUCTION_INPUTS_NOT_EXECUTION',
        'bindings':bindings,'bReceiptsThroughMs':manifest['horizonMs'],
        'activeReductionQueueAndLifecycleEvaluated':False},dict(**evidence,tailVerification=verification)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    frozen=json.loads(Path('research/phase6/queue-aware-active-reduction-freeze.json').read_text())
    for path,sha in frozen['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Frozen source changed '+path)
    c,m,e=prepare();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    for name,obj in [('context.json.gz',c),('bindings.json',m),('evidence.json',e)]:
        raw=(json.dumps(obj,default=str,separators=(',',':'))+'\n').encode()
        (out/name).write_bytes(gzip.compress(raw,mtime=0) if name.endswith('.gz') else raw)
    print(json.dumps(dict(scope=m['scope'],completeOriginalGroups=len(m['bindings']),newPublicReads=0,netPnlRecomputed=False)))
