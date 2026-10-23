"""Frozen649 pool: preserve exact647 and add only its two verified next receipts."""
from collections import Counter
import json
from pathlib import Path

from research.phase6.first_blocker_receipt import digest
from research.phase6.mixed_replay_labels_proof import portions_sha
from research.phase6.next_postactivation_receipt_pool import build as parent_build,identities as parent_identities,canonical
from research.phase6.post647_next_receipts import decode
from research.phase6.post647_next_receipts_result import load,verify,ZIP_SHA
from research.phase6.receipt_audit import corroborate

ROOT=Path('research/experiments/post647-receipt-pool-20261021')
PARENT_LOGICAL_SHA='aa3f42e1cfff24fd5c9f3750136f56a4e23d7cd333a9d949e4224b176c4a4da4'
ORIGIN='VERIFIED_EXACT647_NEXT_RECEIPT'


def build():
    parent=parent_build();raw=canonical(parent)
    if digest(raw)!=PARENT_LOGICAL_SHA:raise ValueError('Changed frozen647 parent')
    pool=json.loads(raw);spec,raws,report=load();proof=verify(spec,raws,report)
    if proof['conservedMakerComponents']!=4 or proof['modelFillsCreated']!=0:raise ValueError('Changed exact647-next receipt evidence')
    keys={(b['seq'],b['eventIndex']) for b in parent['bindings']};txs={b['transactionHash'] for b in parent['bindings']};added=[]
    for item in spec['transactions']:
        tx=item['transactionHash'];data=json.loads(raws[tx]);route=decode(spec,item,data);group=route['matchingGroups'][0];decoded=corroborate(item['sample'],data['receipt'],data['block'],spec['topics']);matches=[m for m in decoded['matches'] if m['exchange']==group['exchange'] and m['ordersMatchedLogIndex']==group['groupLogIndex']]
        if route['identityMatchingGroups']!=1 or not route['uniqueConservedGroup'] or len(route['matchingGroups'])!=1 or len(matches)!=2:raise ValueError('Ambiguous exact649 route')
        b=dict(seq=item['seq'],eventIndex=item['eventIndex'],at=item['at'],sourceMs=int(item['sample']['timestamp']),transactionHash=tx,publicTradeIdSha256=item['publicTradeIdSha256'],token=item['sample']['asset_id'],side=item['sample']['side'],price=item['sample']['price'],size=item['sample']['size'],pair=spec['pair'],condition=spec['condition'],matches=matches,sourceCoverage='MISSING_SCOPED_PAIR_LABEL',origin=ORIGIN)
        if (b['seq'],b['eventIndex']) in keys or tx in txs:raise ValueError('Duplicate exact649 expansion')
        added.append(b);keys.add((b['seq'],b['eventIndex']));txs.add(tx)
    pool['bindings'].extend(added);pool['bindings'].sort(key=lambda b:(b['seq'],b['eventIndex']))
    if [b for b in pool['bindings'] if b.get('origin')!=ORIGIN]!=parent['bindings']:raise ValueError('Prior647 bindings changed')
    pool.update(expectedBindingCount=649,expectedComponentCount=1540,remainingUnboundObservations=15668,parent647PoolLogicalSha256=PARENT_LOGICAL_SHA,post647ReceiptBindings=2,post647ReceiptArtifactSha256=ZIP_SHA)
    counts=Counter(m['matchType'] for b in pool['bindings'] for m in b['matches'])
    if len(pool['bindings'])!=649 or sum(counts.values())!=1540 or counts!=Counter(DIRECT=359,MINT=1164,MERGE=17):raise ValueError('Incomplete649 expansion')
    pool['routeComponentCounts']=dict(counts);pool['portionsLogicalSha256']=portions_sha(pool);return pool


def identities(pool):
    parent=parent_build();source=parent_identities(parent);spec,_,_=load();rows=list(source['observations']);rows.extend(dict(seq=i['seq'],eventIndex=i['eventIndex'],at=i['at'],data=i['originalObservation']) for i in spec['transactions']);rows.sort(key=lambda r:(r['seq'],r['eventIndex']))
    if [(r['seq'],r['eventIndex']) for r in rows]!=[(b['seq'],b['eventIndex']) for b in pool['bindings']]:raise ValueError('Original649 coordinates differ')
    return dict(scope='EXACT649_ORIGINAL_IDENTITY_INPUTS_NOT_EXECUTION_TAPE',observations=rows)


def write(output):
    pool=build();pr=canonical(pool);sr=canonical(identities(pool));out=Path(output);out.mkdir(parents=True,exist_ok=False);(out/'pool.json').write_bytes(pr);(out/'source-identities.json').write_bytes(sr)
    summary=dict(scope='OFFLINE649_PARTIAL_POOL_NOT_ACCOUNT',bindings=649,components=1540,parent647Unchanged=True,addedReceiptBindings=2,poolLogicalSha256=digest(pr),sourceIdentitiesSha256=digest(sr),portionsLogicalSha256=pool['portionsLogicalSha256'],routeComponentCounts=pool['routeComponentCounts'],originalTapeReplayed=False,marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False);(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary


def verify_native(report,summary):
    if report['scope']!='ALL649_NATIVE_IDENTITY_PARITY_NOT_ACCOUNT_REPLAY' or report['originalIdentities']!=649 or report['readerRejectionGuards']!=39 or any(report[k]!=summary[k] for k in ('poolLogicalSha256','sourceIdentitiesSha256','portionsLogicalSha256')):raise ValueError('Native649 parity differs')
    p=report['pool']
    if p['bindings']!=649 or p['actualComponents']!=1540 or p['consumedBindings']!=649 or p['failed'] is not False:raise ValueError('Incomplete649 native consumption')
    for k in ('marketNetPnlRecomputed','completeAccountComparisonPerformed','independentPaperQualificationAllowed','liveAllowed'):
        if report[k] is not False:raise ValueError('Native parity promoted')
    return dict(scope='VERIFIED_ALL649_NATIVE_PARITY_NOT_ACCOUNT',originalIdentities=649,componentTuples=1540,priorBindingsPreserved=647,addedBindings=2,readerRejectionGuards=39,marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False)


if __name__=='__main__':
    import argparse;p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(write(a.output),indent=2))
