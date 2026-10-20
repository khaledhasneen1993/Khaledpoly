"""Verify synthetic atomic safety proof; never promote to execution/profit."""
import argparse
import json
from pathlib import Path

ROOT=Path('research/experiments/atomic-guard-20261020')
GUARDS=set('SUBMITTED ACTIVATION_DUE ACTIVE CANCEL_PENDING CANCEL_DUE OTHER_TOKEN LEDGER_RESERVATION HOLDING NONZERO_BASIS PENDING_FOK UNHEDGED_TIMER SESSION_FAILED ENTRY_STOPPED EXTERNAL_MODE RECOVERED_CHECKPOINT LEDGER_HALTED LEDGER_FAILED LEDGER_CLOSED CHECKPOINT_CLOSED CHECKPOINT_WRITE_FAILED LEDGER_WRITE_FAILED RESTORED_LEDGER'.split())


def verify(proof):
    if (proof['scope']!='SYNTHETIC_ATOMIC_EMPTY_EXPOSURE_GUARD_NOT_EXECUTION'
            or len(proof['rejectionGuards'])!=len(GUARDS) or set(proof['rejectionGuards'])!=GUARDS):
        raise ValueError('Changed synthetic guard scope/complete rejection set')
    for k in ('sessionLedgerMatcherCheckpointLocksHeld','fourConcurrentMonitorUsersBlockedThenReleased',
              'witnessInvalidAfterReturnOrException','crossThreadWitnessRejected',
              'guardDoesNotAdvanceMatcherOrAccount','persistentWriteFailuresAndClosedStateRejected',
              'atomicGuardImplementedInIsolatedBuild'):
        if proof[k] is not True:raise ValueError('Missing atomic lifetime/health evidence '+k)
    for k in ('defaultCoreModified','identityConsumerIntegrated','runtimeExecutionSkipImplemented',
              'originalTapeReplayed','marketNetPnlRecomputed','independentPaperQualificationAllowed','liveAllowed'):
        if proof[k] is not False:raise ValueError('Guard proof cannot authorize execution/profit '+k)
    return dict(scope='VERIFIED_SYNTHETIC_ATOMIC_GUARD_NOT_RUNTIME',rejectionGuards=len(GUARDS),
                atomicGuardImplementedInIsolatedBuild=True,identityConsumerIntegrated=False,
                original628StillUnresolved=True,runtimeExecutionSkipImplemented=False,
                marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--proof',type=Path,default=ROOT/'atomic-guard-proof.json');a=p.parse_args()
    print(json.dumps(verify(json.loads(a.proof.read_bytes())),indent=2))
