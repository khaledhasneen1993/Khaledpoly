"""One SAME-source baseline/candidate first-blocker diagnostic, never a net-PnL result."""
import argparse
from decimal import Decimal as D
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
from research.phase6.full_tape_coverage_result import ROOT,read_archive

STORED_SHA='9363443ae9287016ab7c63d3cf11d6b1ae33d814d9e3ad340bb99b33e7285074'

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def first_missing():
    _,compressed,_=read_archive(ROOT/'artifact.zip')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as source:return json.loads(source.readline())

def verify_failure(proof,expected,candidate,config):
    if (proof['scope']!='INCOMPLETE_ORIGINAL_TAPE_FAIL_CLOSED_DIAGNOSTIC_NOT_FINANCIAL_RESULT'
            or proof['candidateFrozenPoliciesEnabled'] is not candidate or proof['decision']!='NO_GO'):
        raise ValueError('Incorrect failed-run scope/policy')
    for field in ('fullOriginalTapeCoverageProven','completeAccountComparisonPerformed','marketNetPnlRecomputed','independentPaperQualificationAllowed','liveAllowed'):
        if proof[field] is not False:raise ValueError('Incomplete replay cannot become financial/qualification evidence')
    labels=proof['labels'];attempt=labels['lastAttemptedOriginalObservation'];data=attempt['observation']
    if (labels['bindings']!=642 or labels['actualComponents']!=1516 or labels['consumedBindings']!=0
            or labels['failed'] is not True or labels['aggregateFallbackAllowed'] is not False
            or proof['row']['seq']!=expected['seq'] or proof['row']['kind']!='RESEARCH_FRAME'
            or proof['row']['arrivalMs']!=expected['at']
            or any(attempt[k]!=expected[k] for k in ('seq','eventIndex','at'))
            or any(data[k]!=expected[k] for k in ('token','side','sourceMs'))
            or any(D(str(data[k]))!=D(str(expected[k])) for k in ('price','size'))
            or hashlib.sha256(data['tradeId'].encode()).hexdigest()!=expected['publicTradeIdSha256']
            or json.loads(data['tradeId'])['transaction_hash']!=expected['transactionHash']):
        raise ValueError('First original missing identity differs; do not skip or relabel')
    if proof['errors']!=['IllegalArgumentException: Fail-closed pool resolution',
                          'IllegalArgumentException: Unknown original observation; incomplete pool is not zero']:
        raise ValueError('Unexpected replay failure, not coverage diagnosis')
    session=proof['sessionAfterSuspension'];ledger=proof['ledgerAfterSuspension']
    if (session['halted'] is not True or session['openOrderCount']!=0 or ledger['halted'] is not True
            or session['frozenQw0AndFeePositivePoliciesIntegrated'] is not candidate
            or session['settlementExperiment']!=labels):
        raise ValueError('Fail-closed ledger/cancellation/profile differs')
    for key,value in config.items():
        if D(str(session['configuration'][key]))!=D(str(value)):raise ValueError('Risk/fee/queue config changed')
    return dict(seq=expected['seq'],eventIndex=expected['eventIndex'],at=expected['at'],
        transactionHash=expected['transactionHash'],halted=True,openOrderCount=0,
        completeAccountComparisonPerformed=False,marketNetPnlRecomputed=False)

def run(input_root,output,classpath,pool):
    tapes=list(Path(input_root).rglob('events.jsonl.gz'))
    if len(tapes)!=1 or digest(tapes[0])!=STORED_SHA:raise ValueError('Exactly one unchanged original compressed tape required')
    freeze=json.loads(Path('research/phase6/full-runner-freeze.json').read_text())
    for p,sha in freeze['filesSha256'].items():
        if digest(p)!=sha:raise ValueError('Changed frozen runner/config/acceptance dependency '+p)
    if digest(pool)!='745dadce6749d701ba6048ab1ef76f3f43b354c058e27e9163c2174725aaceea':raise ValueError('Changed partial pool')
    expected=first_missing();known=json.loads(Path(pool).read_text())
    if (expected['seq'],expected['eventIndex']) in {(b['seq'],b['eventIndex']) for b in known['bindings']}:raise ValueError('First blocker already covered; update experiment explicitly')
    output=Path(output);output.mkdir(parents=True,exist_ok=False);results={}
    cfg=Path('research/phase2/research-config.json');config=json.loads(cfg.read_text())
    for policy in ('baseline','candidate'):
        out=output/policy
        with (output/(policy+'.log')).open('w') as log:
            process=subprocess.run(['java','-Xmx1g','-cp',classpath,'com.polybot.hft.paper.NativeReplaySupport',
                str(tapes[0]),str(out),str(cfg),str(pool),policy],stdout=log,stderr=subprocess.STDOUT,timeout=180)
        if process.returncode==0 or not (out/'failure.json').is_file() or (out/'report.json').exists():
            raise ValueError('Expected strict coverage stop, not success, timeout, JVM or parser failure')
        results[policy]=verify_failure(json.loads((out/'failure.json').read_text()),expected,policy=='candidate',config)
    result=dict(scope='SAME_ORIGINAL_SOURCE_FIRST_BLOCKER_ONLY_NOT_ACCOUNT_COMPARISON',
        inputStoredSha256=STORED_SHA,poolLogicalSha256=digest(pool),freezeSha256=digest('research/phase6/full-runner-freeze.json'),
        results=results,sameOriginalBlocker=results['baseline']==results['candidate'],
        originalSourceRows=6163831,sourcePrefixOnlyNotCompleteReplay=True,
        unknownObservationsSkipped=0,publicAggregateFallbackAllowed=False,
        completeAccountComparisonPerformed=False,marketNetPnlRecomputed=False,
        independentPaperQualificationAllowed=False,liveAllowed=False,decision='NO_GO')
    if not result['sameOriginalBlocker']:raise ValueError('Policy first blockers differ')
    (output/'verification.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input-root',required=True);p.add_argument('--output',required=True)
    p.add_argument('--classpath',required=True);p.add_argument('--pool',required=True);a=p.parse_args()
    print(json.dumps(run(a.input_root,a.output,a.classpath,a.pool),indent=2))
