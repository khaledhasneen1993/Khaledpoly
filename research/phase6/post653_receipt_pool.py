"""Frozen655 pool: preserve exact653 and add only its two verified next receipts."""
from collections import Counter
import json
from pathlib import Path

from research.phase6.first_blocker_receipt import digest
from research.phase6.mixed_replay_labels_proof import portions_sha
from research.phase6.post651_receipt_pool import build as parent_build,identities as parent_identities,canonical
from research.phase6.post653_next_receipts import decode
from research.phase6.post653_next_receipts_result import load,verify,ZIP_SHA
from research.phase6.receipt_audit import corroborate

ROOT=Path('research/experiments/post653-receipt-pool-20261022')
PARENT_LOGICAL_SHA='a6faa2118ba0fdc721a6eb83876886169f0c68980c0c88e04c1cb82ce6835f3c'
ORIGIN='VERIFIED_EXACT653_NEXT_RECEIPT'


def build():
    parent=parent_build();raw=canonical(parent)
    if digest(raw)!=PARENT_LOGICAL_SHA:raise ValueError('Changed frozen653 parent')
    pool=json.loads(raw);spec,raws,report=load();proof=verify(spec,raws,report)
    if proof['conservedMakerComponents']!=4 or proof['modelFillsCreated']!=0:raise ValueError('Changed exact653-next receipt evidence')
    keys={(b['seq'],b['eventIndex']) for b in parent['bindings']};txs={b['transactionHash'] for b in parent['bindings']};added=[]
    for item in spec['transactions']:
        tx=item['transactionHash'];data=json.loads(raws[tx]);route=decode(spec,item,data);group=route['matchingGroups'][0];decoded=corroborate(item['sample'],data['receipt'],data['block'],spec['topics']);matches=[m for m in decoded['matches'] if m['exchange']==group['exchange'] and m['ordersMatchedLogIndex']==group['groupLogIndex']]
        complements={m['maker']['token'] for m in matches if m['maker']['token']!=item['sample']['asset_id']}
        if (route['identityMatchingGroups']!=1 or not route['uniqueConservedGroup'] or len(route['matchingGroups'])!=1
                or len(matches)!=len(group['components']) or len(complements)!=1):raise ValueError('Ambiguous exact655 route/pair')
        pair=[item['sample']['asset_id'],next(iter(complements))]
        b=dict(seq=item['seq'],eventIndex=item['eventIndex'],at=item['at'],sourceMs=int(item['sample']['timestamp']),transactionHash=tx,publicTradeIdSha256=item['publicTradeIdSha256'],token=item['sample']['asset_id'],side=item['sample']['side'],price=item['sample']['price'],size=item['sample']['size'],pair=pair,condition=item['sample']['market'],matches=matches,sourceCoverage='MISSING_FIXED_RECEIPT_GROUP_LABEL',pairSource='FIXED_RECEIPT_GROUP_COMPLEMENT',origin=ORIGIN)
        if (b['seq'],b['eventIndex']) in keys or tx in txs:raise ValueError('Duplicate exact655 expansion')
        added.append(b);keys.add((b['seq'],b['eventIndex']));txs.add(tx)
    pool['bindings'].extend(added);pool['bindings'].sort(key=lambda b:(b['seq'],b['eventIndex']))
    if [b for b in pool['bindings'] if b.get('origin')!=ORIGIN]!=parent['bindings']:raise ValueError('Prior653 bindings changed')
    markets={}
    for binding in pool['bindings']:
        normalized=sorted(binding['pair']);condition=binding['condition']
        if condition in markets and markets[condition]!=normalized:raise ValueError('Condition mapped to multiple binary pairs')
        markets[condition]=normalized
    pool.update(scope='PARTIAL_MULTI_MARKET_RECEIPT_POOL_NOT_EXECUTION_MANIFEST',multiMarketBindings=True,bindingMarketPairs=dict(sorted(markets.items())))
    pool.update(expectedBindingCount=655,expectedComponentCount=1557,remainingUnboundObservations=15662,parent653PoolLogicalSha256=PARENT_LOGICAL_SHA,post653ReceiptBindings=2,post653ReceiptArtifactSha256=ZIP_SHA)
    counts=Counter(m['matchType'] for b in pool['bindings'] for m in b['matches'])
    if len(pool['bindings'])!=655 or sum(counts.values())!=1557 or counts!=Counter(DIRECT=359,MINT=1181,MERGE=17):raise ValueError('Incomplete655 expansion')
    pool['routeComponentCounts']=dict(counts);pool['portionsLogicalSha256']=portions_sha(pool);return pool


def identities(pool):
    parent=parent_build();source=parent_identities(parent);spec,_,_=load();rows=list(source['observations']);rows.extend(dict(seq=i['seq'],eventIndex=i['eventIndex'],at=i['at'],data=i['originalObservation']) for i in spec['transactions']);rows.sort(key=lambda r:(r['seq'],r['eventIndex']))
    if [(r['seq'],r['eventIndex']) for r in rows]!=[(b['seq'],b['eventIndex']) for b in pool['bindings']]:raise ValueError('Original655 coordinates differ')
    return dict(scope='EXACT655_ORIGINAL_IDENTITY_INPUTS_NOT_EXECUTION_TAPE',observations=rows)


def write(output):
    pool=build();pr=canonical(pool);sr=canonical(identities(pool));out=Path(output);out.mkdir(parents=True,exist_ok=False);(out/'pool.json').write_bytes(pr);(out/'source-identities.json').write_bytes(sr)
    summary=dict(scope='OFFLINE655_PARTIAL_POOL_NOT_ACCOUNT',bindings=655,components=1557,parent653Unchanged=True,addedReceiptBindings=2,poolLogicalSha256=digest(pr),sourceIdentitiesSha256=digest(sr),portionsLogicalSha256=pool['portionsLogicalSha256'],routeComponentCounts=pool['routeComponentCounts'],originalTapeReplayed=False,marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False);(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary


def verify_native(report,summary):
    if report['scope']!='ALL655_NATIVE_IDENTITY_PARITY_NOT_ACCOUNT_REPLAY' or report['originalIdentities']!=655 or report['readerRejectionGuards']!=39 or any(report[k]!=summary[k] for k in ('poolLogicalSha256','sourceIdentitiesSha256','portionsLogicalSha256')):raise ValueError('Native655 parity differs')
    p=report['pool']
    if p['bindings']!=655 or p['actualComponents']!=1557 or p['consumedBindings']!=655 or p['failed'] is not False:raise ValueError('Incomplete655 native consumption')
    for k in ('marketNetPnlRecomputed','completeAccountComparisonPerformed','independentPaperQualificationAllowed','liveAllowed'):
        if report[k] is not False:raise ValueError('Native parity promoted')
    return dict(scope='VERIFIED_ALL655_NATIVE_PARITY_NOT_ACCOUNT',originalIdentities=655,componentTuples=1557,priorBindingsPreserved=653,addedBindings=2,readerRejectionGuards=39,marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False)


if __name__=='__main__':
    import argparse;p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(write(a.output),indent=2))
