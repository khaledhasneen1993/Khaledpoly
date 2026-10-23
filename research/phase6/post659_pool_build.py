"""Patch a separately generated, frozen exact659 source tree to exact661."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from research.phase6.full_runner_build import once

FREEZE=Path('research/phase6/post659-replay-build-freeze.json')
LABELS=Path('research/phase6/IndexedExecutionLabels.java')


def render(text,spec):
    text=once(text,'977b090ad0737c6c43fe9dd8d0fd7b96f2da94534f29b31f7b935f769232355b',spec['poolLogicalSha256'])
    return once(text,'Exact frozen real659 pool required','Exact frozen real661 pool required')


def materialize(source,output):
    spec=json.loads(FREEZE.read_bytes())
    for path,sha in spec['inputsSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Changed661 build dependency '+path)
    source=Path(source);raw=(source/LABELS).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=spec['parentHelperSha256']:raise ValueError('Changed separately frozen exact659 helper')
    output=Path(output);shutil.copytree(source,output);generated=render(raw.decode(),spec).encode()
    if hashlib.sha256(generated).hexdigest()!=spec['generatedHelperSha256']:raise ValueError('Changed generated661 helper')
    (output/LABELS).write_bytes(generated)
    result=dict(scope='GENERATED_SOURCE_LAG0_WITH_EXACT661_POOL_NOT_QUALIFICATION',defaultCoreFilesModified=0,
        poolLogicalSha256=spec['poolLogicalSha256'],expectedReceiptBindings=661,expectedActualComponents=1564,
        parentExact659SourceTreeRebuiltSeparately=True,activationQueueFeeRiskParametersChanged=False,
        independentPaperQualificationAllowed=False,liveAllowed=False)
    (output/'post659-pool-provenance.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(materialize(a.source,a.output),indent=2))
