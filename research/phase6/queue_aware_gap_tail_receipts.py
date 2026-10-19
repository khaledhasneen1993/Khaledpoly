"""ALL14 remaining original pair groups before first GAP; no hedge fill assumed."""
import argparse
from collections import Counter
from decimal import Decimal as D,ROUND_HALF_UP,ROUND_CEILING
import hashlib
import json
from pathlib import Path
import time
from research.phase6.queue_aware_causal import QROOT
from research.phase6.queue_aware_causal_result import load as source
from research.phase6.dq3_bottleneck_receipts import traffic
from research.phase6.queue_aware_postfill_receipts import known
from research.phase6.queue_aware_postfill_result import load as post
from research.phase6.queue_aware_counterpart import summarize as components
from research.phase6.receipt_audit import rpc


def selection():
    context,manifest,_=source();state=manifest['state'];ack=1792269759566;gap=state['terminalMs']
    original=next(s for s in traffic()['states'] if s['selection']['originalSequence']==243583)
    rows={r['input']['seq']:r['input'] for r in context['records']};transactions=[];seen=set()
    for o in original['observations']:
        if o['targetToken']!=state['quotes'][1]['token'] or not ack<o['arrivalMs']<gap:continue
        row=rows[o['normalizedSeq']];event=row['data']['events'][o['eventIndex']];data=event['data'];tx=o['sample']['transaction_hash']
        if event['kind']!='TRADE' or row['arrivalMs']!=o['arrivalMs'] or json.loads(data['tradeId'])!=o['sample'] or data['sourceMs']!=int(o['sample']['timestamp']) or tx in seen:
            raise ValueError('Changed original tail source observation')
        seen.add(tx);transactions.append(dict(transactionHash=tx,sample=o['sample'],arrivalMs=o['arrivalMs'],normalizedSeq=o['normalizedSeq'],eventIndex=o['eventIndex'],originalCensusBid=o['targetBid']))
    if len(transactions)!=14 or gap!=1792269760873:raise ValueError('Require all14 original remaining counterpart groups')
    # Derive the unchanged reduction quote from BOTH complete original ACK-frame books,
    # never from the new receipts/public aggregate prices being audited.
    books={}
    for rec in context['records']:
        row=rec['input']
        for event in row['data'].get('events',[]):
            if event['kind']=='BOOK':books[event['data']['token']]=event['data']
        if row['seq']==259283:break
    market=json.loads((QROOT/'resting-result/evidence.json').read_text())['seedWitness']['market']
    cfg=json.loads(Path('research/phase2/research-config.json').read_text());a,b=[books[q['token']] for q in state['quotes']]
    if any(not 0<=ack-book['sourceMs']<=2000 for book in [a,b]):raise ValueError('No causal original ACK-frame hedge books')
    tick=D(str(market['tick']));bid=max(D(str(l['price'])) for l in a['bids']);ask=min(D(str(l['price'])) for l in a['asks']);other=min(D(str(l['price'])) for l in b['asks'])
    quantity=D(state['quotes'][0]['quantity']);basis=D(state['quotes'][0]['price'])
    fee=lambda p:(D(str(market['feeRate']))*D(cfg['feeMultiplier'])*(p*(1-p))**market['feeExponent']).quantize(D('.00001'),rounding=ROUND_HALF_UP)
    complete=1-basis-other-fee(other)-(D(cfg['mergeCost'])/quantity).quantize(D('1e-18'),rounding=ROUND_CEILING)
    sell=bid-basis-fee(bid);price=max(ask-tick,bid+tick)
    if complete>=D(cfg['minimumEdge']) and complete>=sell:raise ValueError('Original hedge would COMPLETE, not this reduction cohort')
    if price!=D('.51'):raise ValueError('Changed unmodified original hedge quote')
    return dict(scope='ALL14_ORIGINAL_TAIL_GROUPS_BEFORE_FIRST_GAP_NOT_EXECUTION',state=state,targetQuote=state['quotes'][1],
        fixedHorizonMs=gap,afterCancelAckExclusiveMs=ack,maxNewReceiptRequests=14,transactions=transactions,
        hypotheticalUnchangedHedgeQuote=dict(token=state['quotes'][0]['token'],side='SELL',price=str(price),quantity=str(quantity)),
        hedgeQuoteSource=dict(originalSequence=259283,at=ack,leadSourceMs=a['sourceMs'],otherSourceMs=b['sourceMs'],completeValue=str(complete),sellValue=str(sell)),
        originalPublicObservationBindingUnmodified=True,quoteNotSelectedByReceiptOutcome=True,fillsCreated=0,netPnlRecomputed=False,
        independentPaperQualificationAllowed=False,liveAllowed=False)


