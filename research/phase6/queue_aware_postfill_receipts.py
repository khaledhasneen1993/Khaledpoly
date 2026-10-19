"""Freeze ALL79 original post-fill counterpart observations through conditional ACK."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time
from research.phase6.queue_aware_causal import QROOT
from research.phase6.queue_aware_causal_result import load as source
from research.phase6.queue_aware_cached_traffic import cached_evidence
from research.phase6.queue_aware_counterpart import summarize as component_summary
from research.phase6.queue_aware_counterpart_result import load as early_receipts
from research.phase6.queue_aware_unhedged_timing_result import ROOT as TIMING,saved
from research.phase6.receipt_audit import rpc


def selection():
    saved();e=json.loads((TIMING/'evidence.json').read_text());context,_,_=source()
    inputs={r['input']['seq']:r['input'] for r in context['records']};transactions=[];seen=set()
    for o in e['postFillCounterpartSourceObservations']:
        row=inputs[o['normalizedSeq']];event=row['data']['events'][o['eventIndex']];d=event['data'];tx=o['sample']['transaction_hash']
        if (event['kind']!='TRADE' or json.loads(d['tradeId'])!=o['sample'] or row['arrivalMs']!=o['arrivalMs']
                or not e['firstModelAllocationMs']<row['arrivalMs']<=e['expectedFirstDueEngineEvent']['at'] or tx in seen):
            raise ValueError('Changed original conditional post-fill cohort')
        seen.add(tx);transactions.append(dict(transactionHash=tx,sample=o['sample'],arrivalMs=o['arrivalMs'],
            normalizedSeq=o['normalizedSeq'],eventIndex=o['eventIndex'],originalCensusBid=o['targetBid']))
    if len(transactions)!=79:raise ValueError('Require complete79 original post-fill observations')
    return dict(scope='CONDITIONAL_POST_FILL_COUNTERPART79_ACTUAL_COMPONENTS_NOT_ACCOUNT',state=e['state'],
        targetQuote=e['state']['quotes'][1],fixedHorizonMs=e['expectedFirstDueEngineEvent']['at'],
        firstModelAllocationMs=e['firstModelAllocationMs'],conditionalTimingBranchNotYetValidated=True,
        transactions=transactions,maxNewReceiptRequests=79,originalPublicObservationBindingUnmodified=True,
        fillsCreated=0,netPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False)


def known():
    result=cached_evidence();_,early,_=early_receipts()
    if set(result)&set(early):raise ValueError('Duplicate prior cached source receipt')
    return {**result,**early}


def summarize(spec,evidence):
    r=component_summary(spec,evidence)
    r['scope']=spec['scope'];r.pop('counterpartAfterHorizonAudited')
    r.update(firstModelAllocationMs=spec['firstModelAllocationMs'],conditionalTimingBranchNotYetValidated=True,
        outsideSelectedWindowAudited=False,decision='NEED_ACTUAL_CAUSAL_POST_FILL_LIFECYCLE')
    return r


def collect(spec,output,*,read=rpc,pause=time.sleep):
    out=Path(output);raw=out/'raw';raw.mkdir(parents=True,exist_ok=True)
    canonical=json.dumps(spec,sort_keys=True,separators=(',',':'))+'\n';checkpoint=out/'selection.json'
    if checkpoint.exists() and checkpoint.read_text()!=canonical:raise ValueError('Changed selection on resume')
    checkpoint.write_text(canonical)
    if spec['maxNewReceiptRequests']!=79 or len(spec['transactions'])!=79:raise ValueError('Only frozen79 receipts authorized')
    cache=known();topics=next(iter(cache.values()))['topics'];evidence={};blocks={};calls=Counter();errors=[]
    if any(e['topics']!=topics for e in cache.values()):raise ValueError('Archived event topics disagree')
    def query(method,params):calls[method]+=1;return read(method,params)
    if int(query('eth_chainId',[]),16)!=137:raise ValueError('Wrong public chain')
    for t in spec['transactions']:
        tx=t['transactionHash'];path=raw/(tx+'.json')
        try:
            if tx in cache:data=cache[tx]['data']
            elif path.exists():data=json.loads(path.read_text())
            else:
                if calls['eth_getTransactionReceipt']>=79:raise ValueError('Frozen request budget exhausted')
                pause(.5);receipt=query('eth_getTransactionReceipt',[tx])
                if not receipt:raise ValueError('Missing original receipt')
                key=receipt['blockHash'].lower()
                if key not in blocks:blocks[key]=query('eth_getBlockByHash',[key,False])
                if not blocks[key]:raise ValueError('Missing original block')
                data=dict(receipt=receipt,block=blocks[key]);path.write_text(json.dumps(data,separators=(',',':'))+'\n')
            blocks[data['block']['hash'].lower()]=data['block'];evidence[tx]=dict(data=data,topics=topics)
            summarize({**spec,'transactions':[t]},evidence)
        except (OSError,ValueError,KeyError,TypeError) as ex:errors.append(dict(transactionHash=tx,error=str(ex)[:200]))
    report=dict(scope=spec['scope'],complete=not errors and len(evidence)==79,errors=errors,eventTopics=topics,
        rpcCalls=dict(calls),requested=79,fillsCreated=0,netPnlRecomputed=False,liveAllowed=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    if errors:raise ValueError('Incomplete frozen79 cohort; retain successes, never treat unknown as zero')
    r=summarize(spec,evidence);(out/'component-summary.json').write_text(json.dumps(r,indent=2)+'\n');return r


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    f=json.loads(Path('research/phase6/queue-aware-postfill-receipts-freeze.json').read_text())
    for path,sha in f['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Frozen source changed '+path)
    spec=selection()
    if spec!=json.loads((QROOT/'postfill-selection.json').read_text()):raise ValueError('Frozen original selection differs')
    r=collect(spec,a.output);print(json.dumps({k:v for k,v in r.items() if k not in ('results','state')}),flush=True)


if __name__=='__main__':main()
