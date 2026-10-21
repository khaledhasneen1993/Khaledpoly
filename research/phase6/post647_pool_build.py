"""Generated SOURCE_LAG0 build pinned to the separately frozen exact649 pool."""
import argparse
import hashlib
import json
from pathlib import Path

from research.phase6.source_lag_guard_build import materialize as prefix,LABELS
from research.phase6.full_runner_build import once

FREEZE=Path('research/phase6/post647-replay-build-freeze.json')
PARENT_HELPER_SHA='6fae06a13dd1d49c95d2969245326599332a19a8bb525e42dff434b80b4582e7'


def render(text,spec):
    text=once(text,'c41eda69ffe03ed06835a9fac403401f0d68aa3fa92b019bf37d410a212ee231',spec['poolLogicalSha256'])
    return once(text,'Exact frozen real643 pool required','Exact frozen real649 pool required')


def materialize(output):
    spec=json.loads(FREEZE.read_bytes())
    for path,sha in spec['inputsSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Changed649 build dependency '+path)
    provenance=prefix(output);target=Path(output)/LABELS;raw=target.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_HELPER_SHA:raise ValueError('Changed SOURCE_LAG0 helper prefix')
    generated=render(raw.decode(),spec).encode()
    if hashlib.sha256(generated).hexdigest()!=spec['generatedHelperSha256']:raise ValueError('Changed generated649 helper')
    target.write_bytes(generated)
    result=dict(scope='GENERATED_SOURCE_LAG0_WITH_EXACT649_POOL_NOT_QUALIFICATION',defaultCoreFilesModified=0,
        poolLogicalSha256=spec['poolLogicalSha256'],expectedReceiptBindings=649,expectedActualComponents=1540,
        activationQueueFeeRiskParametersChanged=False,independentPaperQualificationAllowed=False,liveAllowed=False,prefix=provenance)
    (Path(output)/'post647-pool-provenance.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(materialize(a.output),indent=2))
