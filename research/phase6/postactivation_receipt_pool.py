"""Frozen645 receipt pool: preserve all643 prior bindings and add exactly two verified receipts."""
import argparse
from collections import Counter
import json
from pathlib import Path

from research.phase6.expanded_receipt_pool import build as parent_build,identities as parent_identities
from research.phase6.first_blocker_receipt import digest
from research.phase6.mixed_replay_labels_proof import portions_sha
from research.phase6.postactivation_receipts import decode
from research.phase6.postactivation_receipts_result import load,verify,ZIP_SHA
from research.phase6.receipt_audit import corroborate

ROOT=Path('research/experiments/postactivation-receipt-pool-20261020')
PARENT_LOGICAL_SHA='c41eda69ffe03ed06835a9fac403401f0d68aa3fa92b019bf37d410a212ee231'
ORIGIN='VERIFIED_POSTACTIVATION_EXACT_RECEIPT'


def canonical(value):
    return (json.dumps(value,separators=(',',':'))+'\n').encode()


def build():
    parent=parent_build();parent_raw=canonical(parent)
    if digest(parent_raw)!=PARENT_LOGICAL_SHA:raise ValueError('Changed frozen643 parent')
    pool=json.loads(parent_raw);spec,raws,report=load();verified=verify(spec,raws,report)
    if verified['conservedMakerComponents']!=2 or verified['modelFillsCreated']!=0:raise ValueError('Changed exact receipt evidence')
    old_keys={(b['seq'],b['eventIndex']) for b in parent['bindings']};old_txs={b['transactionHash'] for b in parent['bindings']}
    additions=[]
    for item in spec['transactions']:
        tx=item['transactionHash'];raw=json.loads(raws[tx]);route=decode(spec,item,raw)
        if route['identityMatchingGroups']!=1 or not route['uniqueConservedGroup'] or len(route['matchingGroups'])!=1:raise ValueError('Ambiguous postactivation route')
        group=route['matchingGroups'][0]
        decoded=corroborate(item['sample'],raw['receipt'],raw['block'],spec['topics'])
        matches=[m for m in decoded['matches'] if m['exchange']==group['exchange'] and m['ordersMatchedLogIndex']==group['groupLogIndex']]
        if len(matches)!=len(group['components']) or len(matches)!=1:raise ValueError('Raw maker component selection differs')
        binding=dict(seq=item['seq'],eventIndex=item['eventIndex'],at=item['at'],sourceMs=int(item['sample']['timestamp']),
            transactionHash=tx,publicTradeIdSha256=item['publicTradeIdSha256'],token=item['sample']['asset_id'],
            side=item['sample']['side'],price=item['sample']['price'],size=item['sample']['size'],pair=spec['pair'],condition=spec['condition'],
            matches=matches,sourceCoverage='MISSING_SCOPED_PAIR_LABEL',origin=ORIGIN)
        if (binding['seq'],binding['eventIndex']) in old_keys or tx in old_txs:raise ValueError('Duplicate postactivation expansion')
        additions.append(binding);old_keys.add((binding['seq'],binding['eventIndex']));old_txs.add(tx)
    if len(additions)!=2:raise ValueError('Exactly two receipt bindings required')
    pool['bindings'].extend(additions);pool['bindings'].sort(key=lambda b:(b['seq'],b['eventIndex']))
    if [b for b in pool['bindings'] if b.get('origin')!=ORIGIN]!=parent['bindings']:raise ValueError('Prior643 bindings changed')
    pool.update(expectedBindingCount=645,expectedComponentCount=1534,remainingUnboundObservations=15672,
        parent643PoolLogicalSha256=PARENT_LOGICAL_SHA,postactivationReceiptBindings=2,
        postactivationReceiptArtifactSha256=ZIP_SHA)
    counts=Counter(m['matchType'] for b in pool['bindings'] for m in b['matches'])
    if len(pool['bindings'])!=645 or sum(counts.values())!=1534 or counts!=Counter(DIRECT=355,MINT=1162,MERGE=17):raise ValueError('Incomplete645 expansion')
    pool['routeComponentCounts']=dict(counts);pool['portionsLogicalSha256']=portions_sha(pool)
    return pool


