"""Full-depth, source-bound inputs for isolated no-cancel activation probes only."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from research.phase3.polybot_sdk.tapes import open_tape


def extract(stream,spec,max_bytes=64000000):
    if not 0<spec['endMs']-spec['startMs']<=30000 or len(spec['states'])!=3:
        raise ValueError('Require exactly three bounded frozen starts')
    if spec['startMs']>min(s['submitMs'] for s in spec['states'])-spec['maxBookAgeMs']:
        raise ValueError('Insufficient full fresh-book warmup')
    anchors={s['originalSequence']:s for s in spec['states']};seen=set()
    rows=[];pending=None;previous=-1;seq=0;last=-1;run=None;ended=False;declared=False;size=0
    digest=hashlib.sha256()
    for line in stream:
        if not line.endswith(b'\n') or len(line)>16*1024*1024:raise ValueError('Incomplete/oversized row')
        digest.update(line);row=json.loads(line);seq+=1
        at=row['arrivalMs'];kind=row['kind'];data=row['data']
        if row['schema']!=1 or row['seq']!=seq or at<last or ended or run is not None and row['runId']!=run:
            raise ValueError('Wrong source chronology/schema/run')
        run=row['runId'];last=at
        if kind=='DATASET_CONFIG':
            if declared or data.get('format')!='normalized-public-v2' or not data.get('strategyIndependent'):
                raise ValueError('Require strategy-independent original framed tape')
            declared=True
        if kind=='RAW_MARKET':
            if pending is not None or data['frameId']<=previous:raise ValueError('Invalid original frame')
            pending=row
        elif kind=='RESEARCH_FRAME':
            if not declared or pending is None or data['frameId']!=pending['data']['frameId']:
                raise ValueError('Unbound original frame')
            previous=data['frameId']
        if spec['startMs']<=at<=spec['endMs'] and kind.startswith('RESEARCH_'):
            record=dict(input=row)
            if kind=='RESEARCH_FRAME':record['raw']=pending
            size+=len(json.dumps(record).encode())
            if size>max_bytes:raise ValueError('Evidence cap exceeded; never truncate')
            rows.append(record)
        if seq in anchors:
            if not kind.startswith('RESEARCH_') or at!=anchors[seq]['submitMs']:
                raise ValueError('Original selected anchor changed')
            seen.add(seq)
        if kind=='RESEARCH_FRAME':pending=None
        if kind=='RUN_END':
            ended=data.get('complete') is True
            if not ended:raise ValueError('Unclean original tape')
    if (not ended or not declared or pending is not None or seen!=set(anchors)
            or seq!=spec['sourceRows'] or digest.hexdigest()!=spec['logicalTapeSha256']):
        raise ValueError('Wrong/incomplete original tape or anchors')
    return dict(scope='FULL_ORIGINAL_INPUTS_FOR_ISOLATED_NO_CANCEL_ACTIVATION_ONLY',spec=spec,
        sourceRows=seq,logicalTapeSha256=digest.hexdigest(),records=rows,retainedBytes=size,
        fullNormalizedDepthUnmodified=True,originalRawFramesUnmodified=True,
        actualCandidateAccountOrCancellationSimulated=False,fillsInferred=False,pnlInferred=False,liveAllowed=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--input-root',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    f=json.loads(Path('research/phase6/dq3-activation-freeze.json').read_text())
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
