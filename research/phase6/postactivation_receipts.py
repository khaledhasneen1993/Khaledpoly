"""Exactly TWO original post-activation blocker receipts. Public read-only; no execution."""
import argparse
from collections import Counter
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import zipfile
from research.phase6.receipt_audit import rpc,corroborate
from research.phase6.route_coverage_audit import routes
from research.phase6.first_blocker_receipt import selection as original_reference
from research.phase6.source_lag_guard_diagnosis import load,ROOT,ZIP_SHA

def digest(raw):return hashlib.sha256(raw).hexdigest()


def selection():
    proof=load();reference=original_reference();items=[]
    with zipfile.ZipFile(ROOT/'ci-artifact.zip') as z:
        for profile in ('candidate','baseline'):
            r=proof['results'][profile];f=json.loads(z.read('development/'+profile+'/failure.json'));a=f['labels']['lastAttemptedOriginalObservation'];data=a['observation'];sample=json.loads(data['tradeId'])
            if not r['temporalShortcutNoLongerApplies'] or sample['market']!=reference['condition'] or sample['asset_id'] not in reference['pair']:raise ValueError('Wrong original frontier/pair')
            items.append(dict(profile=profile,seq=a['seq'],eventIndex=a['eventIndex'],at=a['at'],originalObservation=data,transactionHash=r['transactionHash'],publicTradeIdSha256=r['publicTradeIdSha256'],sample=sample))
    if [r['seq'] for r in items]!=[9035,82964] or len({r['transactionHash'] for r in items})!=2:raise ValueError('Exactly two distinct original frontier receipts required')
    return dict(scope='TWO_EXACT_ORIGINAL_POSTACTIVATION_RECEIPTS_NOT_EXECUTION',sourceArtifactSha256=ZIP_SHA,transactions=items,pair=reference['pair'],condition=reference['condition'],topics=reference['topics'],maxNewReceiptRequests=2,maxNewBlockRequests=2,noPriceOrOutcomeSelection=True,modelFillsCreated=0,marketNetPnlRecomputed=False,liveAllowed=False)


def decode(spec,item,data):
    sample=item['sample'];observation=item['originalObservation']
    if digest(observation['tradeId'].encode())!=item['publicTradeIdSha256'] or json.loads(observation['tradeId'])!=sample or sample['transaction_hash']!=item['transactionHash']:raise ValueError('Changed original raw preimage')
    evidence=corroborate(sample,data['receipt'],data['block'],spec['topics']);route=routes(evidence,set(spec['pair']))
    if not route['uniqueConservedGroup']:raise ValueError('Ambiguous/unknown route; never zero volume')
    group=route['matchingGroups'][0]
    comparisons=[r for r in evidence['takerAggregateComparisons'] if r['ordersMatchedLogIndex']==group['groupLogIndex'] and r['orderHash']==group['takerOrderHash']]
    if len(comparisons)!=1 or D(comparisons[0]['sizeDifference'])!=0 or D(comparisons[0]['priceDifference'])>D('.005'):raise ValueError('Receipt public aggregate identity differs')
    if abs(evidence['blockTimestampMs']-int(sample['timestamp']))>120000:raise ValueError('Receipt block outside original source-time bound')
    return route


def collect(spec,output,*,read=rpc):
    if spec!=selection():raise ValueError('Only exact frozen TWO-original selection authorized')
    out=Path(output);out.mkdir(parents=True,exist_ok=True);directory=out/'raw';directory.mkdir(exist_ok=True)
    canonical=json.dumps(spec,sort_keys=True,separators=(',',':'))+'\n';saved=out/'selection.json'
    if saved.exists() and saved.read_text()!=canonical:raise ValueError('Changed selection on resume')
    saved.write_text(canonical);calls=Counter();results=[];errors=[];blocks={}
    def query(method,params):
        limits={'eth_chainId':1,'eth_getTransactionReceipt':2,'eth_getBlockByHash':2}
        if method not in limits or calls[method]>=limits[method]:raise ValueError('Bounded read-only receipt budget exceeded')
        calls[method]+=1;return read(method,params)
    # Cache is trusted only after decode; successful response bytes are checkpointed immediately.
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
                if not data.get('receipt'):
                    data['receipt']=query('eth_getTransactionReceipt',[item['transactionHash']]);p.write_text(json.dumps(data,separators=(',',':'))+'\n')
                if not data['receipt']:raise ValueError('Original receipt absent; unknown is not zero')
                if not data.get('block'):
                    block_hash=data['receipt']['blockHash'].lower();data['block']=blocks.get(block_hash)
                    if data['block'] is None:data['block']=query('eth_getBlockByHash',[block_hash,False])
                    p.write_text(json.dumps(data,separators=(',',':'))+'\n')
                route=decode(spec,item,data);blocks[data['block']['hash'].lower()]=data['block']
                results.append(dict(profile=item['profile'],seq=item['seq'],transactionHash=item['transactionHash'],rawSha256=digest(p.read_bytes()),route=route))
            except (OSError,ValueError,KeyError,TypeError) as error:errors.append(dict(transactionHash=item['transactionHash'],error=str(error)[:300]))
    except (OSError,ValueError,KeyError,TypeError) as error:errors.append(dict(error=str(error)[:300]))
    report=dict(scope=spec['scope'],complete=len(results)==2 and not errors,results=results,errors=errors,rpcCalls=dict(calls),modelFillsCreated=0,candidateAccountSimulated=False,nativePoolExtended=False,completeAccountComparisonPerformed=False,marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    if not report['complete']:raise ValueError('Post-activation receipts unresolved; retain checkpoints, no invented labels')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output');a=p.parse_args();print(json.dumps(collect(selection(),a.output) if a.output else selection(),indent=2))
