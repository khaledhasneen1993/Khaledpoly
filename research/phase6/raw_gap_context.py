"""Bounded original public WS frames around proven gaps; no execution inference."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from research.phase3.polybot_sdk.tapes import open_tape


def scope(data, tokens):
    affected=set(data.get('tokens',[]))
    if data.get('token'):affected.add(data['token'])
    return not affected or bool(affected & tokens)


def project_event(event, index):
    data=event['data']
    if event['kind']=='BOOK':
        # Full depth remains in the ORIGINAL raw snapshot. This normalized view
        # is diagnostic top-of-book, never queue/depth reconstruction evidence.
        from decimal import Decimal
        data=dict(data,depthProjectionNotFullDepth=True)
        for side,reverse in [('bids',True),('asks',False)]:
            data[side]=sorted(data.get(side,[]),key=lambda x:Decimal(str(x['price'])),reverse=reverse)[:3]
    return dict(kind=event['kind'],data=data,originalEventIndex=index)


def extract(stream, spec, max_bytes=32000000):
    tokens=set(spec['tokens']);start=spec['startMs'];end=spec['endMs']
    if len(tokens)!=2 or not 0<end-start<=30000 or len(spec['anchors'])>8:
        raise ValueError('Require bounded binary GAP context')
    wanted={(a['seq'],a['eventIndex']) for a in spec['anchors']};found=set()
    frames=[];standalone=[];retained=0;seq=0;last=-1;run=None;pending=None;previous_frame=-1
    digest=hashlib.sha256();ended=False;declared=False
    for raw in stream:
        if len(raw)>16*1024*1024 or not raw.endswith(b'\n'):
            raise ValueError('Oversized/incomplete row')
        digest.update(raw);row=json.loads(raw);seq+=1
        at=row['arrivalMs'];kind=row['kind'];data=row['data']
        if (row['schema']!=1 or row['seq']!=seq or at<last or ended
                or run is not None and row['runId']!=run):
            raise ValueError('Invalid recording chronology/schema/run')
        run=row['runId'];last=at
        if kind=='DATASET_CONFIG':
            if declared or data.get('format')!='normalized-public-v2':
                raise ValueError('Require one normalized-public-v2 declaration')
            declared=True
        if kind=='RAW_MARKET':
            frame=data.get('frameId',-1)
            if pending is not None or frame<=previous_frame:
                raise ValueError('Invalid RAW frame boundary')
            pending=row
        elif kind=='RESEARCH_FRAME':
            if not declared or pending is None or data.get('frameId')!=pending['data']['frameId']:
                raise ValueError('Unbound normalized frame')
            previous_frame=data['frameId']
            if start<=at<=end:
                events=[]
                for index,event in enumerate(data['events']):
                    if (seq,index) in wanted:
                        anchor=next(a for a in spec['anchors'] if (a['seq'],a['eventIndex'])==(seq,index))
                        if (event['kind']!='GAP' or at!=anchor['at']
                                or event['data'].get('sourceMs')!=anchor['sourceMs']
                                or event['data'].get('reason')!=anchor['reason']):
                            raise ValueError('Frozen GAP anchor mismatch')
                        found.add((seq,index))
                    if (event['data'].get('token') in tokens
                            or event['kind']=='GAP' and scope(event['data'],tokens)):
                        events.append(project_event(event,index))
                text=pending['data']['text']
                if events or any(token in text for token in tokens):
                    record=dict(raw=pending,normalized=dict(row, data=dict(data,events=events)),
                        canonicalRawRowSha256=hashlib.sha256((json.dumps(pending,sort_keys=True,separators=(',',':'))).encode()).hexdigest())
                    retained+=len(json.dumps(record).encode())
                    if retained>max_bytes:raise ValueError('Bounded evidence cap exceeded; never truncate')
                    frames.append(record)
            pending=None
        elif start<=at<=end and kind in ('RESEARCH_GAP','RESEARCH_FEED_ERROR') and scope(data,tokens):
            retained+=len(raw)
            if retained>max_bytes:raise ValueError('Bounded evidence cap exceeded')
            standalone.append(row)
        if kind=='RUN_END':
            ended=data.get('complete') is True
            if not ended:raise ValueError('Unclean recording')
    if (not ended or not declared or pending is not None or found!=wanted
            or digest.hexdigest()!=spec['logicalTapeSha256']):
        raise ValueError('Incomplete anchors/frame/recording or wrong logical tape hash')
    return dict(scope='ORIGINAL_RAW_GAP_CONTEXT_NOT_ACCOUNT_OR_FILL_MODEL',spec=spec,
        sourceRows=seq,logicalTapeSha256=digest.hexdigest(),runId=run,
        frames=frames,standaloneGaps=standalone,retainedBytes=retained,
        stateBeforeWindowNotReconstructed=True,rawFramesUnmodified=True,
        normalizedDepthIsProjected=True,fillsInferred=False,pnlInferred=False,
        decision='NO_GO',liveAllowed=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--input-root',required=True)
    p.add_argument('--output',required=True);args=p.parse_args()
    freeze=json.loads(Path('research/phase6/raw-gap-context-freeze.json').read_text())
    for name,digest in freeze['filesSha256'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Frozen context source/spec changed: '+name)
    tapes=[*Path(args.input_root).rglob('events.jsonl.gz'),*Path(args.input_root).rglob('events.jsonl')]
    if len(tapes)!=1:raise ValueError('Require one complete unambiguous tape')
    with open_tape(tapes[0]) as stream:result=extract(stream,freeze['spec'])
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as output:
        with gzip.GzipFile(fileobj=output,mode='wb',mtime=0) as encoded:
            encoded.write((json.dumps(result,separators=(',',':'))+'\n').encode())
    print(json.dumps({k:v for k,v in result.items() if k not in ('frames','standaloneGaps')}),flush=True)


if __name__=='__main__':main()
