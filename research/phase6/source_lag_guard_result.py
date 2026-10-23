"""Validate scoped atomic evidence before ONE frozen same-source development comparison."""
import argparse
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path

ROOT=Path('research/experiments/source-lag-guard-20261020')
GUARDS=set('SOURCE_PLUS_ONE SOURCE_FUTURE SOURCE_NEGATIVE MATCHER_CLOCK_REGRESSION SESSION_CLOCK_REGRESSION CANCEL_PENDING CANCEL_DUE SELL_PENDING OLDER_ORDER_ELIGIBLE MISSING_RESERVATION ORPHAN_RESERVATION RESERVATION_PRICE RESERVATION_SIZE HOLDING NONZERO_BASIS PENDING_FOK UNHEDGED SESSION_FAILED ENTRY_STOPPED HALTED LEDGER_FAILED CHECKPOINT_CLOSED LEDGER_CLOSED EXTERNAL_MODE RECOVERED_CHECKPOINT CHECKPOINT_WRITE_FAILED LEDGER_WRITE_FAILED NEGATIVE_AVAILABLE_CASH RESTORED_LEDGER'.split())
CHECKS={x+'_NO_FILL_NO_COMPLETION' for x in ('SOURCE_EQUAL','SOURCE_BEFORE')}|{x+'_HALTS_CANCELS_BLOCKS_CONTINUATION' for x in ('SOURCE_PLUS_ONE','OLDER_ORDER_ELIGIBLE','CANCEL_PENDING','RESERVATION_MISSING','MUTATED_IDENTITY')}


def require(x,why):
    if not x:raise ValueError(why)


def verify_inputs():
    frozen=json.loads(Path('research/phase6/source-lag-guard-freeze.json').read_bytes())
    for p,sha in frozen['inputsSha256'].items():require(hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha,'Changed source-lag guard input '+p)


def verify(p):
    require(p['scope']=='GENERATED_SOURCE_LAG0_ATOMIC_AND_ORIGINAL_PREIMAGE_SYNTHETIC_SESSION_PROOF_NOT_TAPE','Wrong guard scope')
    require(p['nativePredicateCorrespondenceCases']==1929 and len(p['rejectionGuards'])==29 and set(p['rejectionGuards'])==GUARDS and len(p['integrationChecks'])==7 and set(p['integrationChecks'])==CHECKS,'Incomplete native guard evidence')
    for k in ('fourMonitorsHeldThroughCallback','fourConcurrentUsersBlockedThenReleased','escapedCrossThreadAndExceptionWitnessRejected','guardAloneDoesNotAdvanceOrMutateAccount','oldWitnessMethodsUnchanged','atomicSessionWitnessImplementedInGeneratedBuild','unknownVenueQuantityRemainsUnknown'):require(p[k] is True,'Missing safety invariant '+k)
    for k in ('originalCoreModified','originalTapeReplayed','completeAccountComparisonPerformed','marketNetPnlRecomputed','independentPaperQualificationAllowed','liveAllowed'):require(p[k] is False,'Synthetic guard proof promoted '+k)
    require(len(p['safeIndexedSessionReports'])==2,'Missing indexed source timing cases')
    for r in p['safeIndexedSessionReports']:
        require(r['temporalWitnessProfile']=='SOURCE_LAG0' and r['failed'] is False and r['knownAppliedObservations']==1 and r['unknownAtomicClockObservations']==1 and r['unknownSourceLagClockObservations']==1 and r['unknownSourceLagActiveClockObservations']==1 and r['unknownVenueQuantity']=='UNKNOWN_NOT_ZERO' and r['aggregateFallbackAllowed'] is False,'Wrong indexed route/volume scope')
        require(r['sourceIndex']['consumedOriginalPreimages']==2 and r['sourceIndex']['completeOriginalConsumption'] is False and r['sourceIndex']['subsetPreimageTestOnly'] is False and r['realReceiptPool']['consumedBindings']==1,'Changed original prefix consumption')
    require(len(p['frontierEnvelopes'])==2,'Both exact frontier preimages required')
    for r,profile,seq,queues in zip(p['frontierEnvelopes'],('candidate','baseline'),(8739,82880),((D('1182.3'),D(180)),(D(0),D(0)))):
        idx=r['sourceIdentityReport'];require(r['profile']==profile and r['sequence']==seq and r['accountUnchanged'] is True and r['originalTapeReplayed'] is False and idx['subsetPreimageTestOnly'] is True and idx['consumedOriginalPreimages']==1 and idx['completeOriginalConsumption'] is False,'Frontier subset must not certify original replay')
        require(len(r['syntheticOrderDiagnostics'])==2,'Missing frontier orders')
        for o,q in zip(r['syntheticOrderDiagnostics'],queues):require(D(str(o['initialQueueAhead']))==q==D(str(o['remainingQueueAhead'])) and D(str(o['remainingShares']))==5 and D(str(o['eligiblePrintVolume']))==0 and o['terminalMs'] is None,'Changed synthetic frontier queue/account')
    return dict(scope='VERIFIED_GENERATED_SOURCE_LAG0_ATOMIC_SYNTHETIC_INTEGRATION_NOT_ORIGINAL_REPLAY',rejectionGuards=29,integrationChecks=7,nativePredicateCorrespondenceCases=1929,originalFrontierSyntheticEnvelopes=2,atomicSessionWitnessImplementedInGeneratedBuild=True,originalTapeReplayed=False,marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False)


def replay(args):
    verify_inputs();verify(json.loads((Path(args.proof_root)/'source-lag-guard-proof.json').read_bytes()))
    from research.phase6.indexed_execution_result import replay as original
    out=Path(args.output);result=original(args.input_root,args.inputs,args.classpath,out)
    for profile,r in result['results'].items():
        complete=r['status'].startswith('COMPLETE_');path=out/profile/('report.json' if complete else 'failure.json');data=json.loads(path.read_bytes())
        labels=data['settlementExperiment'] if complete else data['labels'];require(labels['temporalWitnessProfile']=='SOURCE_LAG0','Wrong generated source-lag classpath')
        for k in ('unknownSourceLagClockObservations','unknownSourceLagActiveClockObservations'):r[k]=labels[k]
    result['temporalWitnessProfile']='SOURCE_LAG0';(out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--proof-root',required=True);p.add_argument('--input-root');p.add_argument('--inputs');p.add_argument('--classpath');p.add_argument('--output');a=p.parse_args()
    print(json.dumps(replay(a) if a.input_root else verify(json.loads((Path(a.proof_root)/'source-lag-guard-proof.json').read_bytes())),indent=2))
