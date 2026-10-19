"""Materialize an explicitly isolated, exact-source research build; never edit the default core."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

FREEZE=Path('research/phase6/session-bridge-freeze.json')
PATCH=Path('research/phase6/mixed-session-bridge.patch')
CORE=Path('polybot-core/src/main/java')
SESSION=CORE/'com/polybot/hft/paper/ResearchSession.java'


def check_sources(spec):
    actual={str(p) for p in CORE.rglob('*.java')}
    if actual!=set(spec['coreSourcesSha256']):raise ValueError('Core source membership changed')
    for path,sha in {**spec['coreSourcesSha256'],**spec['buildInputsSha256']}.items():
        p=Path(path)
        if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=sha:raise ValueError('Frozen bridge input changed '+path)


def materialize(output):
    spec=json.loads(FREEZE.read_text());check_sources(spec)
    target=Path(output).resolve()
    if target.is_relative_to(Path.cwd().resolve()):raise ValueError('Use a separate temporary build directory outside the repository')
    target.mkdir(parents=True,exist_ok=False)
    shutil.copytree(CORE,target/CORE)
    paths=subprocess.run(['git','apply','--numstat',str(PATCH.resolve())],cwd=target,check=True,capture_output=True,text=True).stdout.strip().splitlines()
    if len(paths)!=1 or paths[0].split('\t')[-1]!=str(SESSION):raise ValueError('Research patch may modify only the generated session')
    subprocess.run(['git','apply','--check',str(PATCH.resolve())],cwd=target,check=True,capture_output=True,text=True)
    subprocess.run(['git','apply',str(PATCH.resolve())],cwd=target,check=True,capture_output=True,text=True)
    generated={str(p.relative_to(target)) for p in (target/CORE).rglob('*.java')}
    if generated!=set(spec['coreSourcesSha256']):raise ValueError('Unexpected generated source membership')
    for path,sha in spec['coreSourcesSha256'].items():
        expected=spec['patchedSessionSha256'] if path==str(SESSION) else sha
        if hashlib.sha256((target/path).read_bytes()).hexdigest()!=expected:raise ValueError('Unexpected generated source change '+path)
    report=dict(scope='ISOLATED_SOURCE_BUILD_NOT_ACCOUNT_OR_PROFIT_PROOF',coreSources=len(spec['coreSourcesSha256']),
        defaultCoreFilesModified=0,generatedCoreFilesChanged=[str(SESSION)],
        originalSessionSha256=spec['coreSourcesSha256'][str(SESSION)],patchedSessionSha256=spec['patchedSessionSha256'],
        patchSha256=spec['buildInputsSha256'][str(PATCH)],frozenStrategyChanged=False,
        independentPaperQualificationAllowed=False,liveAllowed=False)
    (target/'build-provenance.json').write_text(json.dumps(report,indent=2)+'\n');return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(materialize(a.output),indent=2))
