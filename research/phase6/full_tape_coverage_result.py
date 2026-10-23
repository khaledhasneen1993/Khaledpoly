"""Independently reconstruct the full trade-identity census, offline only.

The 451 validated bindings plus ALL missing identities must reproduce the
original scan digest. Cached receipt presence is not a newly validated label.
"""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import zipfile

from research.phase6.full_tape_label_coverage import validate_reference_counts

ROOT = Path('research/experiments/full-tape-coverage-20261020/result')
ZIP_SHA = '882112d70db3b1926e235ebfd0a150fa5a3d6ffc40d0aac657358c9a2ed9a46e'
IDENTITY_FIELDS = {'seq','eventIndex','at','sourceMs','token','condition','side','price','size',
                   'publicTradeIdSha256','transactionHash','coverage'}
MISSING = {'MISSING_SCOPED_PAIR_LABEL','OTHER_MARKET_UNBOUND_NO_AGGREGATE_FALLBACK','UNKNOWN_MARKET_UNBOUND'}


def canonical(row):
    return (json.dumps(row,sort_keys=True,separators=(',',':'))+'\n').encode()


def read_archive(path):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ZIP_SHA:
        raise ValueError('Changed complete coverage artifact')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if (len(archive.infolist()) != 2 or set(archive.namelist()) != {'coverage.json','missing-observations.jsonl.gz'}
                or any(m.file_size > 16*1024*1024 for m in archive.infolist())):
            raise ValueError('Wrong bounded coverage artifact members')
        report = json.loads(archive.read('coverage.json'))
        compressed = archive.read('missing-observations.jsonl.gz')
        manifest = {m.filename:dict(bytes=m.file_size,sha256=hashlib.sha256(archive.read(m.filename)).hexdigest())
                    for m in archive.infolist()}
    return report, compressed, manifest


