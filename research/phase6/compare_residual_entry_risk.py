"""One preregistered causal entry veto, same DEVELOPMENT tape and partial environment labels."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def run(tape,output):
    frozen=json.loads(Path('research/phase6/residual-entry-risk-replay-freeze.json').read_text())
    for path,digest in frozen['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:
            raise ValueError('Current candidate source/config/acceptance changed: '+path)
    output=Path(output);output.mkdir(parents=True,exist_ok=False);reports={}
    for mode in ('control','candidate'):
        command=['java','-Xmx2g','-Dloader.main=com.polybot.hft.paper.ResidualRiskReplayMain',
            '-cp','executor-service/target/executor-service-0.6.0.jar',
            'org.springframework.boot.loader.launch.PropertiesLauncher',str(tape),str(output/mode),
            'research/phase2/research-config.json',frozen['labels'],mode]
        subprocess.run(command,check=True,timeout=1800)
        r=json.loads((output/mode/'report.json').read_text());labels=r['settlementExperiment']
        if (r['inputSha256']!=frozen['inputSha256'] or r['configSha256']!=frozen['configSha256']
                or labels['logicalTapeSha256']!=frozen['logicalTapeSha256']
                or labels['consumedBindings']!=14 or labels['labelBindings']!=14
                or r['residualEntryRiskGuard']!=(mode=='candidate') or r['independentPaperQualificationAllowed']):
            raise ValueError('Input/coverage/mode/qualification differs')
        if mode=='control' and any(r[k]!=v for k,v in frozen['expectedControl'].items()):
            raise ValueError('Default-off behavior does not reproduce corrected baseline')
        reports[mode]=r
    keys=('submittedOrders','fills','cash','netRealizedPnl','feesAndSettlementCosts','maxDrawdown','holdings',
          'halted','riskBreaches','quantityPairCompletion','residualExpiryWorstCaseNotional','executions',
          'decisionReasons','residualEntryRiskGuard','residualEntryRiskRejectSamples','settlementExperiment')
    comparison=dict(scope='CS_RESIDUAL_WORST_CASE_1_SAME_DEVELOPMENT_ACCOUNT_CONTROL',
        variants={mode:{key:r.get(key) for key in keys} for mode,r in reports.items()},
        candidateFrozenBeforeReplay=True,parameterSearchPerformed=False,partialEnvironmentLabels=True,
        independentPaperQualificationAllowed=False,liveAllowed=False,decision='NO_GO',
        note='No-loss or zero-fill result is not profitability. Future receipt labels are environment calibration only.')
    (output/'comparison.json').write_text(json.dumps(comparison,indent=2)+'\n');print(json.dumps(comparison),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input-root',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    tapes=[*Path(a.input_root).rglob('events.jsonl.gz'),*Path(a.input_root).rglob('events.jsonl')]
    if len(tapes)!=1:raise ValueError('Require one complete original development tape')
    run(tapes[0],a.output)
