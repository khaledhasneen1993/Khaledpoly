"""Preserve original logical tape bytes while changing storage compression for an offline replay."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tarfile


def prepare(archive,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    count=0;logical_hash=hashlib.sha256();logical_bytes=0
    with tarfile.open(archive,'r|gz') as source:
        for entry in source:
            if not entry.isfile() or not entry.name.startswith('two-hour/ingestor/') or not entry.name.endswith('/events.jsonl'):continue
            count+=1
            if count!=1:raise ValueError('Multiple original journals')
            with source.extractfile(entry) as stream,gzip.open(output/'events.jsonl.gz','wb',compresslevel=1) as target:
                while chunk:=stream.read(1024*1024):
                    logical_hash.update(chunk);logical_bytes+=len(chunk);target.write(chunk)
    if count!=1:raise ValueError('Missing original journal')
    manifest={'sourceRun':39048983750,'sourceArtifact':12110725491,
              'sourceZipSha256':'16e3f3e960f861b5736b948400b9aef290d0caeca39521cc49b3c5106ab81c36',
              'logicalTapeSha256':logical_hash.hexdigest(),'logicalBytes':logical_bytes,
              'transformation':'LOSSLESS_GZIP_STORAGE_ONLY','newMarketDataCollected':False}
    (output/'provenance.json').write_text(json.dumps(manifest))
    print(json.dumps(manifest),flush=True)


def compare(original,replay,output):
    before=json.loads(Path(original).read_text());after=json.loads((Path(replay)/'report.json').read_text())
    keys=('submittedOrders','filledOrders','fills','cash','netRealizedPnl','feesAndSettlementCosts','maxDrawdown','dataGaps','openOrderCount','riskBreaches','halted','residualExpiryWorstCaseNotional','orderTerminalReasons')
    order_starts={};lifetimes=[];reasons={}
    for line in (Path(replay)/'audit.jsonl').open():
        row=json.loads(line);kind=row['kind'];data=row['data']
        if kind=='ORDER':order_starts[data['id']]=data['at']
        elif kind=='ORDER_TERMINAL':
            if data['id'] in order_starts:lifetimes.append(data['at']-order_starts[data['id']])
            reason=data.get('reason','MISSING_REASON');reasons[reason]=reasons.get(reason,0)+1
    lifetimes.sort()
    result={'scope':'OBSERVED_OLD_PAPER_VS_COUNTERFACTUAL_UPDATED_RAW_REPLAY',
            'originalObserved':{k:before.get(k) for k in keys},'updatedCounterfactual':{k:after.get(k) for k in keys},
            'updatedOrderLifetimeMs':{'samples':len(lifetimes),'min':min(lifetimes) if lifetimes else None,'median':lifetimes[len(lifetimes)//2] if lifetimes else None,'max':max(lifetimes) if lifetimes else None},
            'terminalReasons':reasons,'recordingClosedCleanly':after['recordingClosedCleanly'],
            'sameLogicalSourceTape':True,'venueExecutionEvidence':False,'strategyQualified':False,'decision':'NO_GO','liveAllowed':False}
    Path(output).write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
    if not after['recordingClosedCleanly'] or after['decision']!='NO_GO' or 'MISSING_REASON' in reasons:raise ValueError('Incomplete or unreasoned replay')


def main():
    p=argparse.ArgumentParser();p.add_argument('operation',choices=('prepare','compare'));p.add_argument('--archive');p.add_argument('--output',required=True);p.add_argument('--original');p.add_argument('--replay')
    a=p.parse_args()
    if a.operation=='prepare':prepare(a.archive,a.output)
    else:compare(a.original,a.replay,a.output)
if __name__=='__main__':main()
