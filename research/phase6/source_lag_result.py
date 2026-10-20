"""Strict bounded proof verifier. Does NOT authorize a runtime/session shortcut."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path('research/experiments/source-lag-20261020')
CONTEXTS=['ACTIVE_SOURCE_MINUS66','ACTIVE_SOURCE_EQUAL','DUE_AT_ARRIVAL_EQUAL','DELAYED_ACTIVATION_EQUAL','TWO_ORDERS_OLDEST_CUTOFF','CANCEL_DUE_ACTIVATION_TIE','CANCEL_PENDING','STALE_ACTIVE_BOOK']
GUARDS=set('SOURCE_AFTER_ACTUAL_ACTIVATION FUTURE_SOURCE NEGATIVE_SOURCE CLOCK_REGRESSION OLDER_ORDER_ELIGIBLE_DESPITE_NEWER_ORDER CANCEL_PENDING CANCEL_DUE SELL_EXPOSURE EMPTY_NOT_TEMPORAL_EXPOSURE'.split())


def require(value,why):
    if not value:raise ValueError(why)


def verify_inputs():
    spec=json.loads(Path('research/phase6/source-lag-proof-freeze.json').read_bytes())
    for path,sha in spec['inputsSha256'].items():require(hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha,'Changed bounded source-lag input '+path)
    require(spec['runtimeShortcutAuthorized'] is False and spec['originalTapeReplayAuthorized'] is False,'Proof freeze cannot authorize runtime')


def verify(p):
    require(p['scope']=='SYNTHETIC_SOURCE_LAG_DIFFERENTIAL_OVER_ACTUAL643_COMPONENTS_NOT_RUNTIME_AUTHORIZATION','Changed proof scope')
    require(p['originalIdentities']==643 and p['matcherDifferentials']==5144 and p['distinctFutureContinuations']==5144 and p['syntheticFutureFillEvents']==111,'Incomplete exact matcher evidence')
    require(p['contexts']==CONTEXTS and len(p['proofPredicateRejections'])==9 and set(p['proofPredicateRejections'])==GUARDS,'Incomplete contexts/guard set')
    require(p['activationMsUnchanged']==250 and p['queueMultiplierUnchanged']==2,'Changed activation/queue')
    for k in ('allNonSettlementPrivateMatchingFieldsCompared','runtimeRequiresAllOrdersActualActivationCutoff','globalComponentUniquenessStillRequired'):require(p[k] is True,'Missing invariant '+k)
    require(p['counterexamples']==dict(afterActivationOneMillisecondProducesSyntheticFill=True,newestOrderCutoffWouldMissOlderEligibleOrder=True,repeatedComponentFutureDivergenceVerified=True),'Missing required unsafe counterexamples')
    for k in ('fullMatchingStateEquivalent','newAtomicSessionGuardImplemented','newRuntimeShortcutEnabled','originalTapeReplayed','completeAccountComparisonPerformed','marketNetPnlRecomputed','independentPaperQualificationAllowed','liveAllowed'):require(p[k] is False,'Synthetic proof promoted '+k)
    return dict(scope='VERIFIED_BOUNDED_SOURCE_LAG_MATH_NOT_SESSION_OR_RUNTIME_AUTHORIZATION',matcherDifferentials=5144,distinctFutureContinuations=5144,proofPredicateRejections=9,allOrderAndActualActivationCounterexamplesVerified=True,newAtomicSessionGuardImplemented=False,newRuntimeShortcutEnabled=False,marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False)


def original_frontier_context():
    from research.phase6.preactivation_diagnosis import load
    previous=load();rows={}
    for profile,r in previous['results'].items():
        require(r['frontierOrdersActiveButTradeSourceBeforeTheirActivation'] is True,'Not the proven source-lag frontier')
        rows[profile]=dict(sequence=r['sequence'],arrivalMs=r['arrivalMs'],sourceMs=r['sourceMs'],actualActivatedMs=[o['activatedMs'] for o in r['orders']],actualInitialQueues=[o['initialQueueAhead'] for o in r['orders']],runtimeShortcutStillBlocked=True)
    return dict(scope='REVALIDATED_PREVIOUS_ORIGINAL_FRONTIERS_NOT_NEW_REPLAY',previousRun=previous['runId'],results=rows,originalTapeReplayed=False,marketNetPnlRecomputed=False,liveAllowed=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--proof',type=Path,default=ROOT/'source-lag-proof.json');p.add_argument('--original-context',action='store_true');a=p.parse_args()
    verify_inputs();print(json.dumps(original_frontier_context() if a.original_context else verify(json.loads(a.proof.read_bytes())),indent=2))
