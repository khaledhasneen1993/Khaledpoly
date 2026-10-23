"""Verify retained exact657 native-parity artifact; not performance evidence."""
import hashlib
import json
from pathlib import Path
import zipfile

from research.phase6.post655_receipt_pool import ROOT,verify_native

ZIP_SHA='6c07967f7b302dfed43f8faf36a75955b318e1536b1daf2318e559033be38495'


def verify(path=ROOT/'ci-artifact.zip'):
    raw=Path(path).read_bytes()
    if len(raw)!=1236 or hashlib.sha256(raw).hexdigest()!=ZIP_SHA:raise ValueError('Changed exact657 artifact')
    with zipfile.ZipFile(path) as z:
        if set(z.namelist())!={'native-proof.json','summary.json'} or len(z.infolist())!=2:raise ValueError('Unexpected exact657 artifact')
        proof=json.loads(z.read('native-proof.json'));summary=json.loads(z.read('summary.json'))
    result=verify_native(proof,summary)
    return dict(**result,runId=39874579658,jobId=120156941028,artifactId=12467179513,artifactSha256=ZIP_SHA,
        poolLogicalSha256=summary['poolLogicalSha256'],sourceIdentitiesSha256=summary['sourceIdentitiesSha256'],
        portionsLogicalSha256=summary['portionsLogicalSha256'],routeComponentCounts=summary['routeComponentCounts'],
        originalTapeReplayed=False,completeAccountComparisonPerformed=False,decision='NO_GO',
        nextStep='Freeze one exact657 same-source baseline/QW0 replay; do not retune, change holdout, weaken queue/fees/risk, or repeat parity.')


if __name__=='__main__':print(json.dumps(verify(),indent=2))
