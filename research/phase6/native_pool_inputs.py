"""Exact original tradeId preimages for native parity, not an execution tape."""
import argparse
from collections import defaultdict
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
from research.phase6.dq3_bottleneck_receipts import traffic
from research.phase6.queue_aware_recovery_result import load

ROOT=Path('research/experiments/cached-receipt-pool-20261020')


def prepare():
    compressed=(ROOT/'bindings.json.gz').read_bytes()
    if hashlib.sha256(compressed).hexdigest()!='76be579d7fffe2b9449a502bf8258bf990759a68a458291f82fbad07a417f329':
        raise ValueError('Changed partial receipt pool')
    raw=gzip.decompress(compressed)
    if hashlib.sha256(raw).hexdigest()!='745dadce6749d701ba6048ab1ef76f3f43b354c058e27e9163c2174725aaceea':
        raise ValueError('Changed logical partial pool')
    pool=json.loads(raw);samples=defaultdict(set)
    def retain(sample):
        samples[sample['transaction_hash']].add(json.dumps(sample,separators=(',',':'),ensure_ascii=False))
    for state in traffic()['states']:
        for observation in state['observations']:retain(observation['sample'])
    for t in load()[0]['transactions']:retain(t['sample'])
    rows=[]
    for b in pool['bindings']:
        candidates=[s for s in samples[b['transactionHash']] if hashlib.sha256(s.encode()).hexdigest()==b['publicTradeIdSha256']]
        if len(candidates)!=1:raise ValueError('Cannot recover unique EXACT original tradeId bytes')
        identity=candidates[0];sample=json.loads(identity)
        if (sample['asset_id']!=b['token'] or sample['side']!=b['side'] or int(sample['timestamp'])!=b['sourceMs']
                or any(Decimal(str(sample[k]))!=Decimal(str(b[k])) for k in ('price','size'))):
            raise ValueError('Original public identity/normalized facts differ')
        rows.append(dict(seq=b['seq'],eventIndex=b['eventIndex'],at=b['at'],data={
            **{k:b[k] for k in ('token','side','price','size','sourceMs')},'tradeId':identity}))
    if len(rows)!=642:raise ValueError('Require ALL642 exact original observations')
    return raw,dict(scope='EXACT642_ORIGINAL_IDENTITY_INPUTS_NOT_EXECUTION_TAPE',observations=rows,
        modelFillsCreated=0,netPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raw,rows=prepare()
    a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'pool.json').write_bytes(raw)
    encoded=(json.dumps(rows,separators=(',',':'))+'\n').encode();(a.output/'source-identities.json').write_bytes(encoded)
    print(json.dumps(dict(originalIdentities=len(rows['observations']),sourceIdentitiesSha256=hashlib.sha256(encoded).hexdigest(),
                         poolLogicalSha256=hashlib.sha256(raw).hexdigest(),newPublicReads=0,modelFillsCreated=0)))


if __name__=='__main__':main()
