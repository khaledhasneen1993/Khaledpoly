"""Exact retained frontier preimages; no tape/RPC and no weakened full source index."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from research.phase6.indexed_execution_inputs import prepare as prefix
from research.phase6.preactivation_diagnosis import load,ROOT,ZIP_SHA


def prepare(output):
    original=load();result=prefix(output);out=Path(output)
    archive=ROOT/'ci-artifact.zip'
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=ZIP_SHA:raise ValueError('Changed original frontier artifact')
    rows=[]
    with zipfile.ZipFile(archive) as z:
        for profile in ('candidate','baseline'):
            f=json.loads(z.read('development/'+profile+'/failure.json'));a=f['labels']['lastAttemptedOriginalObservation']
            rows.append(dict(profile=profile,seq=a['seq'],eventIndex=a['eventIndex'],at=a['at'],data=a['observation'],
                originalOrderDiagnostics=f['sessionAfterSuspension']['makerExecutionDiagnostics']))
    value=dict(scope='EXACT_ORIGINAL_FRONTIER_PREIMAGES_SYNTHETIC_SESSION_NOT_TAPE',observations=rows)
    raw=(json.dumps(value,separators=(',',':'))+'\n').encode();(out/'frontier-preimages.json').write_bytes(raw)
    return dict(prefix=result,frontierSha256=hashlib.sha256(raw).hexdigest(),originalFrontiers=[r['seq'] for r in rows],newPublicReads=0,originalTapeReplayed=False,marketNetPnlRecomputed=False,liveAllowed=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(prepare(a.output),indent=2))
