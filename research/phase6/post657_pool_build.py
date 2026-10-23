"""Patch a separately generated, frozen exact657 source tree to exact659."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from research.phase6.full_runner_build import once

FREEZE=Path('research/phase6/post657-replay-build-freeze.json')
LABELS=Path('research/phase6/IndexedExecutionLabels.java')


def render(text,spec):
    text=once(text,'bb479f14c58ead5e1b7dc7234dc98f5e9abb06cd586b138bd351a66b9d864f93',spec['poolLogicalSha256'])
    return once(text,'Exact frozen real657 pool required','Exact frozen real659 pool required')


def materialize(source,output):
    spec=json.loads(FREEZE.read_bytes())
    for path,sha in spec['inputsSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Changed659 build dependency '+path)
    source=Path(source);raw=(source/LABELS).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=spec['parentHelperSha256']:raise ValueError('Changed separately frozen exact657 helper')
    output=Path(output);shutil.copytree(source,output);generated=render(raw.decode(),spec).encode()
    if hashlib.sha256(generated).hexdigest()!=spec['generatedHelperSha256']:raise ValueError('Changed generated659 helper')
    (output/LABELS).write_bytes(generated)
    result=dict(scope='GENERATED_SOURCE_LAG0_WITH_EXACT659_POOL_NOT_QUALIFICATION',defaultCoreFilesModified=0,
        poolLogicalSha256=spec['poolLogicalSha256'],expectedReceiptBindings=659,expectedActualComponents=1562,
        parentExact657SourceTreeRebuiltSeparately=True,activationQueueFeeRiskParametersChanged=False,
        independentPaperQualificationAllowed=False,liveAllowed=False)
    (output/'post657-pool-provenance.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(materialize(a.source,a.output),indent=2))
