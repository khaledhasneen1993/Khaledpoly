"""Verify retained exact659 native-parity artifact; not performance evidence."""
import hashlib
import json
from pathlib import Path
import zipfile

from research.phase6.post657_receipt_pool import ROOT,verify_native

ZIP_SHA='f68081a96160708fd386d5128fc9c90937031c9e0f91b34f824c608344c9a973'


def verify(path=ROOT/'ci-artifact.zip'):
    raw=Path(path).read_bytes()
    if len(raw)!=1235 or hashlib.sha256(raw).hexdigest()!=ZIP_SHA:raise ValueError('Changed exact659 artifact')
    with zipfile.ZipFile(path) as z:
        if set(z.namelist())!={'native-proof.json','summary.json'} or len(z.infolist())!=2:raise ValueError('Unexpected exact659 artifact')
        proof=json.loads(z.read('native-proof.json'));summary=json.loads(z.read('summary.json'))
    result=verify_native(proof,summary)
    return dict(**result,runId=39907805325,jobId=120263653691,artifactId=12481512508,artifactSha256=ZIP_SHA,
        poolLogicalSha256=summary['poolLogicalSha256'],sourceIdentitiesSha256=summary['sourceIdentitiesSha256'],
        portionsLogicalSha256=summary['portionsLogicalSha256'],routeComponentCounts=summary['routeComponentCounts'],
        originalTapeReplayed=False,completeAccountComparisonPerformed=False,decision='NO_GO',
        nextStep='Freeze one exact659 same-source baseline/QW0 replay; do not retune, change holdout, weaken queue/fees/risk, or repeat parity.')


if __name__=='__main__':print(json.dumps(verify(),indent=2))
