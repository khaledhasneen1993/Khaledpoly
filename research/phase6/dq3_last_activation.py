"""One remaining frozen activation window; exact old source hash binds skipped tail."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from research.phase3.polybot_sdk.tapes import open_tape


def extract(stream,spec,max_bytes=64000000):
    if len(spec['states'])!=1 or not 0<spec['endMs']-spec['startMs']<=30000:
        raise ValueError('One bounded selected start required')
    state=spec['states'][0]
    if spec['startMs']>state['submitMs']-2000:raise ValueError('Missing fresh-book warmup')
    digest=hashlib.sha256();seq=0;last=-1;run=None;declared=False;pending=None;previous=-1
    records=[];size=0;anchor=False;tail=False;last_line=None;ended=False
    for line in stream:
        if not line.endswith(b'\n') or len(line)>16*1024*1024:raise ValueError('Incomplete/oversized row')
        digest.update(line);seq+=1;last_line=line
        if tail:continue
        row=json.loads(line);at=row['arrivalMs'];kind=row['kind'];data=row['data']
        if row['schema']!=1 or row['seq']!=seq or at<last or ended or run is not None and row['runId']!=run:
            raise ValueError('Changed prefix chronology/schema/run')
        last=at;run=row['runId']
        if kind=='DATASET_CONFIG':
            if declared or data.get('format')!='normalized-public-v2' or not data.get('strategyIndependent'):
                raise ValueError('Wrong source declaration')
            declared=True
        if kind=='RAW_MARKET':
            if pending is not None or data['frameId']<=previous:raise ValueError('Changed original frame')
            pending=row
        elif kind=='RESEARCH_FRAME':
            if not declared or pending is None or pending['data']['frameId']!=data['frameId']:
                raise ValueError('Unbound original frame')
            previous=data['frameId']
        if spec['startMs']<=at<=spec['endMs'] and kind.startswith('RESEARCH_'):
            record=dict(input=row)
            if kind=='RESEARCH_FRAME':record['raw']=pending
            size+=len(json.dumps(record).encode())
            if size>max_bytes:raise ValueError('Bounded evidence cap exceeded')
            records.append(record)
        if seq==state['originalSequence']:
            if not kind.startswith('RESEARCH_') or at!=state['submitMs']:raise ValueError('Changed selected anchor')
            anchor=True
        if kind=='RESEARCH_FRAME':pending=None
        if kind=='RUN_END':ended=data.get('complete') is True
        if at>spec['endMs'] and pending is None:tail=True
    terminal=json.loads(last_line or b'{}')
    if (not declared or not anchor or pending is not None or seq!=spec['sourceRows']
            or digest.hexdigest()!=spec['logicalTapeSha256'] or terminal.get('kind')!='RUN_END'
            or not terminal['data'].get('complete') or terminal.get('seq')!=seq or terminal.get('runId')!=run):
        raise ValueError('Wrong complete original source/hash/anchor')
    return dict(scope='EXACT_ORIGINAL_LAST_SELECTED_START_ACTIVATION_ONLY',spec=spec,records=records,
        sourceRows=seq,logicalTapeSha256=digest.hexdigest(),retainedBytes=size,
        fullNormalizedDepthUnmodified=True,originalRawFramesUnmodified=True,
        tailIdentityBoundToPreviouslyValidatedCompleteSourceSha256=True,
        actualCandidateAccountOrCancellationSimulated=False,fillsInferred=False,pnlInferred=False,liveAllowed=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--input-root',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    f=json.loads(Path('research/phase6/dq3-last-activation-freeze.json').read_text())
    for path,sha in f['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Changed frozen input '+path)
    tapes=[*Path(a.input_root).rglob('events.jsonl.gz'),*Path(a.input_root).rglob('events.jsonl')]
    if len(tapes)!=1:raise ValueError('Require one complete original tape')
    with open_tape(tapes[0]) as stream:r=extract(stream,f['spec'])
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('xb') as b:
        with gzip.GzipFile(fileobj=b,mode='wb',mtime=0) as gz:gz.write((json.dumps(r,separators=(',',':'))+'\n').encode())
    print(json.dumps({k:v for k,v in r.items() if k!='records'}),flush=True)


if __name__=='__main__':main()
