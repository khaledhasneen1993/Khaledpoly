"""Verify scoped integration proof or diagnose both frozen original development runs."""
import argparse
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path('research/experiments/indexed-execution-20261020')
PREFIX_SHA='2842d45d1fc041fd7c1af8a6ed44403e9c0914e59eaf9c8e4b0515b504c6de8c'
CHECKS=set('ORIGINAL97_KNOWN_AND628_ATOMIC_CLOCK UNKNOWN_VENUE_QUANTITY_NOT_ZERO_OR_PUBLIC PREFIX_CANNOT_CERTIFY_FULL_SOURCE_OR_POOL EXPIRY_AFTER_IDENTITY_AND_REAL_POOL_CONSUMPTION EXPOSURE_HALTS_CANCELS_BLOCKS_CONTINUATION MUTATION_AFTER_EXPIRY_HALTS_CANCELS_BLOCKS_CONTINUATION DUPLICATE_HALTS_CANCELS_BLOCKS_CONTINUATION MISSING_PREFIX_HALTS_CANCELS_BLOCKS_CONTINUATION FRAME_INDEX_HALTS_CANCELS_BLOCKS_CONTINUATION'.split())


def verify(proof):
    if (proof['scope']!='TWO_ORIGINAL_PREIMAGES_IN_SYNTHETIC_SESSION_NOT_ORIGINAL_TAPE_REPLAY'
            or proof['prefixSha256']!=PREFIX_SHA or len(proof['checks'])!=len(CHECKS) or set(proof['checks'])!=CHECKS
            or proof['allFixtureAccountsUnchanged'] is not True or proof['identityAndAtomicWitnessIntegrated'] is not True
            or proof['unknownVenueQuantity']!='UNKNOWN_NOT_ZERO'):
        raise ValueError('Changed integration source/guards/atomic proof')
    for k in ('fullOriginalTapeReplayed','completeAccountComparisonPerformed','marketNetPnlRecomputed','independentPaperQualificationAllowed','liveAllowed'):
        if proof[k] is not False:raise ValueError('Synthetic envelope cannot prove original replay/profit')
    for name in ('ordinary','expired'):
        r=proof[name];index=r['sourceIndex'];pool=r['realReceiptPool']
        if (r['failed'] is not False or r['unknownVenueQuantity']!='UNKNOWN_NOT_ZERO'
                or r['aggregateFallbackAllowed'] is not False or index['consumedOriginalPreimages']!=2
                or index['failed'] is not False or index['subsetPreimageTestOnly'] is not False
                or index['completeOriginalConsumption'] is not False or pool['consumedBindings']!=1
                or pool['bindings']!=643 or pool['actualComponents']!=1532
                or r['unknownAtomicClockObservations']!=1 or D(str(r['unknownObservedPublicSizeNotVenueQuantity']))!=12):
            raise ValueError('Missing source/pool consumption or unknown venue scope')
    if (proof['ordinary']['knownAppliedObservations']!=1 or proof['ordinary']['knownExpiredObservations']!=0
            or proof['expired']['knownAppliedObservations']!=0 or proof['expired']['knownExpiredObservations']!=1
            or proof['expired']['unknownExpiredAtomicClockObservations']!=1
            or D(str(proof['expired']['knownExpiredComponentQuantityNotApplied']))!=200):
        raise ValueError('Expiry accounting changed')
    return dict(scope='VERIFIED_INDEXED_INTEGRATION_IN_SYNTHETIC_ENVELOPE_NOT_MARKET_RESULT',originalPrefixIdentities=2,
                integrationChecks=len(CHECKS),identityAndAtomicWitnessIntegrated=True,
                fullOriginalTapeReplayed=False,marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False)


