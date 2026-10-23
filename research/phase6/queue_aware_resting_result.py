"""Reproduce the bounded conditional resting gate, with no financial qualification."""
from decimal import Decimal as D
import gzip
import hashlib
import json
from research.phase6.queue_aware_causal import QROOT
from research.phase6.queue_aware_causal_result import load, verify as causal_verify
from research.phase6.queue_aware_resting import timeline

ROOT=QROOT/'resting-result'


def verify(evidence,report,artifact):
    context,bindings,prior=load();causal_verify(context,bindings,prior)
    expected=timeline(context,bindings,prior)
    if json.loads(json.dumps(expected,default=str))!=evidence:raise ValueError('Changed source-bound resting reconstruction')
    for name,obj in [('context.json.gz',context),('bindings.json',bindings),('evidence.json',evidence)]:
        raw=(json.dumps(obj,default=str,separators=(',',':'))+'\n').encode()
        if name.endswith('.gz'):raw=gzip.compress(raw,mtime=0)
        member=artifact['members'][name]
        if len(raw)!=member['bytes'] or hashlib.sha256(raw).hexdigest()!=member['sha256']:
            raise ValueError('Retained artifact input differs '+name)
    if (report['scope']!='CONDITIONAL_TARGET_RESTING_LIFETIME_UNKNOWN_COUNTERPART_NOT_ACCOUNT'
            or not report['counterpartExecutionOmitted'] or not report['counterpartRemainsUntouchedAssumed']
            or report['actualBotFillsCreated']!=0 or report['candidateAccountSimulated'] or report['netPnlRecomputed']
            or report['independentPaperQualificationAllowed'] or report['liveAllowed']):raise ValueError('Wrong conditional scope')
    if (report['actualPairPolicyChecks']!=len(evidence['checks']) or any(c['reason']!='RESTING' for c in evidence['checks'])
            or report['cancelRequestMs']!=-1 or report['cancelReason'] is not None):raise ValueError('Resting check result differs')
    count=sum(b['at']<=evidence['fixedHorizonMs'] for b in bindings['bindings'])
    if report['consumedTargetBindings']!=count:raise ValueError('Incomplete original labels before horizon')
    old=prior['diagnostics'][0];new=report['diagnostics'][0]
    if {k:v for k,v in old.items() if k!='id'}!={k:v for k,v in new.items() if k!='id'}:
        raise ValueError('Actual target engine lifecycle differs')
    oldfills=[{k:v for k,v in f.items() if k!='id'} for f in prior['conditionalModelFills']]
    if oldfills!=[{k:v for k,v in f.items() if k!='id'} for f in report['conditionalTargetAllocations']]:
        raise ValueError('Conditional actual-component allocations differ')
    return dict(scope='REPRODUCED_CONDITIONAL_RESTING_NOT_ACCOUNT',actualPairPolicyChecks=len(evidence['checks']),
        matchedOriginalWitnessSequences=evidence['matchedOriginalWitnessSequences'],consumedTargetBindings=count,
        conditionalTargetShares=str(sum(D(f['size']) for f in report['conditionalTargetAllocations'])),
        counterpartExecutionUnknown=True,actualBotFillsCreated=0,netPnlRecomputed=False,
        candidateAccountSimulated=False,independentPaperQualificationAllowed=False,liveAllowed=False,
        decision='REQUIRE_CONSERVED_COUNTERPART_EVIDENCE_AND_FULL_DEVELOPMENT_ACCOUNT_COMPARISON')


def saved():
    evidence=json.loads((ROOT/'evidence.json').read_text())
    raw=(ROOT/'report.json').read_bytes();artifact=json.loads((ROOT/'artifact-manifest.json').read_text())
    if hashlib.sha256(raw).hexdigest()!=artifact['members']['report.json']['sha256']:raise ValueError('Changed actual engine report')
    return verify(evidence,json.loads(raw,parse_float=D),artifact)


if __name__=='__main__':print(json.dumps(saved(),indent=2))
