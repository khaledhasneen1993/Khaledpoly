"""Reuse immutable public receipts across exact frozen DQ3 observation windows.

This measures actual settlement component prices, NOT counterfactual execution.
"""
import argparse
import base64
from collections import Counter
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import time
import zipfile
from research.phase6.dq3_bottleneck_receipts import ROOT,traffic
from research.phase6.receipt_audit import corroborate,event_topics,rpc
from research.phase6.route_coverage_audit import routes

PAIR={q['token'] for q in traffic()['states'][0]['selection']['quotes']}
ARCHIVES=[(ROOT/'bottleneck-result/artifact.zip.b64',
           '7b937464f275b0b562e12d3f203517a9c138448930761bb72178eb9fffe961dd'),
          (Path('research/experiments/risk-pair-context-20261018/receipts/artifact.zip.b64'),
           '5060cec3209b2b3d2f7929a09e349b08075f0b8064d7f942f1ba622201f775f2')]


def cached_receipts():
    cache={}
    for path,sha in ARCHIVES:
        raw=base64.b64decode(path.read_bytes())
        if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('Changed receipt archive')
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            topics=json.loads(z.read('report.json'))['eventTopics']
            for name in z.namelist():
                if name.startswith('raw/') and name.endswith('.json'):
                    data=json.loads(z.read(name));tx=data['receipt']['transactionHash']
                    if tx in cache:raise ValueError('Duplicate cached transaction')
                    cache[tx]=dict(data=data,topics=topics)
    return cache


def sample(observation):
    return dict(observation['sample'],arrivalMs=observation['arrivalMs'])


def component_volume(observation,quote,evidence):
    if observation['targetToken']!=quote['token'] or observation['targetBid']!=quote['price']:
        raise ValueError('Wrong quote binding')
    s=sample(observation);data=evidence['data']
    r=corroborate(s,data['receipt'],data['block'],evidence['topics'])
    route=routes(r,PAIR)
    if not route['uniqueConservedGroup']:raise ValueError('Ambiguous conserved route')
    # Compare integer amounts with exact rational bid, not rounded component price.
    numerator,denominator=Decimal(quote['price']).as_integer_ratio()
    parts=route['matchingGroups'][0]['components']
    return sum(p['sharesRaw'] for p in parts if p['makerToken']==quote['token']
               and p['makerSide']=='BUY' and p['collateralRaw']*denominator<=numerator*p['sharesRaw'])


def coverage(evidence):
    legs=[]
    for state in traffic()['states']:
        for quote in state['selection']['quotes']:
            observations=[o for o in state['observations'] if o['targetToken']==quote['token']]
            present=[o for o in observations if o['sample']['transaction_hash'] in evidence]
            volume=sum(component_volume(o,quote,evidence[o['sample']['transaction_hash']]) for o in present)
            complete=len(present)==len(observations)
            legs.append(dict(originalSequence=state['selection']['originalSequence'],quote=quote,
                observationCount=len(observations),auditedObservations=len(present),complete=complete,
                actualPriceCompatibleSharesRaw=volume if complete else None,
                partialKnownPriceCompatibleSharesRaw=volume,
                completeWindowZeroActualPricedComponents=complete and volume==0))
    return dict(scope='EXACT_FROZEN_STATE_LEG_RECEIPT_COVERAGE_NOT_EXECUTION',legs=legs,
        receiptCacheTransactions=len(evidence),fillsCreated=0,netPnlRecomputed=False,
        queueOrObservedActivationProven=False,independentPaperQualificationAllowed=False,liveAllowed=False,
        incompleteLegsMustNotBeTreatedAsZero=True,overlappingLegVolumesMustNotBeSummed=True)


