"""Rebind ALL reviewed cached candidates; no new reads, fills or account replay.

This is a PARTIAL receipt pool, deliberately not the old window-complete adapter
manifest. Future native consumers must check exact original identities and fail
on unknown observations; never convert missing coverage to aggregate/zero volume.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

from research.phase6.full_tape_coverage_result import ROOT as COVERAGE,read_archive,verify,reviewed_cache
from research.phase6.mixed_replay_labels import export
from research.phase6.mixed_replay_labels_proof import portions_sha
from research.phase6.receipt_audit import corroborate
from research.phase6.route_coverage_audit import routes

ROOT=Path('research/experiments/cached-receipt-pool-20261020')
METADATA=Path('research/experiments/queue-aware-quote-20261019/resting-result/evidence.json')
METADATA_SHA='7fa1a1db395505779421387b038c67cfaf8cc7c1ec5a7c5a099f1a85aa1b5035'


def digest(raw):return hashlib.sha256(raw).hexdigest()


def load_inputs():
    if digest(METADATA.read_bytes())!=METADATA_SHA:
        raise ValueError('Changed original metadata identity evidence')
    # Reproduce the prior source-bound metadata/causal evidence; not just a cache hit.
    from research.phase6.queue_aware_resting_result import saved
    saved()
    market=json.loads(METADATA.read_text())['seedWitness']['market']
    labels=export();path=Path('research/phase6/full-tape-coverage-freeze.json');frozen=json.loads(path.read_text())
    inspection=json.loads(Path(frozen['referenceInspection']).read_text());report,compressed,_=read_archive(COVERAGE/'artifact.zip')
    proof,missing,_=verify(report,compressed,labels,inspection,frozen,digest(path.read_bytes()))
    return market,labels,missing,reviewed_cache(),proof


def build(market,labels,missing,cache,source_proof):
    pair=[market['first'],market['second']];condition=market['condition']
    if (market['negativeRisk'] is not False or len(set(pair))!=2 or set(pair)!=set(labels['coverage']['pair'])
            or source_proof['originalTradeObservations']!=16317 or source_proof['validatedBindings']!=451
            or not source_proof['allTradeIdentityDigestReproduced']):
        raise ValueError('Proven original binary market/source required')
    selected=[row for row in missing if row['transactionHash'] in cache]
    if len(selected)!=191 or len({r['transactionHash'] for r in selected})!=191:
        raise ValueError('Require ALL191 reviewed cached candidates, no outcome filtering')
    bindings=[dict(b,condition=condition,sourceCoverage='BOUND_CONSERVED_GROUP',origin='RECOVERY451') for b in labels['bindings']]
    for row in selected:
        if row['condition']!=condition or row['token'] not in pair or row['coverage']!='MISSING_SCOPED_PAIR_LABEL':
            raise ValueError('No guessed metadata pair for another market')
        evidence=cache[row['transactionHash']];data=evidence['data']
        # These normalized facts AND public identity hash are bound to the complete
        # original census. Native lookup must still recheck the actual tradeId bytes.
        sample=dict(asset_id=row['token'],side=row['side'],price=str(row['price']),size=str(row['size']),
                    timestamp=str(row['sourceMs']),transaction_hash=row['transactionHash'])
        decoded=corroborate(sample,data['receipt'],data['block'],evidence['topics'])
        conserved=routes(decoded,set(pair))
        if not conserved['uniqueConservedGroup']:
            raise ValueError('Unknown/ambiguous actual cached route; never drop candidate')
        group=conserved['matchingGroups'][0]
        matches=[m for m in decoded['matches'] if m['exchange']==group['exchange'] and m['ordersMatchedLogIndex']==group['groupLogIndex']]
        binding={k:row[k] for k in ('seq','eventIndex','at','sourceMs','transactionHash','publicTradeIdSha256','token','side','price','size')}
        binding.update(pair=pair,condition=condition,matches=matches,sourceCoverage=row['coverage'],origin='REBOUND_REVIEWED_CACHE191')
        bindings.append(binding)
    bindings.sort(key=lambda b:(b['seq'],b['eventIndex']))
    keys=[(b['seq'],b['eventIndex']) for b in bindings];txs=[b['transactionHash'] for b in bindings]
    if len(keys)!=642 or len(set(keys))!=642 or len(set(txs))!=642:
        raise ValueError('Duplicate source coordinate/transaction in combined pool')
    counts=Counter();new_counts=Counter();ids=set()
    for b in bindings:
        for m in b['matches']:
            identity=(m['exchange'],b['transactionHash'],m['ordersMatchedLogIndex'],m['maker']['logIndex'])
            if identity in ids:
                raise ValueError('Actual component reused across pool observations')
            ids.add(identity);counts[m['matchType']]+=1
            if b['origin']=='REBOUND_REVIEWED_CACHE191':new_counts[m['matchType']]+=1
    pool=dict(schema=1,experiment='CONSERVED-RECEIPT-POOL0',
        scope='PARTIAL_SINGLE_MARKET_RECEIPT_POOL_NOT_EXECUTION_MANIFEST',partialLabels=True,
        allOriginalPairObservationsWithinWindow=False,unknownScopedObservation='FAIL_CLOSED',
        logicalTapeSha256=labels['logicalTapeSha256'],sourceCensusArtifactZipSha256='882112d70db3b1926e235ebfd0a150fa5a3d6ffc40d0aac657358c9a2ed9a46e',
        sourceAllTradeIdentitiesSha256=source_proof['allObservationIdentitiesSha256'],
        metadataIdentityReference=dict(path=str(METADATA),sha256=METADATA_SHA,condition=condition,pair=pair,negativeRisk=False),
        metadataUsedOnlyForStaticPairIdentityNotDecisionFreshness=True,
        expectedBindingCount=642,expectedComponentCount=len(ids),originalBindings=451,reboundCachedBindings=191,
        remainingUnboundObservations=16317-642,routeComponentCounts=dict(counts),reboundRouteComponentCounts=dict(new_counts),
        bindings=bindings,nativeSourceIdentityRecheckRequired=True,nativePoolConsumerImplemented=False,
        newPublicReads=0,modelFillsCreated=0,netPnlRecomputed=False,candidateAccountSimulated=False,
        fullAccountReplayAuthorized=False,independentPaperQualificationAllowed=False,liveAllowed=False,decision='NO_GO')
    pool['portionsLogicalSha256']=portions_sha(pool)
    return pool


def lookup(pool,seq,index,at,data):
    """Research lookup contract only; NEVER called by default/native/live engine."""
    if (pool['experiment']!='CONSERVED-RECEIPT-POOL0' or pool['allOriginalPairObservationsWithinWindow']
            or pool['unknownScopedObservation']!='FAIL_CLOSED' or pool['fullAccountReplayAuthorized'] or pool['liveAllowed']):
        raise ValueError('Partial offline pool contract required')
    from decimal import Decimal
    matches=[b for b in pool['bindings'] if b['seq']==seq and b['eventIndex']==index]
    if len(matches)!=1:
        raise ValueError('Unknown/duplicate source observation; incomplete pool is not zero')
    b=matches[0];raw=data['tradeId']
    if (b['at']!=at or b['sourceMs']!=data['sourceMs'] or b['token']!=data['token'] or b['side']!=data['side']
            or Decimal(str(b['price']))!=Decimal(str(data['price'])) or Decimal(str(b['size']))!=Decimal(str(data['size']))
            or digest(raw.encode())!=b['publicTradeIdSha256'] or json.loads(raw)['transaction_hash']!=b['transactionHash']):
        raise ValueError('Actual original source identity differs from receipt pool')
    return b


def report(pool):
    return {k:pool[k] for k in pool if k!='bindings'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT);args=parser.parse_args()
    pool=build(*load_inputs());encoded=(json.dumps(pool,separators=(',',':'))+'\n').encode()
    args.output.mkdir(parents=True,exist_ok=True);path=args.output/'bindings.json.gz'
    # Gzip filename empty and timestamp0: reproducible compressed evidence bytes.
    import io
    buffer=io.BytesIO()
    with gzip.GzipFile(filename='',fileobj=buffer,mode='wb',mtime=0) as target:target.write(encoded)
    compressed=buffer.getvalue()
    if path.exists() and path.read_bytes()!=compressed:
        raise ValueError('Do not overwrite changed frozen receipt pool')
    path.write_bytes(compressed)
    result=report(pool);result.update(poolLogicalSha256=digest(encoded),poolCompressedSha256=digest(compressed),
                                    poolLogicalBytes=len(encoded),poolCompressedBytes=len(compressed))
    (args.output/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
