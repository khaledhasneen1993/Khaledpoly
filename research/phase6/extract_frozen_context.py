"""Reuse original RAW extraction for a separately frozen evidence-only window."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from research.phase3.polybot_sdk.tapes import open_tape
from research.phase6.raw_gap_context import extract


def validate_target(result,frozen):
    at=frozen['originalTerminalMs'];gaps=[]
    for frame in result['frames']:
        row=frame['normalized']
        if row['arrivalMs']==at:
            gaps.extend(e for e in row['data']['events'] if e['kind']=='GAP' and e['data'].get('reason')=='invalid_depth')
    gaps.extend(row for row in result['standaloneGaps'] if row['arrivalMs']==at
                and row['kind']=='RESEARCH_GAP' and row['data'].get('reason')=='invalid_depth')
    if not gaps:raise ValueError('Original candidate terminal GAP absent from fixed context')


def main():
    p=argparse.ArgumentParser();p.add_argument('--input-root',required=True);p.add_argument('--output',required=True)
    p.add_argument('--freeze',required=True);a=p.parse_args()
    frozen=json.loads(Path(a.freeze).read_text())
    for name,digest in frozen['filesSha256'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Frozen context spec/source changed: '+name)
    tapes=[*Path(a.input_root).rglob('events.jsonl.gz'),*Path(a.input_root).rglob('events.jsonl')]
    if len(tapes)!=1:raise ValueError('Require one complete original development tape')
    with open_tape(tapes[0]) as stream:result=extract(stream,frozen['spec'])
    validate_target(result,frozen)
    target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as output:
        with gzip.GzipFile(fileobj=output,mode='wb',mtime=0) as encoded:
            encoded.write((json.dumps(result,separators=(',',':'))+'\n').encode())
    print(json.dumps({k:v for k,v in result.items() if k not in ('frames','standaloneGaps')}),flush=True)


if __name__=='__main__':main()