def cached():
    e=known();_,new,_=post()
    if set(e)&set(new):raise ValueError('Duplicate prior raw source receipt')
    return {**e,**new}


def summarize(spec,evidence):
    r=components(spec,evidence);r['scope']=spec['scope'];r.pop('counterpartAfterHorizonAudited')
    token=spec['hypotheticalUnchangedHedgeQuote']['token'];num,den=D(spec['hypotheticalUnchangedHedgeQuote']['price']).as_integer_ratio()
    volume=sum(p['sharesRaw'] for row in r['results'] for p in row['parts'] if p['token']==token and not p['buy'] and p['collateralRaw']*den>=num*p['sharesRaw'])
    r.update(hypotheticalUnchangedHedgeQuote=spec['hypotheticalUnchangedHedgeQuote'],hedgeSellPriceCompatibleSharesRaw=volume,
        noHypotheticalQueueOrFillClaimed=True,decision='NEED_ACTUAL_SOURCE_TIME_HEDGE_QUEUE_AND_LIFECYCLE')
    return r


def collect(spec,output,*,read=rpc,pause=time.sleep):
    out=Path(output);raw=out/'raw';raw.mkdir(parents=True,exist_ok=True)
    canonical=json.dumps(spec,sort_keys=True,separators=(',',':'))+'\n';checkpoint=out/'selection.json'
    if checkpoint.exists() and checkpoint.read_text()!=canonical:raise ValueError('Changed selection on resume')
    checkpoint.write_text(canonical)
    if spec['maxNewReceiptRequests']!=14 or len(spec['transactions'])!=14:raise ValueError('Only frozen14 requests authorized')
    cache=cached();topics=next(iter(cache.values()))['topics'];evidence={};blocks={};calls=Counter();errors=[]
    if any(e['topics']!=topics for e in cache.values()):raise ValueError('Archived topics disagree')
    def query(method,params):calls[method]+=1;return read(method,params)
    if int(query('eth_chainId',[]),16)!=137:raise ValueError('Wrong public chain')
    for t in spec['transactions']:
        tx=t['transactionHash'];path=raw/(tx+'.json')
        try:
            if tx in cache:data=cache[tx]['data']
            elif path.exists():data=json.loads(path.read_text())
            else:
                if calls['eth_getTransactionReceipt']>=14:raise ValueError('Frozen request budget exhausted')
                pause(.5);receipt=query('eth_getTransactionReceipt',[tx])
                if not receipt:raise ValueError('Missing original receipt')
                key=receipt['blockHash'].lower()
                if key not in blocks:blocks[key]=query('eth_getBlockByHash',[key,False])
                if not blocks[key]:raise ValueError('Missing original block')
                data=dict(receipt=receipt,block=blocks[key]);path.write_text(json.dumps(data,separators=(',',':'))+'\n')
            blocks[data['block']['hash'].lower()]=data['block'];evidence[tx]=dict(data=data,topics=topics)
            summarize({**spec,'transactions':[t]},evidence)
        except (OSError,ValueError,KeyError,TypeError) as ex:errors.append(dict(transactionHash=tx,error=str(ex)[:200]))
    report=dict(scope=spec['scope'],complete=not errors and len(evidence)==14,errors=errors,eventTopics=topics,rpcCalls=dict(calls),requested=14,fillsCreated=0,netPnlRecomputed=False,liveAllowed=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    if errors:raise ValueError('Incomplete frozen14; retain successes, unknown is not zero')
    r=summarize(spec,evidence);(out/'component-summary.json').write_text(json.dumps(r,indent=2)+'\n');return r


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();f=json.loads(Path('research/phase6/queue-aware-gap-tail-freeze.json').read_text())
    for path,sha in f['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Frozen source changed '+path)
    spec=selection()
    if spec!=json.loads((QROOT/'gap-tail-selection.json').read_text()):raise ValueError('Changed frozen original tail cohort')
    r=collect(spec,a.output);print(json.dumps({k:v for k,v in r.items() if k not in ('results','state')}),flush=True)


if __name__=='__main__':main()
