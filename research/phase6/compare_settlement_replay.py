"""Same-development full-account calibration, never independent strategy qualification."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def run(tape, output):
    frozen=json.loads(Path('research/phase6/settlement-replay-freeze.json').read_text())
    for path,digest in frozen['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:
            raise ValueError('Predeclared settlement replay input/code changed: '+path)
    output=Path(output);output.mkdir(parents=True,exist_ok=False);reports={}
    for name,main in [('baseline','com.polybot.hft.executor.replay.ClosedLoopMain'),
                      ('candidate','com.polybot.hft.paper.SettlementReplayMain')]:
        command=['java','-Xmx2g','-Dloader.main='+main,'-cp','executor-service/target/executor-service-0.6.0.jar',
                 'org.springframework.boot.loader.launch.PropertiesLauncher',str(tape),str(output/name),
                 'research/phase2/research-config.json']
        if name=='candidate':command.append('research/experiments/settlement-lab0-20261018/replay-labels.json')
        subprocess.run(command,check=True,timeout=1800)
        reports[name]=json.loads((output/name/'report.json').read_text())
        if name=='baseline' and (reports[name]['submittedOrders']!=52 or reports[name]['fills']!=0):
            raise ValueError('Normalized baseline does not reproduce known 52 orders/zero fills')
    before=reports['baseline'];after=reports['candidate']
    if before['inputSha256']!=after['inputSha256'] or before['configSha256']!=after['configSha256']:
        raise ValueError('Comparison input/config differs')
    labels=after['settlementExperiment']
    if labels['consumedBindings']!=5 or labels['labelBindings']!=5 or after['independentPaperQualificationAllowed']:
        raise ValueError('Unexpected label coverage or qualification contract')
    keys=('submittedOrders','fills','cash','netRealizedPnl','feesAndSettlementCosts','holdings','maxDrawdown',
          'riskBreaches','halted','pairCompletions','quantityPairCompletion','residualExpiryWorstCaseNotional')
    result=dict(scope='DEVELOPMENT_FULL_ACCOUNT_SETTLEMENT_MODEL_CALIBRATION_NOT_STRATEGY_QUALIFICATION',
        baseline={k:before.get(k) for k in keys},candidate={k:after.get(k) for k in keys},
        settlementExperiment=labels,settlementVolumeConservation=after['settlementVolumeConservation'],
        inputSha256=before['inputSha256'],configSha256=before['configSha256'],
        independentPaperQualificationAllowed=False,candidateWorthIndependentTest=False,partialLabels=True,
        futureLabelsAreEnvironmentOnly=True,decision='NO_GO',liveAllowed=False,
        reason='Partial offline settlement labels calibrate execution coverage; not a causal live model or profitable strategy proof.')
    (output/'comparison.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--input-root',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    tapes=[*Path(a.input_root).rglob('events.jsonl.gz'),*Path(a.input_root).rglob('events.jsonl')]
    if len(tapes)!=1:raise ValueError('Require one complete unambiguous tape')
    run(tapes[0],a.output)


if __name__=='__main__':main()