def verify(report, compressed, labels, inspection, frozen, freeze_sha):
    if (report['schema'] != 1 or report['scope'] != 'FULL_ORIGINAL_TAPE_LABEL_COVERAGE_ONLY_NOT_ACCOUNT_REPLAY'
            or report['logicalTapeSha256'] != frozen['logicalTapeSha256']
            or report['sourceRows'] != frozen['sourceRows'] or report['coverageFreezeSha256'] != freeze_sha
            or report['labelsSha256'] != frozen['labelsSha256']
            or hashlib.sha256((json.dumps(labels,indent=2)+'\n').encode()).hexdigest() != frozen['labelsSha256']
            or not report['completeOriginalChronologyChecked'] or not report['frameBoundariesChecked']
            or not report['originalInspectorCountsReproduced'] or not report['adapterScopeStillPartial']
            or report['decision'] != 'NO_GO'):
        raise ValueError('Original source/provenance/coverage scope differs')
    for field in ('uncoveredObservationsTreatedAsZero','publicAggregateFallbackAllowed','observedTradeRoutesFullyLabeled',
                  'fullAccountReplayAuthorized','receiptRequests','modelFillsCreated','netPnlRecomputed',
                  'independentPaperQualificationAllowed','liveAllowed'):
        if report[field] != (0 if field in ('receiptRequests','modelFillsCreated') else False):
            raise ValueError('No execution/qualification scope promotion: '+field)
    validate_reference_counts(report,inspection)
    if report['endMs'] - report['startMs'] != inspection['durationMs']:
        raise ValueError('Original source receive window differs')
    if hashlib.sha256(compressed).hexdigest() != report['missingObservationsCompressedSha256']:
        raise ValueError('Missing-observation compressed hash differs')
    pair=set(labels['coverage']['pair']); bound_conditions=[k for k,v in report['coverageByCondition'].items() if v.get('BOUND_CONSERVED_GROUP')]
    if len(bound_conditions)!=1 or report['coverageCounts'].get('KNOWN_TRANSACTION_AGGREGATE_SUPPRESSED',0)!=0:
        raise ValueError('This reconstruction requires original single-pair/no-suppressed artifact')
    condition=bound_conditions[0]
    bindings=[]; bound_keys=set(); known_tx=set()
    for b in labels['bindings']:
        row={k:b[k] for k in IDENTITY_FIELDS-{'condition','coverage'}}
        row.update(condition=condition,coverage='BOUND_CONSERVED_GROUP')
        key=(row['seq'],row['eventIndex'])
        if key in bound_keys or row['transactionHash'] in known_tx:
            raise ValueError('Duplicate validated binding')
        bound_keys.add(key);known_tx.add(row['transactionHash']);bindings.append(row)
    bindings.sort(key=lambda r:(r['seq'],r['eventIndex']))
    if len(bindings)!=report['consumedBindings'] or len(bindings)!=frozen['existingLabels']:
        raise ValueError('Validated binding count differs')
    missing=[]; digest=hashlib.sha256(); byte_count=0; counts=Counter(); by_condition=defaultdict(Counter)
    first={}; previous=(-1,-1); last_at=-1; transaction_counts=Counter(); tokens=defaultdict(set)
    with gzip.GzipFile(fileobj=io.BytesIO(compressed),mode='rb') as source:
        for line in source:
            byte_count+=len(line)
            if byte_count>256*1024*1024 or len(line)>1024*1024 or not line.endswith(b'\n'):
                raise ValueError('Oversized/incomplete missing identity stream')
            row=json.loads(line); key=(row['seq'],row['eventIndex']); status=row['coverage']; at=row['at']
            if (set(row)!=IDENTITY_FIELDS or canonical(row)!=line or key<=previous or key in bound_keys
                    or any(type(row[k]) is not int or row[k]<0 for k in ('seq','eventIndex','at','sourceMs'))
                    or row['seq']<1 or row['seq']>=report['sourceRows'] or at<last_at
                    or not report['startMs']<=at<=report['endMs'] or status not in MISSING
                    or row['side'] not in ('BUY','SELL') or row['transactionHash'] in known_tx
                    or not re.fullmatch('[0-9a-f]{64}',row['publicTradeIdSha256'])
                    or row['transactionHash'] is not None and not re.fullmatch('0x[0-9a-f]{64}',row['transactionHash'])):
                raise ValueError('Changed/duplicate/out-of-order missing identity')
            for name in ('price','size'):
                value=Decimal(str(row[name]))
                if not value.is_finite() or value<=0 or name=='price' and value>=1:
                    raise ValueError('Invalid original missing price/size')
            if (status=='MISSING_SCOPED_PAIR_LABEL') != (row['token'] in pair) or row['token'] in pair and row['condition']!=condition:
                raise ValueError('Missing pair/condition classification differs')
            previous=key;last_at=at;digest.update(line);counts[status]+=1;by_condition[row['condition']][status]+=1
            first.setdefault(status,row);tokens[row['condition']].add(row['token']);transaction_counts[row['transactionHash']]+=1;missing.append(row)
    if (len(missing)!=report['missingObservationCount'] or byte_count!=report['missingObservationBytes']
            or digest.hexdigest()!=report['missingObservationsLogicalSha256'] or first!=report['firstMissingByReason']):
        raise ValueError('Incomplete/changed missing stream count/hash/first identity')
    all_digest=hashlib.sha256(); sides=Counter(); counts['BOUND_CONSERVED_GROUP']=len(bindings)
    by_condition[condition]['BOUND_CONSERVED_GROUP']=len(bindings)
    combined=sorted(missing+bindings,key=lambda r:(r['seq'],r['eventIndex']))
    if any(a['at']>b['at'] for a,b in zip(combined,combined[1:])):
        raise ValueError('Reconstructed receive clock regressed')
    for row in combined:
        all_digest.update(canonical(row));sides[row['side']]+=1
    if (all_digest.hexdigest()!=report['allObservationIdentitiesSha256']
            or dict(counts)!=report['coverageCounts'] or dict(sides)!=report['sides']
            or {k:dict(v) for k,v in by_condition.items()}!=report['coverageByCondition']
            or len(combined)!=report['normalizedTradeObservations']):
        raise ValueError('Full original identity reconstruction/count conservation differs')
    return dict(scope='INDEPENDENTLY_RECONSTRUCTED_COMPLETE_TRADE_IDENTITIES_NOT_ACCOUNT',sourceRows=report['sourceRows'],
        marketsWithMetadata=report['marketCount'],marketsWithTrades=len(by_condition),originalTradeObservations=len(combined),
        validatedBindings=len(bindings),missingObservations=len(missing),missingUniqueTransactions=len(transaction_counts)-int(None in transaction_counts),
        missingRepeatedTransactionObservations=sum(n-1 for tx,n in transaction_counts.items() if tx is not None),
        missingObservationsWithoutTransaction=transaction_counts.get(None,0),allTradeIdentityDigestReproduced=True,
        originalInspectorCountsReproduced=True,coverageCounts=dict(counts),
        allObservationIdentitiesSha256=all_digest.hexdigest(),newReceiptRequests=0,modelFillsCreated=0,netPnlRecomputed=False,
        fullAccountReplayAuthorized=False,independentPaperQualificationAllowed=False,liveAllowed=False),missing,tokens


