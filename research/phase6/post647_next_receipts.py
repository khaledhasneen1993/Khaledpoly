"""Exactly two blockers from retained exact647 replay; bounded public reads only."""
import argparse
from collections import Counter
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import zipfile

from research.phase6.next_postactivation_pool_replay_result import ROOT as REPLAY_ROOT,ZIP_SHA as REPLAY_SHA,verify as verify_replay
from research.phase6.postactivation_receipts import selection as prior_selection
from research.phase6.receipt_audit import rpc,corroborate
from research.phase6.route_coverage_audit import routes


def digest(raw):return hashlib.sha256(raw).hexdigest()


def selection():
    proof=verify_replay();prior=prior_selection();items=[]
    with zipfile.ZipFile(REPLAY_ROOT/'ci-artifact.zip') as z:
        for profile in ('candidate','baseline'):
            target=proof['nextReceiptTargets'][profile];failure=json.loads(z.read('development/'+profile+'/failure.json'))
            attempted=failure['labels']['lastAttemptedOriginalObservation'];observation=attempted['observation'];sample=json.loads(observation['tradeId'])
            if {k:attempted[k] for k in ('seq','eventIndex','at')}!={k:target[k] for k in ('seq','eventIndex','at')}:raise ValueError('Retained exact647 target coordinate changed')
            if sample['market']!=prior['condition'] or sample['asset_id'] not in prior['pair'] or sample['transaction_hash']!=target['transactionHash']:raise ValueError('Retained exact647 target identity changed')
            for key in ('sourceMs','token','side','price','size'):
                if str(observation[key])!=str(target[key]):raise ValueError('Retained exact647 target field changed: '+key)
            items.append(dict(profile=profile,seq=attempted['seq'],eventIndex=attempted['eventIndex'],at=attempted['at'],originalObservation=observation,
                transactionHash=target['transactionHash'],publicTradeIdSha256=digest(observation['tradeId'].encode()),sample=sample))
    if [x['seq'] for x in items]!=[9082,83030] or len({x['transactionHash'] for x in items})!=2:raise ValueError('Exactly two distinct exact647 blockers required')
    return dict(scope='TWO_EXACT_POST647_NEXT_RECEIPTS_NOT_EXECUTION',sourceReplayArtifactSha256=REPLAY_SHA,transactions=items,
        pair=prior['pair'],condition=prior['condition'],topics=prior['topics'],maxNewReceiptRequests=2,maxNewBlockRequests=2,
        noPriceOrOutcomeSelection=True,modelFillsCreated=0,marketNetPnlRecomputed=False,liveAllowed=False)


def decode(spec,item,data):
    sample=item['sample'];observation=item['originalObservation']
    if digest(observation['tradeId'].encode())!=item['publicTradeIdSha256'] or json.loads(observation['tradeId'])!=sample or sample['transaction_hash']!=item['transactionHash']:raise ValueError('Changed retained original raw preimage')
    evidence=corroborate(sample,data['receipt'],data['block'],spec['topics']);route=routes(evidence,set(spec['pair']))
    if not route['uniqueConservedGroup']:raise ValueError('Ambiguous/unknown route; never zero volume')
    group=route['matchingGroups'][0];comparisons=[r for r in evidence['takerAggregateComparisons'] if r['ordersMatchedLogIndex']==group['groupLogIndex'] and r['orderHash']==group['takerOrderHash']]
    if len(comparisons)!=1 or D(comparisons[0]['sizeDifference'])!=0 or D(comparisons[0]['priceDifference'])>D('.005'):raise ValueError('Receipt public aggregate identity differs')
    if abs(evidence['blockTimestampMs']-int(sample['timestamp']))>120000:raise ValueError('Receipt block outside original source-time bound')
    return route


def collect(spec,output,*,read=rpc):
    if spec!=selection():raise ValueError('Only exact frozen post647 next-two selection authorized')
    out=Path(output);out.mkdir(parents=True,exist_ok=True);directory=out/'raw';directory.mkdir(exist_ok=True)
    canonical=json.dumps(spec,sort_keys=True,separators=(',',':'))+'\n';saved=out/'selection.json'
    if saved.exists() and saved.read_text()!=canonical:raise ValueError('Changed selection on resume')
    saved.write_text(canonical);calls=Counter();results=[];errors=[];blocks={}
    def query(method,params):
        limits={'eth_chainId':1,'eth_getTransactionReceipt':2,'eth_getBlockByHash':2}
        if method not in limits or calls[method]>=limits[method]:raise ValueError('Bounded read-only receipt budget exceeded')
        calls[method]+=1;return read(method,params)
    for item in spec['transactions']:
        p=directory/(item['transactionHash']+'.json')
        if p.exists():
            cached=json.loads(p.read_bytes())
            if cached.get('receipt') and cached.get('block'):decode(spec,item,cached);blocks[cached['block']['hash'].lower()]=cached['block']
    try:
        if int(query('eth_chainId',[]),16)!=137:raise ValueError('Wrong public chain')
        for item in spec['transactions']:
            p=directory/(item['transactionHash']+'.json');data=json.loads(p.read_bytes()) if p.exists() else {}
            try:
                if not data.get('receipt'):data['receipt']=query('eth_getTransactionReceipt',[item['transactionHash']]);p.write_text(json.dumps(data,separators=(',',':'))+'\n')
                if not data['receipt']:raise ValueError('Original receipt absent; unknown is not zero')
                if not data.get('block'):
                    block_hash=data['receipt']['blockHash'].lower();data['block']=blocks.get(block_hash)
                    if data['block'] is None:data['block']=query('eth_getBlockByHash',[block_hash,False])
                    p.write_text(json.dumps(data,separators=(',',':'))+'\n')
                route=decode(spec,item,data);blocks[data['block']['hash'].lower()]=data['block'];results.append(dict(profile=item['profile'],seq=item['seq'],transactionHash=item['transactionHash'],rawSha256=digest(p.read_bytes()),route=route))
            except (OSError,ValueError,KeyError,TypeError) as error:errors.append(dict(transactionHash=item['transactionHash'],error=str(error)[:300]))
    except (OSError,ValueError,KeyError,TypeError) as error:errors.append(dict(error=str(error)[:300]))
    report=dict(scope=spec['scope'],complete=len(results)==2 and not errors,results=results,errors=errors,rpcCalls=dict(calls),modelFillsCreated=0,
        candidateAccountSimulated=False,nativePoolExtended=False,completeAccountComparisonPerformed=False,marketNetPnlRecomputed=False,
        independentPaperQualificationAllowed=False,liveAllowed=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    if not report['complete']:raise ValueError('Post647 receipts unresolved; retain checkpoints, no invented labels')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output');a=p.parse_args();print(json.dumps(collect(selection(),a.output) if a.output else selection(),indent=2))
