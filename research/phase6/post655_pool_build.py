"""Patch a separately generated, frozen exact655 source tree to exact657."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from research.phase6.full_runner_build import once

FREEZE=Path('research/phase6/post655-replay-build-freeze.json')
LABELS=Path('research/phase6/IndexedExecutionLabels.java')


def render(text,spec):
    text=once(text,'6dcf2f28956569965373d60ff040c2737d4c8412d812ac50def2b5608fb2881f',spec['poolLogicalSha256'])
    return once(text,'Exact frozen real655 pool required','Exact frozen real657 pool required')


def materialize(source,output):
    spec=json.loads(FREEZE.read_bytes())
    for path,sha in spec['inputsSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Changed657 build dependency '+path)
    source=Path(source);raw=(source/LABELS).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=spec['parentHelperSha256']:raise ValueError('Changed separately frozen exact655 helper')
    output=Path(output);shutil.copytree(source,output);generated=render(raw.decode(),spec).encode()
    if hashlib.sha256(generated).hexdigest()!=spec['generatedHelperSha256']:raise ValueError('Changed generated657 helper')
    (output/LABELS).write_bytes(generated)
    result=dict(scope='GENERATED_SOURCE_LAG0_WITH_EXACT657_POOL_NOT_QUALIFICATION',defaultCoreFilesModified=0,
        poolLogicalSha256=spec['poolLogicalSha256'],expectedReceiptBindings=657,expectedActualComponents=1559,
        parentExact655SourceTreeRebuiltSeparately=True,activationQueueFeeRiskParametersChanged=False,
        independentPaperQualificationAllowed=False,liveAllowed=False)
    (output/'post655-pool-provenance.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(materialize(a.source,a.output),indent=2))
