"""Verify retained exact651 native-parity artifact; not performance evidence."""
import hashlib
import json
from pathlib import Path
import zipfile

from research.phase6.post649_receipt_pool import ROOT,verify_native

ZIP_SHA='b50b77dcd5de6c23f6050a46104b54adebb7e4fc333bf49b7701eb9bc186e3e7'


def verify(path=ROOT/'ci-artifact.zip'):
    raw=Path(path).read_bytes()
    if len(raw)!=1230 or hashlib.sha256(raw).hexdigest()!=ZIP_SHA:raise ValueError('Changed exact651 artifact')
    with zipfile.ZipFile(path) as z:
        if set(z.namelist())!={'native-proof.json','summary.json'} or len(z.infolist())!=2:raise ValueError('Unexpected exact651 artifact')
        proof=json.loads(z.read('native-proof.json'));summary=json.loads(z.read('summary.json'))
    result=verify_native(proof,summary)
    return dict(**result,runId=39572013713,jobId=119128270610,artifactId=12331629082,artifactSha256=ZIP_SHA,
        poolLogicalSha256=summary['poolLogicalSha256'],sourceIdentitiesSha256=summary['sourceIdentitiesSha256'],
        portionsLogicalSha256=summary['portionsLogicalSha256'],routeComponentCounts=summary['routeComponentCounts'],
        originalTapeReplayed=False,completeAccountComparisonPerformed=False,decision='NO_GO',
        nextStep='Freeze one exact651 same-source baseline/QW0 replay; do not retune, change holdout, weaken queue/fees/risk, or repeat parity.')


if __name__=='__main__':print(json.dumps(verify(),indent=2))