def identities(pool):
    parent=parent_build();source=parent_identities(parent);spec,_,_=load();rows=list(source['observations'])
    for item in spec['transactions']:
        rows.append(dict(seq=item['seq'],eventIndex=item['eventIndex'],at=item['at'],data=item['originalObservation']))
    rows.sort(key=lambda r:(r['seq'],r['eventIndex']))
    if [(r['seq'],r['eventIndex']) for r in rows]!=[(b['seq'],b['eventIndex']) for b in pool['bindings']]:raise ValueError('Original645 coordinates differ')
    return dict(scope='EXACT645_ORIGINAL_IDENTITY_INPUTS_NOT_EXECUTION_TAPE',observations=rows)


def write(output):
    pool=build();pool_raw=canonical(pool);source_raw=canonical(identities(pool));out=Path(output);out.mkdir(parents=True,exist_ok=False)
    (out/'pool.json').write_bytes(pool_raw);(out/'source-identities.json').write_bytes(source_raw)
    summary=dict(scope='OFFLINE645_PARTIAL_POOL_NOT_ACCOUNT',bindings=645,components=1534,parent643Unchanged=True,
        addedReceiptBindings=2,poolLogicalSha256=digest(pool_raw),sourceIdentitiesSha256=digest(source_raw),
        portionsLogicalSha256=pool['portionsLogicalSha256'],routeComponentCounts=pool['routeComponentCounts'],
        generatedHelperRequired=True,originalTapeReplayed=False,marketNetPnlRecomputed=False,
        independentPaperQualificationAllowed=False,liveAllowed=False)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary


def verify_native(report,summary):
    if (report['scope']!='ALL645_NATIVE_IDENTITY_PARITY_NOT_ACCOUNT_REPLAY' or report['originalIdentities']!=645
            or report['readerRejectionGuards']!=39 or report['conservativeRoundingBoundaryCases']!=2
            or any(report[k]!=summary[k] for k in ('poolLogicalSha256','sourceIdentitiesSha256','portionsLogicalSha256'))):raise ValueError('Native645 source/component parity differs')
    reader=report['pool']
    if (reader['bindings']!=645 or reader['actualComponents']!=1534 or reader['consumedBindings']!=645
            or reader['failed'] is not False or reader['strictPartialPool'] is not True):raise ValueError('Incomplete645 native consumption')
    for k in ('aggregateFallbackAllowed','fullOriginalTapeCoverageProven','fullAccountReplayAuthorized','independentPaperQualificationAllowed','liveAllowed'):
        if reader[k] is not False:raise ValueError('Partial pool scope promoted')
    for k in ('marketNetPnlRecomputed','completeAccountComparisonPerformed','independentPaperQualificationAllowed','liveAllowed'):
        if report[k] is not False:raise ValueError('Native parity promoted to performance evidence')
    guard=report['separateSyntheticUnknownGuard'];session=guard['session']
    if (guard['inputKind']!='SYNTHETIC_ONLY_NOT_MARKET' or guard['unknownCoveredTransactionAtWrongCoordinateHaltsCancels'] is not True
            or guard['subsequentInputBlocked'] is not True or guard['existingCashAndInventoryPreserved'] is not True
            or session['halted'] is not True or session['openOrderCount']!=0):raise ValueError('Synthetic unknown guard differs')
    return dict(scope='VERIFIED_ALL645_NATIVE_PARITY_NOT_ACCOUNT',originalIdentities=645,componentTuples=1534,
        priorBindingsPreserved=643,addedBindings=2,readerRejectionGuards=39,marketNetPnlRecomputed=False,
        independentPaperQualificationAllowed=False,liveAllowed=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(write(a.output),indent=2))
