"""Same-development five-vs-seven label control, never a strategy qualification."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from research.phase6.export_exit_covered_labels import export


def run(tape, output):
    frozen = json.loads(Path('research/phase6/exit-covered-replay-freeze.json').read_text())
    for path,digest in frozen['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen exit-covered replay changed: '+path)
    candidate = json.loads(Path(frozen['variants']['candidate']['labels']).read_text())
    if export() != candidate:
        raise ValueError('Exported receipt bindings changed')
    output = Path(output); output.mkdir(parents=True,exist_ok=False); reports = {}
    for name,variant in frozen['variants'].items():
        command = ['java','-Xmx2g','-Dloader.main=com.polybot.hft.paper.SettlementReplayMain',
            '-cp','executor-service/target/executor-service-0.6.0.jar',
            'org.springframework.boot.loader.launch.PropertiesLauncher',str(tape),str(output/name),
            'research/phase2/research-config.json',variant['labels']]
        subprocess.run(command,check=True,timeout=1800)
        report = json.loads((output/name/'report.json').read_text()); labels = report['settlementExperiment']
        if (labels['labelBindings'] != variant['bindings'] or labels['consumedBindings'] != variant['bindings']
                or report['independentPaperQualificationAllowed']
                or report['inputSha256'] != frozen['inputSha256']
                or labels['logicalTapeSha256'] != frozen['logicalTapeSha256']
                or report['configSha256'] != frozen['configSha256']):
            raise ValueError('Unexpected tape/config/coverage/qualification')
        reports[name] = report
    keys = ('submittedOrders','fills','cash','netRealizedPnl','feesAndSettlementCosts','holdings','maxDrawdown',
            'riskBreaches','halted','pairCompletions','quantityPairCompletion','residualExpiryWorstCaseNotional',
            'executions','settlementExperiment','settlementVolumeConservation')
    result = dict(scope='DEVELOPMENT_FIVE_VS_SEVEN_ENVIRONMENT_LABELS_ACCOUNT_CONTROL_NOT_STRATEGY_CANDIDATE',
        variants={name:{key:report.get(key) for key in keys} for name,report in reports.items()},
        logicalTapeSha256=frozen['logicalTapeSha256'],configSha256=frozen['configSha256'],
        candidateFrozenBeforeReplay=True,partialLabels=True,futureLabelsAreEnvironmentOnly=True,
        independentPaperQualificationAllowed=False,candidateWorthIndependentTest=False,liveAllowed=False,decision='NO_GO')
    (output/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--input-root',required=True); p.add_argument('--output',required=True)
    a = p.parse_args(); tapes = [*Path(a.input_root).rglob('events.jsonl.gz'),*Path(a.input_root).rglob('events.jsonl')]
    if len(tapes) != 1: raise ValueError('Require one complete unambiguous original tape')
    run(tapes[0],a.output)
