"""Both-order source/receipt-bound prefix; no hedge, account or profit inferred."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from research.phase6.queue_aware_causal_result import load as causal
from research.phase6.queue_aware_counterpart_result import load as counterpart,verify
from research.phase6.queue_aware_resting import timeline


def prepare():
    context,original,prior=causal();spec,cache,summary=counterpart();verify(spec,cache,summary)
    horizon=spec['fixedHorizonMs'];manifest={**original,'scope':'COMPLETE_BOTH_ORDER_ORIGINAL_PREFIX_NOT_ACCOUNT',
        'bindings':[b for b in original['bindings'] if b['at']<=horizon],
        'counterpartExecutionOmitted':False,'restingRiskCancellationOmitted':False,'fixedHorizonMs':horizon}
    manifest['bindings'] += [dict(seq=r['normalizedSeq'],eventIndex=r['eventIndex'],at=r['arrivalMs'],
        sourceMs=int(r['sample']['timestamp']),sample=r['sample'],transactionHash=r['transactionHash'],parts=r['parts'])
        for r in summary['results']]
    manifest['bindings'].sort(key=lambda b:(b['seq'],b['eventIndex']))
    labels={(b['seq'],b['eventIndex']):b for b in manifest['bindings']};identities=set()
    if len(labels)!=40:raise ValueError('Changed complete both-order40 original bindings')
    for b in manifest['bindings']:
        for p in b['parts']:
            if p['identity'] in identities:raise ValueError('Overlapping actual maker component')
            identities.add(p['identity'])
    pair=set(manifest['pair']);consumed=set()
    for rec in context['records']:
        row=rec['input'];at=row['arrivalMs']
        if at>horizon:break
        events=row['data']['events'] if row['kind']=='RESEARCH_FRAME' else [dict(kind=row['kind'][9:],data=row['data'])]
        for ix,event in enumerate(events):
            data=event['data'];key=(row['seq'],ix)
            if event['kind']=='TRADE' and data['token'] in pair and manifest['state']['activationDueMs']<=data['sourceMs']:
                if key not in labels:raise ValueError('Unknown pair observation inside frozen prefix')
            if key in labels:
                b=labels[key]
                if event['kind']!='TRADE' or json.loads(data['tradeId'])!=b['sample'] or at!=b['at'] or data['sourceMs']!=b['sourceMs']:
                    raise ValueError('Receipt label differs from original causal source')
                consumed.add(key)
    if consumed!=set(labels):raise ValueError('Incomplete original prefix labels')
    evidence=timeline(context,original,prior)
    return context,manifest,evidence


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    f=json.loads(Path('research/phase6/queue-aware-pair-prefix-freeze.json').read_text())
    for path,sha in f['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Frozen input changed '+path)
    context,manifest,evidence=prepare();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    for name,obj in [('context.json.gz',context),('bindings.json',manifest),('evidence.json',evidence)]:
        raw=(json.dumps(obj,default=str,separators=(',',':'))+'\n').encode()
        (out/name).write_bytes(gzip.compress(raw,mtime=0) if name.endswith('.gz') else raw)
    print(json.dumps(dict(originalSequence=243583,completeBothOrderBindings=len(manifest['bindings']),
        scheduledChecks=len(evidence['checks']),fixedHorizonMs=manifest['fixedHorizonMs'],newRpcCalls=0,newTapeScans=0)))


if __name__=='__main__':main()
