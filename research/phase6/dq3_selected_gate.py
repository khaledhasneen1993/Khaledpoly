"""Close the eleven selected-state necessary-leg gate, NOT global policy performance."""
import base64
from decimal import Decimal as D
import hashlib
import io
import json
import zipfile
from research.phase6.dq3_bottleneck_receipts import ROOT
from research.phase6.dq3_last_cancel import load,evidence
from research.phase6.dq3_activation_result import load as prior_load,verify as prior_verify


def verify_cancel(report):
    context,activation,_=load();e=evidence(context,activation);d=report['targetDiagnostic']
    if (report['scope']!='CONDITIONAL_ISOLATED_PAIR_FIRST_RESTING_CHECK_NOT_ACTUAL_ACCOUNT'
            or not report['allTradeVolumeSuppressed'] or report['fillsCreated']!=0
            or report['netPnlRecomputed'] or report['candidateAccountSimulated']
            or report['independentPaperQualificationAllowed'] or report['liveAllowed']):
        raise ValueError('Wrong conditional no-fill scope')
    if (report['cancelRequestMs']!=e['expectedCancelRequestMs'] or report['cancelDueMs']!=e['expectedCancelDueMs']
            or D(str(report['requiredEdge']))!=D(e['requiredEdge']) or D(str(report['reservedNetEdgeTotal']))!=D(e['netEdgeTotal'])
            or D(str(report['restingQuantity']))!=5 or D(str(report['legacyNewEntryQuantityNotUsed']))!=D('.5')):
        raise ValueError('Wrong original resting-risk timing/quantity')
    source=next(rec['input'] for rec in context['records'] if rec['input']['seq']==report['cancelAckSequence'])
    if (source['arrivalMs']!=d['terminalMs'] or d['terminalMs']<report['cancelDueMs']
            or not d['terminalMs']<e['firstPossibleTargetPrintArrivalMs'] or d['terminalReason']!='RESTING_NET_EDGE'
            or d['initialQueueAhead']!=200 or d['remainingQueueAhead']!=200 or d['remainingShares']!=5
            or d['eligiblePrintVolume']!=0 or d['activeMs']!=d['terminalMs']-d['activatedMs']
            or d['activatedMs']!=e['expectedCancelRequestMs']):
        raise ValueError('Unproven source-bound engine cancellation before first print')
    return dict(originalSequence=299650,reason='CONDITIONAL_RESTING_RISK_CANCEL_BEFORE_ANY_TARGET_OBSERVATION',
        cancelAckMs=d['terminalMs'],cancelAckSequence=report['cancelAckSequence'],
        firstPossibleTargetPrintArrivalMs=e['firstPossibleTargetPrintArrivalMs'],
        millisecondsBeforeFirstPrint=e['firstPossibleTargetPrintArrivalMs']-d['terminalMs'])


def analyze():
    raw=base64.b64decode((ROOT/'last-cancel-result/artifact.zip.b64').read_bytes())
    if hashlib.sha256(raw).hexdigest()!='e90d8fb1cb8068fe41b97db20105080cd1057694971799264294182741471ac7':
        raise ValueError('Changed engine cancel artifact')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if set(z.namelist())!={'evidence.json','cancel-report.json'}:raise ValueError('Wrong cancel members')
        context,activation,_=load()
        if json.loads(z.read('evidence.json'))!=json.loads(json.dumps(evidence(context,activation),default=str)):
            raise ValueError('Changed cached source/witness evidence')
        cancel=verify_cancel(json.loads(z.read('cancel-report.json'),parse_float=D))
    prior={r['originalSequence']:r for r in prior_verify(*prior_load())['results']}
    legs=json.loads((ROOT/'last-leg-result/coverage.json').read_text())['legs'];results=[]
    for leg in legs:
        if not leg['complete']:continue
        seq=leg['originalSequence']
        if leg['actualPriceCompatibleSharesRaw']==0:reason='ZERO_ACTUAL_PRICE_COMPATIBLE_COMPONENTS_IN_COMPLETE_TARGET_LEG_WINDOW'
        elif seq in prior:reason=prior[seq]['reason']
        elif seq==299650:reason=cancel['reason']
        else:raise ValueError('A selected complete leg remains unproven')
        results.append(dict(originalSequence=seq,targetQuote=leg['quote'],reason=reason))
    if len(results)!=11:raise ValueError('Incomplete selected-state gate')
    return dict(scope='ELEVEN_SELECTED_LEGACY_STARTS_NOT_GLOBAL_DQ3_TRAJECTORY_OR_PROFIT',results=results,
        finalConditionalCancel=cancel,zeroActualComponentLegs=7,queueBoundRejectedStarts=2,
        postOnlyRejectedStarts=1,conditionalRiskCanceledStarts=1,
        fillsCreated=0,netPnlRecomputed=False,candidateAccountSimulated=False,
        independentPaperQualificationAllowed=False,liveAllowed=False,
        decision='DO_NOT_PROMOTE_DQ3_ON_THESE_SELECTED_DEVELOPMENT_STATES')


if __name__=='__main__':print(json.dumps(analyze(),indent=2))