def replay(input_root,inputs,classpath,output):
    from research.phase6.full_runner_diagnosis import STORED_SHA,digest
    frozen=json.loads(Path('research/phase6/indexed-execution-freeze.json').read_bytes())
    for p,sha in frozen['inputsSha256'].items():
        if digest(p)!=sha:raise ValueError('Changed frozen indexed replay dependency '+p)
    tapes=list(Path(input_root).rglob('events.jsonl.gz'))
    if len(tapes)!=1 or digest(tapes[0])!=STORED_SHA:raise ValueError('Unchanged original development recording required')
    out=Path(output);out.mkdir(parents=True,exist_ok=False);inputs=Path(inputs);results={}
    cfg=json.loads(Path('research/phase2/research-config.json').read_bytes())
    for profile in ('baseline','candidate'):
        target=out/profile
        with (out/(profile+'.log')).open('w') as log:
            proc=subprocess.run(['java','-Xmx1g','-cp',classpath,'com.polybot.hft.paper.IndexedReplaySupport',
                str(tapes[0]),str(target),'research/phase2/research-config.json',str(inputs/'pool/pool.json'),
                str(inputs/'source/complete-index.jsonl'),profile],stdout=log,stderr=subprocess.STDOUT,timeout=1200)
        if proc.returncode==0:
            if (target/'failure.json').exists():raise ValueError('Successful replay with failure report')
            report=json.loads((target/'report.json').read_bytes());labels=report['settlementExperiment']
            if (report['rows']!=6163831 or report['inputSha256']!=STORED_SHA
                    or labels['failed'] is not False or labels['sourceIndex']['completeOriginalConsumption'] is not True
                    or labels['sourceIndex']['consumedOriginalPreimages']!=16317
                    or labels['realReceiptPool']['consumedBindings']!=643):raise ValueError('Incomplete original replay promoted')
            results[profile]=dict(status='COMPLETE_INDEXED_DEVELOPMENT_REPLAY_NOT_INDEPENDENT',
                netRealizedPnl=report['netRealizedPnl'],feesAndSettlementCosts=report['feesAndSettlementCosts'],
                sourceConsumed=16317,unknownAtomicClockObservations=labels['unknownAtomicClockObservations'])
        else:
            if not (target/'failure.json').exists() or (target/'report.json').exists():raise ValueError('Unreported original replay failure; inspect log')
            failure=json.loads((target/'failure.json').read_bytes());labels=failure['labels'];report=failure['sessionAfterSuspension'];attempt=labels['lastAttemptedOriginalObservation']
            if (labels['failed'] is not True or report['halted'] is not True or report['openOrderCount']!=0
                    or failure['candidateFrozenPoliciesEnabled'] is not (profile=='candidate')):raise ValueError('Unsafe failure/profile')
            results[profile]=dict(status='INCOMPLETE_FAIL_CLOSED_NOT_PNL_RESULT',row=failure['row'],
                lastOriginalSequence=attempt.get('seq'),errors=failure['errors'],
                sourceConsumed=labels['sourceIndex']['consumedOriginalPreimages'],
                knownApplied=labels['knownAppliedObservations'],unknownAtomicClockObservations=labels['unknownAtomicClockObservations'],
                marketNetPnlRecomputed=False)
        if any(D(str(report['configuration'][k]))!=D(str(v)) for k,v in cfg.items()):raise ValueError('Frozen execution/risk/fee configuration changed')
        if labels['unknownVenueQuantity']!='UNKNOWN_NOT_ZERO' or labels['aggregateFallbackAllowed'] is not False:raise ValueError('Unknown venue scope promoted')
    result=dict(scope='SAME_FROZEN_ORIGINAL_DEVELOPMENT_INDEXED_EXECUTION_DIAGNOSTIC_NOT_QUALIFICATION',
        sourceStoredSha256=STORED_SHA,results=results,completeAccountComparisonPerformed=all(r['status'].startswith('COMPLETE_INDEXED_') for r in results.values()),
        independentPaperQualificationAllowed=False,liveAllowed=False,decision='NO_GO')
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--proof',type=Path);p.add_argument('--input-root');p.add_argument('--inputs');p.add_argument('--classpath');p.add_argument('--output');a=p.parse_args()
    print(json.dumps(verify(json.loads(a.proof.read_bytes())) if a.proof else replay(a.input_root,a.inputs,a.classpath,a.output),indent=2))
