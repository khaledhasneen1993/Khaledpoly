"""Verify retained exact649 native-parity artifact; not performance evidence."""
import hashlib
import json
from pathlib import Path
import zipfile

from research.phase6.post647_receipt_pool import ROOT,verify_native

ZIP_SHA='178d32559cbfff83689f85fbba608e491155a034b3f60b0270fc1c89292a03a7'


def verify(path=ROOT/'ci-artifact.zip'):
    raw=Path(path).read_bytes()
    if len(raw)!=1235 or hashlib.sha256(raw).hexdigest()!=ZIP_SHA:raise ValueError('Changed exact649 artifact')
    with zipfile.ZipFile(path) as z:
        if set(z.namelist())!={'native-proof.json','summary.json'} or len(z.infolist())!=2:raise ValueError('Unexpected exact649 artifact')
        proof=json.loads(z.read('native-proof.json'));summary=json.loads(z.read('summary.json'))
    result=verify_native(proof,summary)
    return dict(**result,runId=39534147635,jobId=119006749423,artifactId=12317191472,artifactSha256=ZIP_SHA,
        poolLogicalSha256=summary['poolLogicalSha256'],sourceIdentitiesSha256=summary['sourceIdentitiesSha256'],
        portionsLogicalSha256=summary['portionsLogicalSha256'],routeComponentCounts=summary['routeComponentCounts'],
        originalTapeReplayed=False,completeAccountComparisonPerformed=False,decision='NO_GO',
        nextStep='Freeze one exact649 same-source baseline/QW0 replay; do not retune, change holdout, weaken queue/fees/risk, or repeat parity.')


if __name__=='__main__':print(json.dumps(verify(),indent=2))
