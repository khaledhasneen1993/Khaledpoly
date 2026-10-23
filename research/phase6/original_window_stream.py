"""Stream exact original normalized+RAW records; bounded memory, no truncation."""
import gzip
import hashlib
import json
from pathlib import Path

MAX_ROW_BYTES=16*1024*1024
MAX_RETAINED_BYTES=512*1024*1024


def extract_to(stream,spec,path,observe,*,max_bytes=MAX_RETAINED_BYTES):
    if len(spec['states'])!=1 or not 0<spec['endMs']-spec['startMs']<=30000:raise ValueError('One fixed bounded original window required')
    state=spec['states'][0]
    if spec['startMs']>state['submitMs']-2000:raise ValueError('Missing original book warmup')
    path=Path(path);partial=path.with_name(path.name+'.partial')
    if path.exists() or partial.exists():raise ValueError('Do not overwrite original evidence')
    digest=hashlib.sha256();retained=hashlib.sha256();seq=0;last=-1;run=None;declared=False;pending=None;previous=-1
    size=0;count=0;anchor=False;tail=False;last_line=None;ended=False
    with partial.open('xb') as target:
        with gzip.GzipFile(filename='',fileobj=target,mode='wb',mtime=0) as gz:
            for line in stream:
                if not line.endswith(b'\n') or len(line)>MAX_ROW_BYTES:raise ValueError('Incomplete/oversized original row')
                digest.update(line);seq+=1;last_line=line
                if tail:continue
                row=json.loads(line);at=row['arrivalMs'];kind=row['kind'];data=row['data']
                if row['schema']!=1 or row['seq']!=seq or at<last or ended or run is not None and row['runId']!=run:raise ValueError('Changed prefix chronology/schema/run')
                last=at;run=row['runId']
                if kind=='DATASET_CONFIG':
                    if declared or data.get('format')!='normalized-public-v2' or not data.get('strategyIndependent'):raise ValueError('Wrong original source declaration')
                    declared=True
                if kind=='RAW_MARKET':
                    if pending is not None or data['frameId']<=previous:raise ValueError('Changed original RAW frame')
                    pending=row
                elif kind=='RESEARCH_FRAME':
                    if not declared or pending is None or pending['data']['frameId']!=data['frameId']:raise ValueError('Unbound original normalized frame')
                    previous=data['frameId']
                if spec['startMs']<=at<=spec['endMs'] and kind.startswith('RESEARCH_'):
                    record=dict(input=row)
                    if kind=='RESEARCH_FRAME':record['raw']=pending
                    encoded=(json.dumps(record,separators=(',',':'))+'\n').encode();size+=len(encoded)
                    if size>max_bytes:raise ValueError('Streaming evidence cap exceeded; never truncate')
                    gz.write(encoded);retained.update(encoded);count+=1;observe(record)
                if seq==state['originalSequence']:
                    if not kind.startswith('RESEARCH_') or at!=state['submitMs']:raise ValueError('Changed original anchor')
                    anchor=True
                if kind=='RESEARCH_FRAME':pending=None
                if kind=='RUN_END':ended=data.get('complete') is True
                if at>spec['endMs'] and pending is None:tail=True
    terminal=json.loads(last_line or b'{}')
    if (not declared or not anchor or pending is not None or seq!=spec['sourceRows'] or digest.hexdigest()!=spec['logicalTapeSha256']
            or terminal.get('kind')!='RUN_END' or not terminal['data'].get('complete') or terminal.get('seq')!=seq or terminal.get('runId')!=run):
        raise ValueError('Wrong complete original source/hash/anchor; partial evidence not accepted')
    partial.rename(path)
    compressed=hashlib.sha256()
    with path.open('rb') as saved:
        for chunk in iter(lambda:saved.read(1024*1024),b''):compressed.update(chunk)
    return dict(format='original-research-records-jsonl-gzip-v1',spec=spec,complete=True,sourceRows=seq,
        logicalTapeSha256=digest.hexdigest(),retainedRecords=count,retainedBytes=size,retainedLogicalSha256=retained.hexdigest(),
        compressedSha256=compressed.hexdigest(),maxRetainedBytes=max_bytes,
        fullNormalizedDepthUnmodified=True,originalRawFramesUnmodified=True,tailIdentityBoundToCompleteOriginalSha256=True,
        recordsNeverTruncated=True,fillsInferred=False,pnlInferred=False,liveAllowed=False)
