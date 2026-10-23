"""One predeclared baseline/QW0 replay; hard-gated on retained exact645 native parity."""
import argparse
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import subprocess

from research.phase6.full_runner_diagnosis import STORED_SHA,digest
from research.phase6.postactivation_receipt_pool import ROOT,verify_native

EXPECTED_BINDINGS=645
EXPECTED_COMPONENTS=1534


def require_native():
    summary=json.loads((ROOT/'summary.json').read_bytes());proof=json.loads((ROOT/'native-proof.json').read_bytes())
    result=verify_native(proof,summary)
    if result['originalIdentities']!=EXPECTED_BINDINGS or result['componentTuples']!=EXPECTED_COMPONENTS:raise ValueError('Incomplete retained native645 prerequisite')
    return result


def replay(input_root,inputs,classpath,output):
    require_native();frozen=json.loads(Path('research/phase6/postactivation-pool-freeze.json').read_bytes())
    for p,sha in frozen['inputsSha256'].items():
        if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=sha:raise ValueError('Changed exact645 replay dependency '+p)
    tapes=list(Path(input_root).rglob('events.jsonl.gz'))
    if len(tapes)!=1 or digest(tapes[0])!=STORED_SHA:raise ValueError('Exactly one unchanged original development recording required')
    inputs=Path(inputs);pool=inputs/'pool/pool.json';index=inputs/'source/complete-index.jsonl'
    if digest(pool)!=frozen['poolLogicalSha256']:raise ValueError('Changed exact645 pool input')
    out=Path(output);out.mkdir(parents=True,exist_ok=False);cfg=json.loads(Path('research/phase2/research-config.json').read_bytes());results={}
    for profile in ('baseline','candidate'):
        target=out/profile
        with (out/(profile+'.log')).open('w') as log:
            proc=subprocess.run(['java','-Xmx1g','-cp',classpath,'com.polybot.hft.paper.IndexedReplaySupport',
                str(tapes[0]),str(target),'research/phase2/research-config.json',str(pool),str(index),profile],stdout=log,stderr=subprocess.STDOUT,timeout=1200)
        if proc.returncode==0:
            if (target/'failure.json').exists():raise ValueError('Successful exact645 replay has failure report')
            report=json.loads((target/'report.json').read_bytes());labels=report['settlementExperiment'];reader=labels['realReceiptPool'];source=labels['sourceIndex']
            if (report['rows']!=6163831 or report['inputSha256']!=STORED_SHA or labels['failed'] is not False
                    or labels['temporalWitnessProfile']!='SOURCE_LAG0' or source['completeOriginalConsumption'] is not True
                    or source['consumedOriginalPreimages']!=16317 or reader['bindings']!=EXPECTED_BINDINGS
                    or reader['actualComponents']!=EXPECTED_COMPONENTS or reader['consumedBindings']!=EXPECTED_BINDINGS):raise ValueError('Incomplete exact645 original replay promoted')
            results[profile]=dict(status='COMPLETE_EXACT645_DEVELOPMENT_REPLAY_NOT_INDEPENDENT',netRealizedPnl=report['netRealizedPnl'],
                feesAndSettlementCosts=report['feesAndSettlementCosts'],sourceConsumed=16317,knownReceiptBindingsConsumed=EXPECTED_BINDINGS,
                unknownSourceLagClockObservations=labels['unknownSourceLagClockObservations'],unknownSourceLagActiveClockObservations=labels['unknownSourceLagActiveClockObservations'])
        else:
            if not (target/'failure.json').exists() or (target/'report.json').exists():raise ValueError('Unreported exact645 replay failure')
            failure=json.loads((target/'failure.json').read_bytes());labels=failure['labels'];report=failure['sessionAfterSuspension']
            if labels['failed'] is not True or report['halted'] is not True or report['openOrderCount']!=0 or failure['candidateFrozenPoliciesEnabled'] is not (profile=='candidate'):raise ValueError('Unsafe exact645 failure/profile')
            results[profile]=dict(status='INCOMPLETE_FAIL_CLOSED_NOT_PNL_RESULT',row=failure['row'],errors=failure['errors'],
                sourceConsumed=labels['sourceIndex']['consumedOriginalPreimages'],knownReceiptBindingsConsumed=labels['realReceiptPool']['consumedBindings'],marketNetPnlRecomputed=False)
        if any(D(str(report['configuration'][k]))!=D(str(v)) for k,v in cfg.items()):raise ValueError('Frozen execution/risk/fee configuration changed')
        if labels['unknownVenueQuantity']!='UNKNOWN_NOT_ZERO' or labels['aggregateFallbackAllowed'] is not False:raise ValueError('Unknown venue scope promoted')
    complete=all(r['status'].startswith('COMPLETE_') for r in results.values())
    result=dict(scope='ONE_SAME_ORIGINAL_DEVELOPMENT_EXACT645_BASELINE_QW0_NOT_QUALIFICATION',sourceStoredSha256=STORED_SHA,
        poolLogicalSha256=frozen['poolLogicalSha256'],results=results,completeAccountComparisonPerformed=complete,
        independentPaperQualificationAllowed=False,liveAllowed=False,decision='NO_GO')
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input-root',required=True);p.add_argument('--inputs',required=True);p.add_argument('--classpath',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    print(json.dumps(replay(a.input_root,a.inputs,a.classpath,a.output),indent=2))
