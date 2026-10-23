"""Bounded temporal evidence, not synthetic fills promoted to market performance."""
import argparse
import hashlib
import json
from pathlib import Path

GUARDS=set('ACTIVATION_DUE_EQUAL ACTIVATION_PAST_DUE ACTIVE SELL_PENDING CANCEL_PENDING CANCEL_DUE SOURCE_FUTURE SOURCE_NEGATIVE CLOCK_REGRESSION RESERVATION_MISSING ORPHAN_RESERVATION RESERVATION_MISMATCH HOLDING PENDING_FOK UNHEDGED_TIMER SESSION_FAILED ENTRY_STOPPED HALTED PERSISTENCE_FAILED CHECKPOINT_CLOSED LEDGER_CLOSED EXTERNAL_MODE RECOVERED_CHECKPOINT'.split())
CHECKS={f'ORIGINAL628_PENDING_AGE_{a}_NO_FILL_NO_COMPLETION' for a in (20,54,249)}|{f'{m}_HALTS_CANCELS_BLOCKS_CONTINUATION' for m in ('DUE','ACTIVE','CANCEL_PENDING','RESERVATION_MISSING','MUTATED_IDENTITY')}


def require(condition,message):
    if not condition:raise ValueError(message)


def verify(root):
    root=Path(root);p=json.loads((root/'preactivation-proof.json').read_bytes());s=json.loads((root/'preactivation-session-proof.json').read_bytes())
    require(p['scope']=='SYNTHETIC_PRE_ACTIVATION_CONTEXTS_OVER_ACTUAL643_COMPONENTS_NOT_MARKET','Changed proof scope')
    require(p['actualIdentities']==643 and p['pendingDifferentials']==5144 and p['distinctFutureContinuations']==5144 and p['syntheticFutureFillEvents']==128,'Incomplete differential evidence')
    require(len(p['rejectionGuards'])==len(GUARDS) and set(p['rejectionGuards'])==GUARDS,'Incomplete temporal guards')
    require(p['activationMsUnchanged']==250 and p['queueMultiplierUnchanged']==2 and p['pendingAgeContextsMs']==[0,20,54,249] and p['sourceTimeContexts']==['BEFORE_SUBMIT','LATEST_AT_ARRIVAL'],'Changed temporal parameters')
    for k in ('allNonSettlementPrivateMatchingFieldsCompared','repeatedComponentFutureDivergenceVerified','oldEmptyOrderGuardUnchanged'):require(p[k] is True,'Missing differential invariant '+k)
    require(p['fullMatchingStateEquivalent'] is False,'Settlement bookkeeping is not equivalent')
    require(s['scope']=='TWO_ORIGINAL_PREIMAGES_SYNTHETIC_PENDING_SESSION_NOT_TAPE_REPLAY' and len(s['checks'])==8 and set(s['checks'])==CHECKS and s['allFixtureAccountsUnchanged'] is True,'Incomplete session guards')
    require(len(s['safeReports'])==3,'Missing synthetic pending ages')
    for r in s['safeReports']:
        require(r['temporalWitnessProfile']=='PRE_ACTIVATION0' and r['failed'] is False and r['unknownPreActivationClockObservations']==1 and r['unknownAtomicClockObservations']==1 and r['knownAppliedObservations']==1,'Changed execution routes')
        require(r['sourceIndex']['consumedOriginalPreimages']==2 and r['sourceIndex']['completeOriginalConsumption'] is False and r['sourceIndex']['failed'] is False and r['realReceiptPool']['consumedBindings']==1 and r['unknownVenueQuantity']=='UNKNOWN_NOT_ZERO' and r['aggregateFallbackAllowed'] is False,'Changed identity/pool/unknown scope')
    for proof in (p,s):
        for flag in ('originalTapeReplayed','marketNetPnlRecomputed','independentPaperQualificationAllowed','liveAllowed'):require(proof[flag] is False,'Synthetic evidence promoted '+flag)
    return dict(scope='VERIFIED_BOUNDED_PRE_ACTIVATION0_NOT_ORIGINAL_REPLAY',pendingDifferentials=5144,distinctFutureContinuations=5144,temporalGuards=23,sessionChecks=8,marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False)


def verify_inputs():
    frozen=json.loads(Path('research/phase6/preactivation-freeze.json').read_bytes())
    for path,sha in frozen['inputsSha256'].items():require(hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha,'Changed temporal input '+path)


def replay(args):
    verify_inputs();verify(args.proof_root)
    from research.phase6.indexed_execution_result import replay as original
    out=Path(args.output);result=original(args.input_root,args.inputs,args.classpath,out)
    for name,r in result['results'].items():
        path=out/name/('report.json' if r['status'].startswith('COMPLETE_') else 'failure.json');raw=json.loads(path.read_bytes())
        labels=raw['settlementExperiment'] if r['status'].startswith('COMPLETE_') else raw['labels']
        require(labels['temporalWitnessProfile']=='PRE_ACTIVATION0','Wrong generated classpath')
        r['unknownPreActivationClockObservations']=labels['unknownPreActivationClockObservations']
    result['temporalWitnessProfile']='PRE_ACTIVATION0';(out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--proof-root',required=True);p.add_argument('--input-root');p.add_argument('--inputs');p.add_argument('--classpath');p.add_argument('--output');a=p.parse_args()
    print(json.dumps(replay(a) if a.input_root else verify(a.proof_root),indent=2))
