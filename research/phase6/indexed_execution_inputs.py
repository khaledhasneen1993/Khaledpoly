"""Original prefix preimages from retained diagnostics; synthetic test envelope only."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from research.phase6.native_source_index import prepare as source
from research.phase6.expanded_receipt_pool import write as pool
from research.phase6.complete_source_index import reconstruct,SourceIdentityIndex

def prepare(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    source(out/'source');pool(out/'pool')
    rows,report,_=reconstruct();actual=json.loads((out/'pool/source-identities.json').read_bytes())['observations'][0]
    archive=Path('research/experiments/expanded-receipt-pool-20261020/ci-artifact.zip')
    if hashlib.sha256(archive.read_bytes()).hexdigest()!='37f62ac28456837a107eb021c7f7716e57fb9662f05902dcab89d253e685513e':raise ValueError('Changed original628 diagnostic')
    with zipfile.ZipFile(archive) as z:
        attempts=[json.loads(z.read('original-diagnosis/'+p+'/failure.json'))['labels']['lastAttemptedOriginalObservation'] for p in ('baseline','candidate')]
    if attempts[0]!=attempts[1]:raise ValueError('Original stopped identities differ')
    old=attempts[0];second=dict(seq=old['seq'],eventIndex=old['eventIndex'],at=old['at'],data=old['observation'])
    observations=[actual,second];reader=SourceIdentityIndex(rows,report)
    for row in observations:reader.consume(row['seq'],row['eventIndex'],row['at'],row['data'])
    if [(r['seq'],r['eventIndex']) for r in observations]!=[(97,0),(628,0)]:raise ValueError('Require exact first TWO original identities')
    prefix=dict(scope='EXACT_FIRST_TWO_ORIGINAL_PREIMAGES_SYNTHETIC_SESSION_ENVELOPE_NOT_TAPE',observations=observations)
    raw=(json.dumps(prefix,separators=(',',':'))+'\n').encode();(out/'original-prefix.json').write_bytes(raw)
    return dict(scope=prefix['scope'],prefixSha256=hashlib.sha256(raw).hexdigest(),originalPrefixIdentities=2,
                completeOriginalTapeReplayed=False,newPublicReads=0,marketNetPnlRecomputed=False,liveAllowed=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(prepare(a.output),indent=2))
