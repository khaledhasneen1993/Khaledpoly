"""Prepare conserved both-order replay through original first scoped GAP, no account."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from research.phase6.queue_aware_causal_result import load as original
from research.phase6.queue_aware_pair_prefix import prepare as prefix
from research.phase6.queue_aware_counterpart_result import load as early
from research.phase6.queue_aware_postfill_result import load as post,verify
from research.phase6.queue_aware_unhedged_timing_result import ROOT as TIMING


def prepare():
    context,manifest,_=original();_,_,seed=prefix();_,_,early_summary=early();spec,receipts,post_summary=post();verify(spec,receipts,post_summary)
    timing=json.loads((TIMING/'evidence.json').read_text());bindings=list(manifest['bindings'])
    for summary in [early_summary,post_summary]:
        bindings.extend(dict(seq=r['normalizedSeq'],eventIndex=r['eventIndex'],at=r['arrivalMs'],sourceMs=int(r['sample']['timestamp']),
            sample=r['sample'],transactionHash=r['transactionHash'],parts=r['parts']) for r in summary['results'])
    bindings.sort(key=lambda b:(b['seq'],b['eventIndex']));labels={(b['seq'],b['eventIndex']):b for b in bindings};ids=set();seen=set()
    if len(labels)!=148:raise ValueError('Require all39 A plus109 B source groups')
    for b in bindings:
        for p in b['parts']:
            if p['identity'] in ids:raise ValueError('Duplicate actual component across cohorts')
            ids.add(p['identity'])
    ack=timing['expectedFirstDueEngineEvent']['at'];pair=set(manifest['pair'])
    for rec in context['records']:
        row=rec['input'];at=row['arrivalMs'];events=row['data']['events'] if row['kind']=='RESEARCH_FRAME' else [dict(kind=row['kind'][9:],data=row['data'])]
        for ix,event in enumerate(events):
            data=event['data'];key=(row['seq'],ix)
            if key in labels:
                b=labels[key]
                if event['kind']!='TRADE' or at!=b['at'] or data['sourceMs']!=b['sourceMs'] or json.loads(data['tradeId'])!=b['sample']:
                    raise ValueError('Original conserved group/source binding differs')
                seen.add(key)
            elif event['kind']=='TRADE' and data['token'] in pair and manifest['state']['activationDueMs']<=data['sourceMs'] and at<=ack:
                raise ValueError('Unknown pair observation before cancel ACK')
    if seen!=set(labels):raise ValueError('Incomplete source group consumption')
    out={**manifest,'scope':'ACTUAL_COMPONENTS_THROUGH_FIRST_SCOPED_GAP_NOT_ACCOUNT','bindings':bindings,
        'counterpartExecutionOmitted':False,'restingRiskCancellationOmitted':False,'bReceiptsThroughMs':ack,
        'horizonMs':manifest['state']['terminalMs']}
    return context,out,dict(prefix=seed,timing=timing)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    frozen=json.loads(Path('research/phase6/queue-aware-through-gap-freeze.json').read_text())
    for path,sha in frozen['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Frozen source changed '+path)
    context,manifest,evidence=prepare();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    for name,obj in [('context.json.gz',context),('bindings.json',manifest),('evidence.json',evidence)]:
        raw=(json.dumps(obj,default=str,separators=(',',':'))+'\n').encode()
        (out/name).write_bytes(gzip.compress(raw,mtime=0) if name.endswith('.gz') else raw)
    print(json.dumps(dict(completeActualGroups=len(manifest['bindings']),sourceGAP=manifest['horizonMs'],newPublicReads=0,newTapeScans=0)))


if __name__=='__main__':main()
