"""Data-driven bounded label controls. Future receipts are never strategy inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from research.phase6.export_exit_window_labels import export


def run(tape,output,freeze_path):
    frozen=json.loads(Path(freeze_path).read_text())
    for path,digest in frozen['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:
            raise ValueError('Frozen label control changed: '+path)
    if export()!=json.loads(Path(frozen['variants']['candidate']['labels']).read_text()):
        raise ValueError('Complete-window receipt export differs')
    output=Path(output);output.mkdir(parents=True,exist_ok=False);reports={}
    for mode,variant in frozen['variants'].items():
        command=['java','-Xmx2g','-Dloader.main=com.polybot.hft.paper.SettlementReplayMain',
            '-cp','executor-service/target/executor-service-0.6.0.jar',
            'org.springframework.boot.loader.launch.PropertiesLauncher',str(tape),str(output/mode),
            'research/phase2/research-config.json',variant['labels']]
        subprocess.run(command,check=True,timeout=1800)
        report=json.loads((output/mode/'report.json').read_text());labels=report['settlementExperiment']
        if (labels['consumedBindings']!=variant['bindings'] or labels['labelBindings']!=variant['bindings']
                or report['inputSha256']!=frozen['inputSha256'] or report['configSha256']!=frozen['configSha256']
                or labels['logicalTapeSha256']!=frozen['logicalTapeSha256'] or report['independentPaperQualificationAllowed']):
            raise ValueError('Tape/config/coverage/qualification contract differs')
        reports[mode]=report
    keys=('submittedOrders','fills','cash','netRealizedPnl','feesAndSettlementCosts','holdings','maxDrawdown',
          'riskBreaches','halted','pairCompletions','quantityPairCompletion','residualExpiryWorstCaseNotional',
          'executions','settlementExperiment','settlementVolumeConservation','missingMarkoutsByReason')
    comparison=dict(scope=frozen['experiment'],variants={mode:{key:r.get(key) for key in keys} for mode,r in reports.items()},
        inputSha256=frozen['inputSha256'],logicalTapeSha256=frozen['logicalTapeSha256'],configSha256=frozen['configSha256'],
        partialLabels=True,futureLabelsAreEnvironmentOnly=True,candidateFrozenBeforeReplay=True,
        independentPaperQualificationAllowed=False,liveAllowed=False,decision='NO_GO')
    (output/'comparison.json').write_text(json.dumps(comparison,indent=2)+'\n');print(json.dumps(comparison),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input-root',required=True);p.add_argument('--output',required=True)
    p.add_argument('--freeze',required=True);a=p.parse_args()
    tapes=[*Path(a.input_root).rglob('events.jsonl.gz'),*Path(a.input_root).rglob('events.jsonl')]
    if len(tapes)!=1:raise ValueError('Require one complete original development tape')
    run(tapes[0],a.output,a.freeze)
