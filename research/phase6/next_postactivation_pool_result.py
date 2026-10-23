"""Verify retained exact647 native-parity artifact; not performance evidence."""
import hashlib,json
from pathlib import Path
import zipfile
from research.phase6.next_postactivation_receipt_pool import ROOT,verify_native
ZIP_SHA='6c854c25ea475c9a97e5d62972858ccabf9982e37a218c94a81070c6b26ea975'
def verify(path=ROOT/'ci-artifact.zip'):
 raw=Path(path).read_bytes()
 if len(raw)!=1233 or hashlib.sha256(raw).hexdigest()!=ZIP_SHA:raise ValueError('Changed exact647 artifact')
 with zipfile.ZipFile(path) as z:
  if set(z.namelist())!={'native-proof.json','summary.json'} or len(z.infolist())!=2:raise ValueError('Unexpected exact647 artifact')
  proof=json.loads(z.read('native-proof.json'));summary=json.loads(z.read('summary.json'))
 result=verify_native(proof,summary)
 return dict(**result,runId=39518124376,jobId=118955093214,artifactId=12308562731,artifactSha256=ZIP_SHA,poolLogicalSha256=summary['poolLogicalSha256'],sourceIdentitiesSha256=summary['sourceIdentitiesSha256'],portionsLogicalSha256=summary['portionsLogicalSha256'],routeComponentCounts=summary['routeComponentCounts'],originalTapeReplayed=False,completeAccountComparisonPerformed=False,decision='NO_GO',nextStep='Freeze one exact647 same-source baseline/QW0 replay; do not retune, change holdout, weaken queue/fees/risk, or repeat parity.')
if __name__=='__main__':print(json.dumps(verify(),indent=2))
