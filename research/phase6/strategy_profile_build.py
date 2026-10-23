"""Compose the immutable label bridge and one exact frozen-policy patch, offline only."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from research.phase6.session_bridge_build import materialize as bridge,CORE,SESSION

FREEZE=Path('research/phase6/strategy-profile-freeze.json')
PATCH=Path('research/phase6/frozen-strategy-profile.patch')


def materialize(output):
    spec=json.loads(FREEZE.read_text())
    for path,sha in spec['inputsSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Frozen strategy integration input changed '+path)
    prefix=bridge(output);root=Path(output).resolve()
    if hashlib.sha256((root/SESSION).read_bytes()).hexdigest()!=spec['prefixSessionSha256']:raise ValueError('Changed bridge prefix')
    paths=subprocess.run(['git','apply','--numstat',str(PATCH.resolve())],cwd=root,check=True,capture_output=True,text=True).stdout.strip().splitlines()
    if len(paths)!=1 or paths[0].split('\t')[-1]!=str(SESSION):raise ValueError('Policy patch must change only generated ResearchSession')
    subprocess.run(['git','apply','--check',str(PATCH.resolve())],cwd=root,check=True,capture_output=True,text=True)
    subprocess.run(['git','apply',str(PATCH.resolve())],cwd=root,check=True,capture_output=True,text=True)
    base=json.loads(Path('research/phase6/session-bridge-freeze.json').read_text())['coreSourcesSha256']
    if {str(p.relative_to(root)) for p in (root/CORE).rglob('*.java')}!=set(base):raise ValueError('Generated core membership changed')
    for path,sha in base.items():
        expected=spec['integratedSessionSha256'] if path==str(SESSION) else sha
        if hashlib.sha256((root/path).read_bytes()).hexdigest()!=expected:raise ValueError('Unapproved generated policy source '+path)
    result=dict(scope='ISOLATED_FROZEN_POLICY_BUILD_NOT_ACCOUNT_EVALUATION',defaultCoreFilesModified=0,
        frozenCausalRulesPortedWithoutParameterChanges=True,prefix=prefix,
        integratedSessionSha256=spec['integratedSessionSha256'],fullOriginalTapeCoverageProven=False,
        independentPaperQualificationAllowed=False,liveAllowed=False)
    (root/'strategy-build-provenance.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(materialize(a.output),indent=2))