def next_selection(evidence):
    # Earliest still-uncovered additional state; least-observed full leg, lexical tie.
    states=traffic()['states'];screen=json.loads((ROOT/'state-screen.json').read_text())
    additional={s['originalSequence'] for s in screen['states'] if s['additionalPricedState']}
    for state in sorted(states,key=lambda s:s['selection']['originalSequence']):
        if state['selection']['originalSequence'] not in additional:continue
        quote=min(state['selection']['quotes'],key=lambda q:(sum(o['targetToken']==q['token'] for o in state['observations']),q['token']))
        obs=[o for o in state['observations'] if o['targetToken']==quote['token']]
        if all(o['sample']['transaction_hash'] in evidence for o in obs):continue
        transactions=[];seen=set()
        for o in obs:
            tx=o['sample']['transaction_hash']
            if tx in seen:raise ValueError('Repeated transaction needs multi-observation scope')
            seen.add(tx)
            if not state['selection']['activationDueMs']<=int(o['sample']['timestamp'])<=o['arrivalMs']<state['terminalMs']:
                raise ValueError('Source outside upper-bound window')
            transactions.append(dict(transactionHash=tx,sample=sample(o),normalizedSeq=o['normalizedSeq'],eventIndex=o['eventIndex']))
        return dict(scope='NEXT_EARLIEST_UNCOVERED_ADDITIONAL_STATE_COMPLETE_LEAST_OBSERVED_LEG',
            state=state['selection'],targetQuote=quote,terminalMs=state['terminalMs'],terminalReason=state['terminalReason'],
            actualOrderOrObservedActivationClaimed=False,relaxedUpperBoundNotActualLifecycle=True,
            transactions=transactions,maxNewReceiptRequests=sum(t['transactionHash'] not in evidence for t in transactions),
            rule='Chronological first uncovered additional state; full least-observed leg; no outcome or price optimization')
    raise ValueError('No uncovered additional state')


def collect(spec,output,*,read=rpc,topics=None):
    out=Path(output);raw=out/'raw';raw.mkdir(parents=True,exist_ok=True)
    canonical=json.dumps(spec,sort_keys=True,separators=(',',':'))+'\n';checkpoint=out/'selection.json'
    if checkpoint.exists() and checkpoint.read_text()!=canonical:raise ValueError('Changed selection on resume')
    checkpoint.write_text(canonical);evidence=cached_receipts();calls=Counter();blocks={};errors=[]
    topics=topics or event_topics()
    def query(method,params):calls[method]+=1;return read(method,params)
    if int(query('eth_chainId',[]),16)!=137:raise ValueError('Wrong chain')
    for t in spec['transactions']:
        tx=t['transactionHash'];p=raw/(tx+'.json')
        try:
            if tx in evidence:continue
            if p.exists():data=json.loads(p.read_text())
            else:
                if calls['eth_getTransactionReceipt']>=spec['maxNewReceiptRequests']:raise ValueError('Receipt budget exhausted')
                time.sleep(.5);receipt=query('eth_getTransactionReceipt',[tx])
                if not receipt:raise ValueError('Missing receipt')
                b=receipt['blockHash'].lower()
                if b not in blocks:blocks[b]=query('eth_getBlockByHash',[b,False])
                if not blocks[b]:raise ValueError('Missing block')
                data=dict(receipt=receipt,block=blocks[b]);p.write_text(json.dumps(data,separators=(',',':'))+'\n')
            blocks[data['block']['hash'].lower()]=data['block']
            bound=next(o for s in traffic()['states'] if s['selection']==spec['state'] for o in s['observations']
                       if o['targetToken']==spec['targetQuote']['token'] and o['sample']['transaction_hash']==tx)
            e=dict(data=data,topics=topics);component_volume(bound,spec['targetQuote'],e);evidence[tx]=e
        except (ValueError,KeyError,TypeError,OSError) as ex:errors.append(dict(transactionHash=tx,error=str(ex)[:200]))
    report=dict(scope=spec['scope'],complete=not errors,errors=errors,rpcCalls=dict(calls),eventTopics=topics,
                fillsCreated=0,netPnlRecomputed=False,liveAllowed=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    result=coverage(evidence);(out/'coverage.json').write_text(json.dumps(result,indent=2)+'\n')
    if errors:raise ValueError('Incomplete receipt cohort; preserve raw successes, do not broaden selection')
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    freeze=json.loads(Path('research/phase6/dq3-overlap-receipts-freeze.json').read_text())
    for name,sha in freeze['filesSha256'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=sha:raise ValueError('Changed frozen input: '+name)
    spec=next_selection(cached_receipts())
    if spec!=json.loads((ROOT/'overlap-selection.json').read_text()):raise ValueError('Changed selection')
    print(json.dumps(collect(spec,a.output)),flush=True)


if __name__=='__main__':main()