def reviewed_cache():
    from research.phase6.queue_aware_recovery_receipts import cached
    from research.phase6.queue_aware_recovery_result import load
    older=cached();_,recovery,_=load()
    if set(older)&set(recovery):
        raise ValueError('Duplicate reviewed receipt cache')
    return {**older,**recovery}


def cache_inventory(missing,tokens,cache):
    txs={row['transactionHash'] for row in missing if row['transactionHash'] is not None}
    present=txs&set(cache); absent=txs-set(cache)
    first_new=next((r for r in missing if r['transactionHash'] in absent),None)
    # Presence only: no rebinding, route coverage, volume or fills are inferred here.
    return dict(scope='REVIEWED_CACHED_RECEIPT_PRESENCE_NOT_NEW_VALIDATED_LABELS',reviewedCacheReceipts=len(cache),
        missingUniqueTransactions=len(txs),existingReceiptCandidates=len(present),
        existingReceiptCandidateObservations=sum(r['transactionHash'] in present for r in missing),
        missingTransactionsOutsideReviewedCache=len(absent),earliestUncachedObservation=first_new,
        observedTokenCandidatesByCondition={k:sorted(v) for k,v in sorted(tokens.items())},
        observedTokensAreNotMetadataPairProof=True,cachedPresenceIsNotCorroboration=True,
        collectionAuthorizedByThisReport=False,newReceiptRequests=0,newValidatedLabels=0,modelFillsCreated=0,netPnlRecomputed=False,
        fullAccountReplayAuthorized=False,independentPaperQualificationAllowed=False,liveAllowed=False)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--archive',type=Path,default=ROOT/'artifact.zip')
    parser.add_argument('--output',type=Path,default=ROOT);args=parser.parse_args()
    from research.phase6.mixed_replay_labels import export
    freeze_path=Path('research/phase6/full-tape-coverage-freeze.json');frozen=json.loads(freeze_path.read_text())
    inspection=json.loads(Path(frozen['referenceInspection']).read_text());labels=export()
    report,compressed,members=read_archive(args.archive)
    proof,missing,tokens=verify(report,compressed,labels,inspection,frozen,hashlib.sha256(freeze_path.read_bytes()).hexdigest())
    inventory=cache_inventory(missing,tokens,reviewed_cache())
    args.output.mkdir(parents=True,exist_ok=True);target=args.output/'artifact.zip'
    if args.archive.resolve()!=target.resolve():
        if target.exists():raise ValueError('Do not replace retained source artifact')
        shutil.copyfile(args.archive,target)
    manifest=dict(sourceCommit='2328229a352b54c68fa0b4fa6a142c9d2157e76c',runId=39342821835,jobId=118368228365,
        artifactId=12228709938,artifactBytes=target.stat().st_size,artifactZipSha256=ZIP_SHA,members=members,
        githubOfflineTests=288,githubOfflineTestSeconds=296.068,githubConclusion='success',liveAllowed=False)
    for name,value in [('coverage.json',report),('verification.json',proof),('reviewed-cache-inventory.json',inventory),('artifact-manifest.json',manifest)]:
        (args.output/name).write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps(dict(verification=proof,inventory={k:v for k,v in inventory.items() if k not in ('observedTokenCandidatesByCondition','earliestUncachedObservation')})),flush=True)


if __name__=='__main__':main()
