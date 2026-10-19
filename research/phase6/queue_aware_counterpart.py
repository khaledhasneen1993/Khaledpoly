"""Fixed QW0 counterpart receipts through prior conditional first-fill horizon only."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time
from research.phase6.dq3_bottleneck_receipts import traffic
from research.phase6.queue_aware_causal import QROOT,selection_and_bindings
from research.phase6.queue_aware_causal_result import load
from research.phase6.queue_aware_cached_traffic import cached_evidence,actual_priced_volume
from research.phase6.receipt_audit import corroborate,rpc
from research.phase6.route_coverage_audit import routes


def selection():
    context,manifest,report=load();_,expected=selection_and_bindings()
    if manifest!=expected:raise ValueError('Changed original selected QW0 state')
    horizon=1792269754123
    if len(report['conditionalModelFills'])!=1 or report['conditionalModelFills'][0]['at']!=horizon:
        raise ValueError('Changed PREVIOUS fixed first conditional target-fill horizon')
    state=manifest['state'];quote=state['quotes'][1]
    source=next(s for s in traffic()['states'] if s['selection']['originalSequence']==243583)
    inputs={r['input']['seq']:r['input'] for r in context['records']};cache=cached_evidence();txs=[];seen=set()
    for o in source['observations']:
        if o['targetToken']!=quote['token'] or o['arrivalMs']>horizon:continue
        tx=o['sample']['transaction_hash'];row=inputs[o['normalizedSeq']]
        event=row['data']['events'][o['eventIndex']];d=event['data']
        if (event['kind']!='TRADE' or json.loads(d['tradeId'])!=o['sample'] or row['arrivalMs']!=o['arrivalMs']
                or d['sourceMs']!=int(o['sample']['timestamp']) or tx in seen
                or not state['activationDueMs']<=d['sourceMs']<=row['arrivalMs']<=horizon):
            raise ValueError('Counterpart census does not bind exact original input')
        seen.add(tx);txs.append(dict(transactionHash=tx,sample=o['sample'],arrivalMs=o['arrivalMs'],
            normalizedSeq=o['normalizedSeq'],eventIndex=o['eventIndex'],originalCensusBid=o['targetBid']))
    if len(txs)!=30 or any(t['transactionHash'] in cache for t in txs):raise ValueError('Changed complete30 uncached observations')
    return dict(scope='QW0_COUNTERPART_ALL_SOURCE_OBSERVATIONS_THROUGH_PRIOR_FIRST_TARGET_FILL_NOT_ACCOUNT',
        state=state,targetQuote=quote,fixedHorizonMs=horizon,transactions=txs,maxNewReceiptRequests=30,
        remainingCounterpartObservationsAfterHorizon=123-30,originalSourceObservationBindingUnmodified=True,
        fillsCreated=0,netPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False)


def summarize(spec,evidence):
    pair={q['token'] for q in spec['state']['quotes']};quote=spec['targetQuote'];rows=[];seen=set()
    for t in spec['transactions']:
        tx=t['transactionHash']
        if tx not in evidence:raise ValueError('Incomplete counterpart receipts; unknown is not zero')
        e=evidence[tx];raw=e['data'];decoded=corroborate(t['sample'],raw['receipt'],raw['block'],e['topics'])
        route=routes(decoded,pair)
        if not route['uniqueConservedGroup']:raise ValueError('Ambiguous original counterpart route')
        group=route['matchingGroups'][0];parts=[]
        for p in group['components']:
            identity=f"{group['exchange']}:{tx}:{group['groupLogIndex']}:{p['makerLogIndex']}"
            if identity in seen or type(p['sharesRaw']) is not int or type(p['collateralRaw']) is not int or not 0<p['collateralRaw']<p['sharesRaw']:
                raise ValueError('Duplicate or invalid integer actual counterpart component')
            seen.add(identity);parts.append(dict(identity=identity,token=p['makerToken'],buy=p['makerSide']=='BUY',
                sharesRaw=p['sharesRaw'],collateralRaw=p['collateralRaw']))
        volume=actual_priced_volume(group['components'],quote['token'],quote['price'])
        rows.append(dict(**t,actualPriceCompatibleSharesRaw=volume,parts=parts))
    volume=sum(r['actualPriceCompatibleSharesRaw'] for r in rows)
    return dict(scope='COMPLETE30_ORIGINAL_COUNTERPART_ACTUAL_COMPONENTS_NOT_QUEUE_OR_ACCOUNT',
        state=spec['state'],targetQuote=quote,fixedHorizonMs=spec['fixedHorizonMs'],observations=len(rows),
        complete=True,results=rows,actualPriceCompatibleSharesRaw=volume,
        componentPriceDerivedFromIntegerSettlementNotAggregateComplement=True,
        counterpartAfterHorizonAudited=False,activationQueueOrStrategyLifecycleProven=False,
        fillsCreated=0,netPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False,
        decision='NEED_CAUSAL_COUNTERPART_GATE' if volume else 'NO_COUNTERPART_PRICED_COMPONENTS_BEFORE_PRIOR_TARGET_FILL')


def collect(spec,output,*,read=rpc,pause=time.sleep):
    out=Path(output);raw=out/'raw';raw.mkdir(parents=True,exist_ok=True)
    canonical=json.dumps(spec,sort_keys=True,separators=(',',':'))+'\n';checkpoint=out/'selection.json'
    if checkpoint.exists() and checkpoint.read_text()!=canonical:raise ValueError('Selection changed on resume')
    checkpoint.write_text(canonical);cached=cached_evidence();topics=next(iter(cached.values()))['topics']
    if any(e['topics']!=topics for e in cached.values()):raise ValueError('Cached original event topics disagree')
    if spec['maxNewReceiptRequests']!=30 or len(spec['transactions'])!=30:raise ValueError('Only frozen30 public receipts allowed')
    calls=Counter();blocks={};evidence={};errors=[]
    def query(method,params):calls[method]+=1;return read(method,params)
    if int(query('eth_chainId',[]),16)!=137:raise ValueError('Wrong public chain')
    for t in spec['transactions']:
        tx=t['transactionHash'];path=raw/(tx+'.json')
        try:
            if tx in cached:raise ValueError('Do not redownload cached source transaction')
            if path.exists():data=json.loads(path.read_text())
            else:
                if calls['eth_getTransactionReceipt']>=30:raise ValueError('Frozen receipt budget exhausted')
                pause(.5);receipt=query('eth_getTransactionReceipt',[tx])
                if not receipt:raise ValueError('Missing original receipt')
                key=receipt['blockHash'].lower()
                if key not in blocks:blocks[key]=query('eth_getBlockByHash',[key,False])
                if not blocks[key]:raise ValueError('Missing original block')
                data=dict(receipt=receipt,block=blocks[key]);path.write_text(json.dumps(data,separators=(',',':'))+'\n')
            blocks[data['block']['hash'].lower()]=data['block'];evidence[tx]=dict(data=data,topics=topics)
            # Fail each source binding promptly; never turn an unknown route into zero volume.
            one={**spec,'transactions':[t]};summarize(one,evidence)
        except (OSError,ValueError,KeyError,TypeError) as ex:errors.append(dict(transactionHash=tx,error=str(ex)[:200]))
    report=dict(scope=spec['scope'],complete=not errors and len(evidence)==30,errors=errors,
        eventTopics=topics,rpcCalls=dict(calls),requested=30,fillsCreated=0,netPnlRecomputed=False,liveAllowed=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    if errors:raise ValueError('Incomplete frozen cohort; preserve successes and do not broaden requests')
    result=summarize(spec,evidence);(out/'component-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    f=json.loads(Path('research/phase6/queue-aware-counterpart-freeze.json').read_text())
    for path,sha in f['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Frozen source changed '+path)
    spec=selection()
    if spec!=json.loads((QROOT/'counterpart-selection.json').read_text()):raise ValueError('Changed frozen30 source selection')
    r=collect(spec,a.output);print(json.dumps({k:v for k,v in r.items() if k!='results'}),flush=True)


if __name__=='__main__':main()
