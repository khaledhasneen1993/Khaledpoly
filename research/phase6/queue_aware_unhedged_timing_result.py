"""Reproduce conditional wait/cancel evidence; suppressed trades remain unknown."""
from decimal import Decimal as D
import gzip
import hashlib
import json
from research.phase6.queue_aware_causal import QROOT
from research.phase6.queue_aware_pair_prefix import prepare
from research.phase6.queue_aware_pair_prefix_result import saved as verify_prefix
from research.phase6.queue_aware_unhedged_timing import timeline

ROOT=QROOT/'unhedged-timing-result'


def verify(evidence,report,artifact):
    verify_prefix();context,manifest,seed=prepare();expected=timeline(context,manifest,seed)
    if json.loads(json.dumps(expected,default=str))!=evidence:raise ValueError('Changed source-bound conditional wait/cancel reconstruction')
    for name,obj in [('context.json.gz',context),('evidence.json',evidence)]:
        raw=(json.dumps(obj,default=str,separators=(',',':'))+'\n').encode()
        if name.endswith('.gz'):raw=gzip.compress(raw,mtime=0)
        member=artifact['members'][name]
        if len(raw)!=member['bytes'] or hashlib.sha256(raw).hexdigest()!=member['sha256']:raise ValueError('Changed timing artifact input '+name)
    if (report['scope']!='CONDITIONAL_NO_FURTHER_ALLOCATIONS_WAIT_CANCEL_NOT_ACCOUNT'
            or not report['allTradeVolumeSuppressed'] or not report['furtherCounterpartAllocationsSuppressed']
            or not report['accountRiskAndOtherMarketsOmitted'] or report['fillsCreated']!=0 or report['candidateAccountSimulated']
            or report['netPnlRecomputed'] or report['independentPaperQualificationAllowed'] or report['liveAllowed']):raise ValueError('Wrong conditional timing scope')
    checks=[dict(originalSequence=c['originalSequence'],at=c['at'],waitMs=c['waitMs'],reason=c['reason']) for c in evidence['checks']]
    if report['actualPairPolicyChecks']!=checks or report['actualCancelAck']!=evidence['expectedFirstDueEngineEvent']:
        raise ValueError('Actual wait/cancel callback/ack differs')
    prior=json.loads((QROOT/'pair-prefix-result/report.json').read_text(),parse_float=D)['diagnostics'][1]
    diag=report['diagnostic'];ack=evidence['expectedFirstDueEngineEvent']['at']
    for key in ['token','buy','price','submittedMs','activationDueMs','activatedMs','initialQueueAhead','remainingQueueAhead','remainingShares']:
        if diag[key]!=prior[key]:raise ValueError('Actual unchanged conditional B lifecycle differs '+key)
    if (diag['terminalMs']!=ack or diag['terminalReason']!='CANCEL_BEFORE_RISK_EXIT'
            or diag['activeMs']!=ack-diag['activatedMs'] or diag['printObservations'] or diag['eligiblePrintVolume']!=0):
        raise ValueError('Conditional actual matcher terminal differs')
    return dict(scope=report['scope'],actualPairPolicyChecks=len(checks),conditionalCancelRequestMs=evidence['conditionalCancelRequest']['at'],
        conditionalCancelDueMs=evidence['conditionalCancelDueMs'],conditionalCancelAck=evidence['expectedFirstDueEngineEvent'],
        sourcePostFillCounterpartObservations=len(evidence['postFillCounterpartSourceObservations']),
        postFillCounterpartExecutionUnknown=True,accountRiskAndOtherMarketsOmitted=True,
        fillsCreated=0,candidateAccountSimulated=False,netPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False,
        decision='REQUIRE_BOUNDED_POST_FILL_RECEIPTS_BEFORE_ACTUAL_HEDGE_EXIT_ACCOUNT_PATH')


def saved():
    artifact=json.loads((ROOT/'artifact-manifest.json').read_text());raw=(ROOT/'report.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=artifact['members']['report.json']['sha256']:raise ValueError('Changed actual timing report')
    return verify(json.loads((ROOT/'evidence.json').read_text()),json.loads(raw,parse_float=D),artifact)


if __name__=='__main__':print(json.dumps(saved(),indent=2))
