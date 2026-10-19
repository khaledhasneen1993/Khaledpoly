"""Frozen ALL451 original pair observations; generic BUY/SELL conserved labels only."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time
from research.phase6.queue_aware_causal import QROOT
from research.phase6.queue_aware_post_gap_result import ROOT,verify,COMPRESSED_SHA
from research.phase6.queue_aware_gap_tail_receipts import cached as prior_cache
from research.phase6.queue_aware_gap_tail_result import load as tail_receipts
from research.phase6.receipt_audit import rpc,corroborate
from research.phase6.route_coverage_audit import routes


def selection():
    verify();s=json.loads((ROOT/'data-summary.json').read_text());seen=set();txs=[]
    for r in s['allOriginalPairTradesAfterGap']:
        tx=r['sample']['transaction_hash']
        if tx in seen or not s['spec']['firstGapMs']<r['at']<=s['spec']['endMs']:raise ValueError('Changed complete original recovery cohort')
        seen.add(tx);txs.append(dict(transactionHash=tx,sample=r['sample'],arrivalMs=r['at'],normalizedSeq=r['seq'],eventIndex=r['eventIndex']))
    if len(txs)!=451:raise ValueError('Require ALL451 original observations, no price/outcome filter')
    pair=json.loads((QROOT/'causal-bindings.json').read_text())['pair']
    return dict(scope='ALL451_ORIGINAL_RECOVERY_PAIR_COMPONENTS_NOT_EXECUTION',originalTapeLogicalSha256=s['spec']['logicalTapeSha256'],originalContextCompressedSha256=COMPRESSED_SHA,
        pair=pair,window=s['spec'],transactions=txs,maxNewReceiptRequests=451,
        selectionNotFilteredByPriceOrOutcome=True,fillsCreated=0,netPnlRecomputed=False,
        candidateAccountSimulated=False,independentPaperQualificationAllowed=False,liveAllowed=False)


def cached():
    old=prior_cache();_,tail,_=tail_receipts()
    if set(old)&set(tail):raise ValueError('Duplicate archived receipt identity')
    return {**old,**tail}


def decode(t,data,topics,pair):
    r=corroborate(t['sample'],data['receipt'],data['block'],topics);route=routes(r,set(pair))
    if not route['uniqueConservedGroup']:raise ValueError('Unknown/ambiguous actual recovery route; never zero')
    g=route['matchingGroups'][0];parts=[];seen=set()
    for p in g['components']:
        identity=f"{g['exchange']}:{t['transactionHash']}:{g['groupLogIndex']}:{p['makerLogIndex']}"
        if (identity in seen or p['makerToken'] not in pair or p['makerSide'] not in ('BUY','SELL')
                or type(p['sharesRaw']) is not int or type(p['collateralRaw']) is not int or not 0<p['collateralRaw']<p['sharesRaw']):raise ValueError('Duplicate/invalid actual integer recovery component')
        seen.add(identity);parts.append(dict(identity=identity,token=p['makerToken'],buy=p['makerSide']=='BUY',sharesRaw=p['sharesRaw'],collateralRaw=p['collateralRaw']))
    return dict(**t,parts=parts)


def collect(spec,output,*,read=rpc,pause=time.sleep):
    if spec['maxNewReceiptRequests']!=451 or len(spec['transactions'])!=451:raise ValueError('Only frozen451 receipt budget authorized')
    out=Path(output);out.mkdir(parents=True,exist_ok=True);raw=out/'raw';raw.mkdir(exist_ok=True)
    canonical=json.dumps(spec,sort_keys=True,separators=(',',':'))+'\n';checkpoint=out/'selection.json'
    if checkpoint.exists() and checkpoint.read_text()!=canonical:raise ValueError('Changed frozen selection on resume')
    checkpoint.write_text(canonical)
    cache=cached();topics=next(iter(cache.values()))['topics'];blocks={};calls=Counter();errors=[];rows=[];reused=0
    if any(e['topics']!=topics for e in cache.values()):raise ValueError('Archived event topics disagree')
    def query(method,params):calls[method]+=1;return read(method,params)
    if int(query('eth_chainId',[]),16)!=137:raise ValueError('Wrong public chain')
    for t in spec['transactions']:
        tx=t['transactionHash'];path=raw/(tx+'.json')
        try:
            if path.exists():data=json.loads(path.read_text());reused+=1
            elif tx in cache:data=cache[tx]['data'];reused+=1
            else:
                if calls['eth_getTransactionReceipt']>=451:raise ValueError('Frozen request budget exhausted')
                pause(.5);receipt=query('eth_getTransactionReceipt',[tx])
                if not receipt:raise ValueError('Missing original receipt; unknown is not zero')
                key=receipt['blockHash'].lower()
                if key not in blocks:blocks[key]=query('eth_getBlockByHash',[key,False])
                if not blocks[key]:raise ValueError('Missing original block')
                data=dict(receipt=receipt,block=blocks[key])
            rows.append(decode(t,data,topics,spec['pair']))
            blocks[data['block']['hash'].lower()]=data['block']
            if not path.exists():path.write_text(json.dumps(data,separators=(',',':'))+'\n')
        except (OSError,ValueError,KeyError,TypeError) as ex:errors.append(dict(transactionHash=tx,error=str(ex)[:200]))
    report=dict(scope=spec['scope'],complete=not errors and len(rows)==451,errors=errors,requested=451,reusedReceipts=reused,
        eventTopics=topics,rpcCalls=dict(calls),fillsCreated=0,netPnlRecomputed=False,liveAllowed=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    if errors:raise ValueError('Incomplete original451; retain raw checkpoint, do not rerun successful receipts')
    identities=[p['identity'] for r in rows for p in r['parts']]
    if len(identities)!=len(set(identities)):raise ValueError('Duplicate actual component across recovery groups')
    result=dict(scope=spec['scope'],complete=True,observations=451,results=rows,uniqueMakerComponents=len(identities),
        genericBothMakerSidesAndBothTokens=True,queueAndStrategyLifecycleNotSimulated=True,
        fillsCreated=0,netPnlRecomputed=False,candidateAccountSimulated=False,independentPaperQualificationAllowed=False,liveAllowed=False)
    (out/'component-summary.json').write_text(json.dumps(result,indent=2)+'\n');return report


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    f=json.loads(Path('research/phase6/queue-aware-recovery-receipts-freeze.json').read_text())
    for path,sha in f['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Frozen recovery input changed '+path)
    s=selection()
    if s!=json.loads((QROOT/'recovery-selection.json').read_text()):raise ValueError('Changed frozen original451 selection')
    print(json.dumps(collect(s,a.output)))


if __name__=='__main__':main()
