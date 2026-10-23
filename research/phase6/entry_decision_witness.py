"""One frozen observational replay; reproduce ALL archived candidate fields before diagnosis."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

FREEZE=Path('research/phase6/entry-decision-witness-freeze.json')


def golden():
    raw=base64.b64decode(Path('research/experiments/residual-entry-risk-20261018/result/artifact.zip.b64').read_bytes())
    if hashlib.sha256(raw).hexdigest()!='680a934c5e0d38d57cbd85a725052e0771f3a1fcfae7a3958a07a37d405d4bf7':
        raise ValueError('Original account artifact changed')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if archive.getinfo('candidate/report.json').file_size>100000:
            raise ValueError('Oversized original candidate report')
        return json.loads(archive.read('candidate/report.json'))


def verify_report(report,reference,windows):
    # Only the code revision can differ; ALL old behavioral/economic/queue,
    # decision count, fee, source and label-consumption fields must reproduce.
    changed=[k for k,v in reference.items() if k!='strategyRevision' and (k not in report or report[k]!=v)]
    if changed:raise ValueError('Observational replay changed original fields: '+','.join(changed))
    rows=report.get('entryDecisionWitnesses',[])
    if not 1<=len(rows)<=500:raise ValueError('Missing/oversized decision witnesses')
    for r in rows:
        if (not any(w['condition']==r['condition'] and w['startMs']<=r['at']<=w['endMs'] for w in windows)
                or r['nextDecisionMs']<=r['at'] or not isinstance(r['actualDecisionReasonDelta'],dict)):
            raise ValueError('Out-of-scope or malformed decision witness')
    return dict(scope='ACTUAL_CAUSAL_ENTRY_DECISIONS_OBSERVATION_ONLY',originalAccountFieldsReproduced=True,
        originalAccountFieldCount=len(reference)-('strategyRevision' in reference),witnessCount=len(rows),
        newFillsCreatedByObservation=0,netRealizedPnl=report['netRealizedPnl'],fills=report['fills'],
        independentPaperQualificationAllowed=False,liveAllowed=False,decision='NO_GO')


def run(input_root,output):
    frozen=json.loads(FREEZE.read_text())
    for p,d in frozen['filesSha256'].items():
        if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=d:raise ValueError('Frozen witness source changed: '+p)
    tapes=[*Path(input_root).rglob('events.jsonl.gz'),*Path(input_root).rglob('events.jsonl')]
    if len(tapes)!=1:raise ValueError('Require one original development tape')
    windows=json.loads(Path(frozen['windows']).read_text());out=Path(output)
    subprocess.run(['java','-Xmx2g','-Dloader.main=com.polybot.hft.paper.EntryDecisionWitnessReplayMain',
        '-cp','executor-service/target/executor-service-0.6.0.jar','org.springframework.boot.loader.launch.PropertiesLauncher',
        str(tapes[0]),str(out),'research/phase2/research-config.json',frozen['labels'],frozen['windows']],check=True,timeout=1800)
    report=json.loads((out/'report.json').read_text());summary=verify_report(report,golden(),windows)
    (out/'witness-verification.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input-root',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.input_root,a.output)
