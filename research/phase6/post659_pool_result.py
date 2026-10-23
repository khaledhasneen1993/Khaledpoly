"""Verify retained exact661 native-parity artifact; not performance evidence."""
import hashlib
import json
from pathlib import Path
import zipfile

from research.phase6.post659_receipt_pool import ROOT,verify_native

ZIP_SHA='121b954d37d05191f7b7d2efa4c03bc1f7920d8e563e4189504fdd222b6e0b2c'


def verify(path=ROOT/'ci-artifact.zip'):
    raw=Path(path).read_bytes()
    if len(raw)!=1231 or hashlib.sha256(raw).hexdigest()!=ZIP_SHA:raise ValueError('Changed exact661 artifact')
    with zipfile.ZipFile(path) as z:
        if set(z.namelist())!={'native-proof.json','summary.json'} or len(z.infolist())!=2:raise ValueError('Unexpected exact661 artifact')
        proof=json.loads(z.read('native-proof.json'));summary=json.loads(z.read('summary.json'))
    result=verify_native(proof,summary)
    return dict(**result,runId=39933500222,jobId=120347296378,artifactId=12493127348,artifactSha256=ZIP_SHA,
        poolLogicalSha256=summary['poolLogicalSha256'],sourceIdentitiesSha256=summary['sourceIdentitiesSha256'],
        portionsLogicalSha256=summary['portionsLogicalSha256'],routeComponentCounts=summary['routeComponentCounts'],
        originalTapeReplayed=False,completeAccountComparisonPerformed=False,decision='NO_GO',
        nextStep='Freeze one exact661 same-source baseline/QW0 replay; do not retune, change holdout, weaken queue/fees/risk, or repeat parity.')


if __name__=='__main__':print(json.dumps(verify(),indent=2))
