"""Verify bounded differential evidence; explicitly NOT authorization to skip unknown trades."""
import argparse
import json
from pathlib import Path

ROOT=Path('research/experiments/no-order-differential-20261020')
GUARDS={'SUBMITTED_WAITING','ACTIVATION_DUE','ACTIVE','CANCEL_PENDING','CANCEL_DUE','OTHER_TOKEN',
        'LEDGER_RESERVATION','NONZERO_HOLDING','PENDING_FOK','FAILED_SESSION','ENTRY_STOPPED','HALTED_LEDGER'}
EXCLUDED={'settlementAllocated','settlementComponents','settlementQueue','settlementUnused','settlementVenue'}

def verify(p):
    if (p['scope']!='PROOF_ONLY_SYNTHETIC_BOOK_CONTEXTS_OVER_ACTUAL643_IDENTITIES_NOT_MARKET_REPLAY'
            or p['poolLogicalSha256']!='c41eda69ffe03ed06835a9fac403401f0d68aa3fa92b019bf37d410a212ee231'
            or p['sourceIdentitiesSha256']!='27ac545988149c87bdfd4caee963100b7d10eb2808e6a74d82ae4b8321c65423'
            or p['actualIdentities']!=643 or p['matcherDifferentialCases']!=2572
            or p['distinctFutureContinuationCases']!=2572 or p['syntheticFutureFillEvents']<=0
            or len(p['guardRejections'])!=12 or set(p['guardRejections'])!=GUARDS
            or set(p['excludedMatchingFields'])!=EXCLUDED):raise ValueError('Changed bounded differential/guard/source evidence')
    for k in ('allOtherPrivateMatchingFieldsCompared','repeatedComponentFutureDivergenceDetected',
              'legacyPublicPrintBookkeepingDivergenceDetected','knownVenueVolumeNotEquivalentToClockOnly',
              'sourceIdentityAndGlobalTransactionUniquenessStillRequired'):
        if p[k] is not True:raise ValueError('Missing counterexample/state comparison constraint')
    for k in ('fullMatchingStateEquivalent','sessionLevelEquivalenceProven','runtimeOptimizationImplemented',
              'unknownObservationsSkipped','fullAccountReplayAuthorized','marketNetPnlRecomputed','independentPaperQualificationAllowed','liveAllowed'):
        if p[k] is not False:raise ValueError('Differential proof cannot authorize runtime/account/qualification claims')
    session=p['separateSyntheticSessionDifferential']
    if (session['scope']!='SYNTHETIC_SESSION_LEDGER_AUDIT_CONTINUATION_NOT_MARKET'
            or session['comparisonPoints']!=3 or session['futureOpenOrders']!=2):raise ValueError('Synthetic session scope/count differs')
    for k in ('wholeReportExceptTwoExplicitDiagnosticsEqual','wholeLedgerAndAuditEqual','futureEntryAndActivationEqual','noOrderPredicateRejectedAfterEntry'):
        if session[k] is not True:raise ValueError('Synthetic future session/ledger/audit guard differs')
    return dict(scope='VERIFIED_LIMITED_NO_ORDER_DIFFERENTIAL_NOT_RUNTIME_AUTHORIZATION',
        matcherCases=2572,distinctFutureContinuations=2572,guardRejections=12,syntheticSessionComparisonPoints=3,
        repeatedComponentAndPublicPrintCounterexamplesVerified=True,
        requiresFullSourceIdentityIndexAndGlobalTransactionUniqueness=True,
        requiresAtomicSessionGuardAndSeparateUnknownVolumeAccounting=True,
        runtimeOptimizationAuthorized=False,original628StillUnresolved=True,
        marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args()
    print(json.dumps(verify(json.loads((a.root/'no-order-proof.json').read_text())),indent=2))
