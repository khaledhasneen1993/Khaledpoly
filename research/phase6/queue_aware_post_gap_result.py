"""Validate retained original context, reproduce data-only summary; never PnL."""
import gzip
import hashlib
import json
from research.phase6.queue_aware_causal import QROOT
from research.phase6.queue_aware_post_gap_context import spec,summarize

ROOT=QROOT/'post-gap-result'
COMPRESSED_SHA='69bdd106567b5730fdff368bcbd39446164187ae2499912cfa26191925ba96cf'
LOGICAL_SHA='979e23d894f7b4e3d229de9955d7b093f12d96757be1a5580e0ad4428fe4ec64'


def records(path,manifest):
    s=spec();digest=hashlib.sha256();size=count=0;last=-1;last_at=-1;run=None;frame=-1
    with gzip.open(path,'rb') as source:
        for line in source:
            if not line.endswith(b'\n') or len(line)>32*1024*1024:raise ValueError('Incomplete/oversized retained original record')
            digest.update(line);size+=len(line);count+=1
            if size>512*1024*1024 or count>500000:raise ValueError('Bounded original context exceeded')
            rec=json.loads(line);row=rec['input'];at=row['arrivalMs'];seq=row['seq']
            if row['schema']!=1 or seq<=last or at<last_at or not s['startMs']<=at<=s['endMs'] or run is not None and row['runId']!=run:raise ValueError('Changed retained original chronology/run/window')
            last=seq;last_at=at;run=row['runId']
            if row['kind']=='RESEARCH_FRAME':
                raw=rec['raw'];fid=row['data']['frameId']
                if (raw['kind']!='RAW_MARKET' or raw['schema']!=1 or raw['runId']!=run or raw['seq']>=seq
                        or raw['data']['frameId']!=fid or fid<=frame):raise ValueError('Changed retained original RAW frame binding')
                frame=fid
            yield rec
    if (count!=manifest['retainedRecords'] or size!=manifest['retainedBytes'] or digest.hexdigest()!=LOGICAL_SHA
            or digest.hexdigest()!=manifest['retainedLogicalSha256']):raise ValueError('Incomplete/changed original retained context hash/count')


def verify(root=ROOT):
    m=json.loads((root/'context-manifest.json').read_text());artifact=json.loads((root/'artifact-manifest.json').read_text())
    if (m['format']!='original-research-records-jsonl-gzip-v1' or m['spec']!=spec() or not m['complete']
            or m['sourceRows']!=6163831 or m['logicalTapeSha256']!=spec()['logicalTapeSha256']
            or m['compressedSha256']!=COMPRESSED_SHA or m['retainedLogicalSha256']!=LOGICAL_SHA
            or not m['recordsNeverTruncated'] or not m['fullNormalizedDepthUnmodified'] or not m['originalRawFramesUnmodified']
            or not m['tailIdentityBoundToCompleteOriginalSha256'] or m['fillsInferred'] or m['pnlInferred'] or m['liveAllowed']):raise ValueError('Wrong original data-only context contract')
    for name in ['context.records.jsonl.gz','context-manifest.json','data-summary.json']:
        path=root/name;digest=hashlib.sha256()
        with path.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
        member=artifact['members'][name]
        if digest.hexdigest()!=member['sha256'] or path.stat().st_size!=member['bytes']:raise ValueError('Changed original artifact member '+name)
        if name.endswith('.gz') and digest.hexdigest()!=COMPRESSED_SHA:raise ValueError('Changed compressed original context')
    pair=set(json.loads((QROOT/'causal-bindings.json').read_text())['pair'])
    calculated=summarize(dict(spec=spec(),records=records(root/'context.records.jsonl.gz',m)),pair)
    if calculated!=json.loads((root/'data-summary.json').read_text()):raise ValueError('Original data-only recovery summary differs')
    first=calculated['firstFreshBothBookCallback']
    return dict(scope='VERIFIED_ORIGINAL_POST_GAP_CONTEXT_NOT_EXECUTION',retainedRecords=m['retainedRecords'],retainedBytes=m['retainedBytes'],
        completeSourceRows=m['sourceRows'],originalPairObservations=calculated['observationCount'],
        firstFreshBothBookNonemptyFrame=None if first is None else {k:v for k,v in first.items() if k!='books'},
        scopedGapEvents=len(calculated['scopedGaps']),uniqueScopedGapFrames=len({g['seq'] for g in calculated['scopedGaps']}),
        modelFillsCreated=0,netPnlRecomputed=False,candidateAccountSimulated=False,
        independentPaperQualificationAllowed=False,liveAllowed=False)


if __name__=='__main__':print(json.dumps(verify(),indent=2))
