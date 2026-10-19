"""Prepare first changed exit allocation gate; frozen initial inventory is conditional."""
import argparse
import hashlib
import json
from pathlib import Path
from research.phase6.queue_aware_recovery_result import load,verify,ROOT
from research.phase6.queue_aware_causal import QROOT


def prepare():
    spec,evidence,summary=load();proof=verify(spec,evidence,summary)
    prefix=json.loads((QROOT/'active-reduction-result/report.json').read_text())
    seed=json.loads((QROOT/'resting-result/evidence.json').read_text())
    if prefix['remainingUnhedgedShares']!=5 or prefix['stoppedOnFirstReductionAllocation'] or not prefix['firstGapActuallyProcessed']:raise ValueError('Changed original conditional initial inventory')
    if any(d['terminalMs'] is None for d in prefix['diagnostics']):raise ValueError('Open order at original GAP')
    next_at=max(c['at'] for c in prefix['decisions'])+seed['config']['decisionMillis']
    if next_at!=1792269761068:raise ValueError('Changed original next strategy callback clock')
    bindings=[dict(seq=r['normalizedSeq'],eventIndex=r['eventIndex'],at=r['arrivalMs'],sourceMs=int(r['sample']['timestamp']),sample=r['sample'],transactionHash=r['transactionHash'],parts=r['parts']) for r in summary['results']]
    return dict(scope='CONDITIONAL_FIRST_POST_GAP_EXIT_ALLOCATION_NOT_FULL_ACCOUNT',pair=spec['pair'],bindings=bindings,
        market=seed['seedWitness']['market'],config=seed['config'],startMs=spec['window']['firstGapMs'],horizonMs=spec['window']['endMs'],
        nextDecisionMs=next_at,firstModelAllocationMs=spec['window']['firstModelAllocationMs'],
        initialQuantity='5',initialBasisPerShare='0.48',initialUnspentExitLossBudget=seed['config']['maxExitLoss'],
        seedFromPriorNativeModelNotActualBotInventory=True,stopImmediatelyOnFirstNewAllocation=True,
        accountRiskAndOtherMarketsOmitted=True,candidateAccountSimulated=False,netPnlRecomputed=False,
        independentPaperQualificationAllowed=False,liveAllowed=False,receiptVerification=proof)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    f=json.loads(Path('research/phase6/queue-aware-recovery-exit-freeze.json').read_text())
    for path,sha in f['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Frozen recovery exit source changed '+path)
    r=prepare();p=Path(a.output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(scope=r['scope'],bindings=len(r['bindings']),nextDecisionMs=r['nextDecisionMs'],newPublicReads=0)))


if __name__=='__main__':main()
