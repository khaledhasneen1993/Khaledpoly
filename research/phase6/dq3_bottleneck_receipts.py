"""Complete smallest-leg receipt cohort of the FIRST additional DQ3 state only."""
import argparse
import base64
from collections import Counter
from decimal import Decimal as D
import hashlib
import io
import json
from pathlib import Path
import time
import zipfile
from research.phase6.receipt_audit import corroborate,event_topics,rpc
from research.phase6.route_coverage_audit import routes

ROOT=Path('research/experiments/depth-quote-20261018')
ZIP_SHA='c0750f3db849972f1d4cd01f5428944c1b55b179fbe66c0dd1e7f236b2817490'


def traffic():
    raw=base64.b64decode((ROOT/'traffic-result/artifact.zip.b64').read_bytes())
    if hashlib.sha256(raw).hexdigest()!=ZIP_SHA:raise ValueError('Original traffic artifact changed')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if [(i.filename,i.file_size) for i in z.infolist()]!=[('depth-quote-traffic.json',794108)]:
            raise ValueError('Unexpected traffic artifact members')
        return json.loads(z.read('depth-quote-traffic.json'))


def selection():
    r=traffic();screen=json.loads((ROOT/'state-screen.json').read_text())
    if (r['sourceRows']!=6163831 or r['fillsCreated']!=0 or r['netPnlRecomputed']
            or r['observationCount']!=sum(len(s['observations']) for s in r['states'])):
        raise ValueError('Wrong source/no-fill traffic scope')
    additional=sorted((s for s in screen['states'] if s['additionalPricedState']),key=lambda s:s['originalSequence'])
    state=next(s for s in r['states'] if s['selection']['originalSequence']==additional[0]['originalSequence'])
    counts=Counter(o['targetToken'] for o in state['observations'])
    quote=min(state['selection']['quotes'],key=lambda q:(counts[q['token']],q['token']))
    selected=[o for o in state['observations'] if o['targetToken']==quote['token']]
    txs=[]
    for o in selected:
        sample=dict(o['sample'],arrivalMs=o['arrivalMs']);tx=sample['transaction_hash']
        if not state['selection']['activationDueMs']<=int(sample['timestamp'])<=sample['arrivalMs']<state['terminalMs']:
            raise ValueError('Sample outside explicit upper-bound window')
        txs.append(dict(transactionHash=tx,sample=sample,normalizedSeq=o['normalizedSeq'],eventIndex=o['eventIndex']))
    if len(txs)!=8 or len({t['transactionHash'] for t in txs})!=8:raise ValueError('Complete eight-receipt cohort changed')
    return dict(scope='FIRST_ADDITIONAL_DQ3_STATE_COMPLETE_LEAST_OBSERVED_LEG',
        rule='First additional state by original sequence; least observed target leg, lexical token tie-break; ALL its observations',
        originalTrafficZipSha256=ZIP_SHA,state=state['selection'],terminalMs=state['terminalMs'],terminalReason=state['terminalReason'],
        targetQuote=quote,otherLegObservationsNotAudited=sum(counts.values())-len(selected),maxNewReceiptRequests=8,
        actualOrderOrObservedActivationClaimed=False,relaxedUpperBoundNotActualLifecycle=True,transactions=txs)


def summarize(report,spec):
    if not report['complete'] or len(report['results'])!=8:raise ValueError('Incomplete complete-leg receipt cohort')
    expected={x['transactionHash']:x['sample'] for x in spec['transactions']};seen=set();out=[]
    for row in report['results']:
        sample=row['sample'];tx=sample['transaction_hash'];route=row['routeConservation']
        if tx in seen or sample!=expected[tx] or not route['uniqueConservedGroup']:raise ValueError('Wrong/duplicate/ambiguous source route')
        seen.add(tx);parts=route['matchingGroups'][0]['components'];q=spec['targetQuote']
        buys=[p for p in parts if p['makerToken']==q['token'] and p['makerSide']=='BUY']
        priced=[p for p in buys if D(p['collateralRaw'])<=D(q['price'])*p['sharesRaw']]
        out.append(dict(transactionHash=tx,routeSharesRaw=route['matchingGroups'][0]['routeSharesRaw'],
            targetBuyComponents=buys,atOrBelowOwnBidSharesRaw=sum(p['sharesRaw'] for p in priced)))
    return dict(scope='ACTUAL_RECEIPT_COMPONENTS_OF_SELECTED_UPPER_BOUND_LEG_NOT_QUEUE_ALLOCATION',
        targetQuote=spec['targetQuote'],results=out,targetBuyAtOrBelowOwnBidSharesRaw=sum(r['atOrBelowOwnBidSharesRaw'] for r in out),
        otherLegAudited=False,otherStatesAudited=False,observedActivationOrQueueProven=False,
        fillsCreated=0,netPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False,decision='NO_GO')


def collect(spec,output,*,read=rpc,topics=None):
    out=Path(output);out.mkdir(parents=True,exist_ok=True);raw=out/'raw';raw.mkdir(exist_ok=True)
    canonical=json.dumps(spec,sort_keys=True,separators=(',',':'))+'\n';checkpoint=out/'selection.json'
    if checkpoint.exists() and checkpoint.read_text()!=canonical:raise ValueError('Frozen selection changed on resume')
    checkpoint.write_text(canonical)
    calls=Counter();blocks={};results=[];errors=[];topics=topics or event_topics()
    def query(method,params):calls[method]+=1;return read(method,params)
    if int(query('eth_chainId',[]),16)!=137:raise ValueError('Wrong public chain')
    pair={q['token'] for q in spec['state']['quotes']}
    for item in spec['transactions']:
        tx=item['transactionHash'];p=raw/(tx+'.json')
        try:
            if p.exists():data=json.loads(p.read_text())
            else:
                if calls['eth_getTransactionReceipt']>=8:raise ValueError('Frozen request budget exhausted')
                time.sleep(.5);receipt=query('eth_getTransactionReceipt',[tx])
                if not receipt:raise ValueError('Receipt absent')
                block_hash=receipt['blockHash'].lower()
                if block_hash not in blocks:blocks[block_hash]=query('eth_getBlockByHash',[block_hash,False])
                if not blocks[block_hash]:raise ValueError('Public block absent; do not cache incomplete data')
                data=dict(receipt=receipt,block=blocks[block_hash]);p.write_text(json.dumps(data,separators=(',',':'))+'\n')
            blocks[data['block']['hash'].lower()]=data['block']
            result=corroborate(item['sample'],data['receipt'],data['block'],topics)
            result['routeConservation']=routes(result,pair);results.append(result)
        except (ValueError,KeyError,TypeError,OSError) as e:errors.append(dict(transactionHash=tx,error=str(e)[:200]))
    report=dict(scope='FROZEN_SOURCE_RECEIPTS_NOT_ACTUAL_ORDER_LIFECYCLE',complete=not errors and len(results)==8,
        requested=8,results=results,errors=errors,eventTopics=topics,rpcCalls=dict(calls),fillsCreated=0,netPnlRecomputed=False,
        independentPaperQualificationAllowed=False,liveAllowed=False,decision='NO_GO')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    summary=summarize(report,spec);(out/'route-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    f=json.loads(Path('research/phase6/dq3-bottleneck-receipts-freeze.json').read_text())
    for name,d in f['filesSha256'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=d:raise ValueError('Frozen source changed: '+name)
    spec=selection()
    if spec!=json.loads((ROOT/'bottleneck-selection.json').read_text()):raise ValueError('Frozen source selection changed')
    r=collect(spec,a.output);print(json.dumps(r),flush=True)


if __name__=='__main__':main()
