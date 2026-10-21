"""Frozen651 pool: preserve exact649 and add only its two verified next receipts."""
from collections import Counter
import json
from pathlib import Path

from research.phase6.first_blocker_receipt import digest
from research.phase6.mixed_replay_labels_proof import portions_sha
from research.phase6.post647_receipt_pool import build as parent_build,identities as parent_identities,canonical
from research.phase6.post649_next_receipts import decode
from research.phase6.post649_next_receipts_result import load,verify,ZIP_SHA
from research.phase6.receipt_audit import corroborate

ROOT=Path('research/experiments/post649-receipt-pool-20261021')
PARENT_LOGICAL_SHA='377a4394ec3542dfa085f33771a238e030142303b327ef8a14caf3b93de6481a'
ORIGIN='VERIFIED_EXACT649_NEXT_RECEIPT'


def build():
    parent=parent_build();raw=canonical(parent)
    if digest(raw)!=PARENT_LOGICAL_SHA:raise ValueError('Changed frozen649 parent')
    pool=json.loads(raw);spec,raws,report=load();proof=verify(spec,raws,report)
    if proof['conservedMakerComponents']!=10 or proof['modelFillsCreated']!=0:raise ValueError('Changed exact649-next receipt evidence')
    keys={(b['seq'],b['eventIndex']) for b in parent['bindings']};txs={b['transactionHash'] for b in parent['bindings']};added=[]
    for item in spec['transactions']:
        tx=item['transactionHash'];data=json.loads(raws[tx]);route=decode(spec,item,data);group=route['matchingGroups'][0];decoded=corroborate(item['sample'],data['receipt'],data['block'],spec['topics']);matches=[m for m in decoded['matches'] if m['exchange']==group['exchange'] and m['ordersMatchedLogIndex']==group['groupLogIndex']]
        if route['identityMatchingGroups']!=1 or not route['uniqueConservedGroup'] or len(route['matchingGroups'])!=1 or len(matches)!=len(group['components']):raise ValueError('Ambiguous exact651 route')
        b=dict(seq=item['seq'],eventIndex=item['eventIndex'],at=item['at'],sourceMs=int(item['sample']['timestamp']),transactionHash=tx,publicTradeIdSha256=item['publicTradeIdSha256'],token=item['sample']['asset_id'],side=item['sample']['side'],price=item['sample']['price'],size=item['sample']['size'],pair=spec['pair'],condition=spec['condition'],matches=matches,sourceCoverage='MISSING_SCOPED_PAIR_LABEL',origin=ORIGIN)
        if (b['seq'],b['eventIndex']) in keys or tx in txs:raise ValueError('Duplicate exact651 expansion')
        added.append(b);keys.add((b['seq'],b['eventIndex']));txs.add(tx)
    pool['bindings'].extend(added);pool['bindings'].sort(key=lambda b:(b['seq'],b['eventIndex']))
    if [b for b in pool['bindings'] if b.get('origin')!=ORIGIN]!=parent['bindings']:raise ValueError('Prior649 bindings changed')
    pool.update(expectedBindingCount=651,expectedComponentCount=1550,remainingUnboundObservations=15666,parent649PoolLogicalSha256=PARENT_LOGICAL_SHA,post649ReceiptBindings=2,post649ReceiptArtifactSha256=ZIP_SHA)
    counts=Counter(m['matchType'] for b in pool['bindings'] for m in b['matches'])
    if len(pool['bindings'])!=651 or sum(counts.values())!=1550 or counts!=Counter(DIRECT=359,MINT=1174,MERGE=17):raise ValueError('Incomplete651 expansion')
    pool['routeComponentCounts']=dict(counts);pool['portionsLogicalSha256']=portions_sha(pool);return pool


def identities(pool):
    parent=parent_build();source=parent_identities(parent);spec,_,_=load();rows=list(source['observations']);rows.extend(dict(seq=i['seq'],eventIndex=i['eventIndex'],at=i['at'],data=i['originalObservation']) for i in spec['transactions']);rows.sort(key=lambda r:(r['seq'],r['eventIndex']))
    if [(r['seq'],r['eventIndex']) for r in rows]!=[(b['seq'],b['eventIndex']) for b in pool['bindings']]:raise ValueError('Original651 coordinates differ')
    return dict(scope='EXACT651_ORIGINAL_IDENTITY_INPUTS_NOT_EXECUTION_TAPE',observations=rows)


def write(output):
    pool=build();pr=canonical(pool);sr=canonical(identities(pool));out=Path(output);out.mkdir(parents=True,exist_ok=False);(out/'pool.json').write_bytes(pr);(out/'source-identities.json').write_bytes(sr)
    summary=dict(scope='OFFLINE651_PARTIAL_POOL_NOT_ACCOUNT',bindings=651,components=1550,parent649Unchanged=True,addedReceiptBindings=2,poolLogicalSha256=digest(pr),sourceIdentitiesSha256=digest(sr),portionsLogicalSha256=pool['portionsLogicalSha256'],routeComponentCounts=pool['routeComponentCounts'],originalTapeReplayed=False,marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False);(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary


def verify_native(report,summary):
    if report['scope']!='ALL651_NATIVE_IDENTITY_PARITY_NOT_ACCOUNT_REPLAY' or report['originalIdentities']!=651 or report['readerRejectionGuards']!=39 or any(report[k]!=summary[k] for k in ('poolLogicalSha256','sourceIdentitiesSha256','portionsLogicalSha256')):raise ValueError('Native651 parity differs')
    p=report['pool']
    if p['bindings']!=651 or p['actualComponents']!=1550 or p['consumedBindings']!=651 or p['failed'] is not False:raise ValueError('Incomplete651 native consumption')
    for k in ('marketNetPnlRecomputed','completeAccountComparisonPerformed','independentPaperQualificationAllowed','liveAllowed'):
        if report[k] is not False:raise ValueError('Native parity promoted')
    return dict(scope='VERIFIED_ALL651_NATIVE_PARITY_NOT_ACCOUNT',originalIdentities=651,componentTuples=1550,priorBindingsPreserved=649,addedBindings=2,readerRejectionGuards=39,marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False)


if __name__=='__main__':
    import argparse;p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(write(a.output),indent=2))
