"""Generated SOURCE_LAG0 build pinned to the separately frozen exact651 pool."""
import argparse
import hashlib
import json
from pathlib import Path

from research.phase6.post647_pool_build import materialize as prefix,LABELS
from research.phase6.full_runner_build import once

FREEZE=Path('research/phase6/post649-replay-build-freeze.json')
PARENT_HELPER_SHA='a98e946e853e37c84e235763d5a90cbcff5c13d9fdb8caaff61a97ab53609751'


def render(text,spec):
    text=once(text,'377a4394ec3542dfa085f33771a238e030142303b327ef8a14caf3b93de6481a',spec['poolLogicalSha256'])
    return once(text,'Exact frozen real649 pool required','Exact frozen real651 pool required')


def materialize(output):
    spec=json.loads(FREEZE.read_bytes())
    for path,sha in spec['inputsSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Changed651 build dependency '+path)
    provenance=prefix(output);target=Path(output)/LABELS;raw=target.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_HELPER_SHA:raise ValueError('Changed exact649 helper prefix')
    generated=render(raw.decode(),spec).encode()
    if hashlib.sha256(generated).hexdigest()!=spec['generatedHelperSha256']:raise ValueError('Changed generated651 helper')
    target.write_bytes(generated)
    result=dict(scope='GENERATED_SOURCE_LAG0_WITH_EXACT651_POOL_NOT_QUALIFICATION',defaultCoreFilesModified=0,
        poolLogicalSha256=spec['poolLogicalSha256'],expectedReceiptBindings=651,expectedActualComponents=1550,
        activationQueueFeeRiskParametersChanged=False,independentPaperQualificationAllowed=False,liveAllowed=False,prefix=provenance)
    (Path(output)/'post649-pool-provenance.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(materialize(a.output),indent=2))
