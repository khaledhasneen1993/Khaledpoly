"""Prepare exact native identity inputs and independently verify bounded parity.

No new source scan/RPC. The full index is reconstructed, not copied from a
synthetic tape. This does not authorize no-order skips or execution.
"""
import argparse
import hashlib
import json
from pathlib import Path

from research.phase6.complete_source_index import reconstruct, IDENTITIES_SHA
from research.phase6.full_tape_coverage_result import canonical

ROOT = Path('research/experiments/native-source-index-20261020')
SOURCE_IDENTITIES_SHA = '27ac545988149c87bdfd4caee963100b7d10eb2808e6a74d82ae4b8321c65423'
GUARDS = {
    'SUBSET_CANNOT_CERTIFY_COMPLETE', 'FAILED_FINALIZATION_NO_CONTINUATION',
    'WRONG_SEQUENCE', 'WRONG_FRAME_INDEX', 'WRONG_ARRIVAL', 'WRONG_SOURCE',
    'WRONG_TOKEN', 'WRONG_SIDE', 'WRONG_PRICE', 'WRONG_SIZE', 'PRICE_NAN',
    'SIZE_BOOLEAN', 'SOURCE_BOOLEAN', 'SOURCE_FRACTIONAL', 'RAW_BYTES_WHITESPACE',
    'RAW_TRANSACTION_MUTATION', 'RAW_MISSING', 'RAW_OVERSIZED',
    'DUPLICATE_CONSUMPTION', 'REVERSED_CONSUMPTION',
    'FULL_MODE_NO_MISSING_OBSERVATION', 'EMPTY_CANNOT_CERTIFY_COMPLETE',
    'CHANGED_FULL_CENSUS_BYTES',
}


def prepare(output):
    from research.phase6.expanded_receipt_pool import build, identities
    rows, _, proof = reconstruct()
    index = b''.join(canonical(row) for row in rows)
    source = (json.dumps(identities(build()), separators=(',', ':')) + '\n').encode()
    if hashlib.sha256(index).hexdigest() != IDENTITIES_SHA or hashlib.sha256(source).hexdigest() != SOURCE_IDENTITIES_SHA:
        raise ValueError('Changed original census/preimages')
    out = Path(output); out.mkdir(parents=True, exist_ok=False)
    (out/'complete-index.jsonl').write_bytes(index)
    (out/'source-identities.json').write_bytes(source)
    return dict(index=proof, sourceIdentitiesSha256=SOURCE_IDENTITIES_SHA,
                indexBytes=len(index), nativeInputIsNotExecutionTape=True)


def verify(proof):
    if (proof['scope'] != 'NATIVE_COMPLETE_INDEX_WITH643_PREIMAGE_PARITY_NOT_EXECUTION'
            or proof['indexLogicalSha256'] != IDENTITIES_SHA
            or proof['sourceIdentitiesSha256'] != SOURCE_IDENTITIES_SHA
            or proof['originalIdentities'] != 16317 or proof['actualRawPreimagesMatched'] != 643
            or proof['unconsumedOriginalPreimages'] != 15674):
        raise ValueError('Changed native original source/counts')
    flags = ('runtimeOptimizationImplemented', 'atomicSessionGuardImplemented', 'originalTapeReplayed',
             'modelFillsCreated', 'marketNetPnlRecomputed', 'fullAccountReplayAuthorized',
             'independentPaperQualificationAllowed', 'liveAllowed')
    if any(proof[k] is not False for k in flags):
        raise ValueError('Identity parity cannot authorize execution/net/qualification')
    if (len(proof['rejectionGuards']) != len(GUARDS) or set(proof['rejectionGuards']) != GUARDS
            or any(proof[k] is not True for k in ('allRejectionsPoisonConsumption',
                       'fullModeFirstOriginal97Matched', 'fullModeMissing628Rejected'))):
        raise ValueError('Missing native rejection/sequence/poison guards')
    subset = proof['preimageSubsetBeforeRejectedFinalization']
    if (subset['originalIdentities'] != 16317 or subset['consumedOriginalPreimages'] != 643
            or subset['identitiesSha256'] != IDENTITIES_SHA or subset['failed'] is not False
            or subset['subsetPreimageTestOnly'] is not True
            or any(subset[k] is not False for k in ('completeOriginalConsumption',
                                  'settlementRoutesValidatedByIndex', 'runtimeSkipAuthorized'))):
        raise ValueError('Subset is not complete execution/settlement proof')
    return dict(scope='INDEPENDENTLY_VERIFIED_NATIVE_SOURCE_IDENTITY_PARITY_ONLY',
                originalIndexIdentities=16317, actualPreimagesMatched=643,
                rejectionGuards=len(GUARDS), original628ExecutionStillUnresolved=True,
                runtimeSkipAuthorized=False, marketNetPnlRecomputed=False,
                independentPaperQualificationAllowed=False, liveAllowed=False)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--prepare', type=Path); p.add_argument('--verify', type=Path)
    args = p.parse_args()
    if bool(args.prepare) == bool(args.verify):
        p.error('Exactly one of --prepare or --verify required')
    print(json.dumps(prepare(args.prepare) if args.prepare else verify(json.loads(args.verify.read_bytes())), indent=2))
