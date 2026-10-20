"""Verify retained successful Java21 bounded artifact against frozen local evidence."""
import hashlib
import json
from pathlib import Path
import zipfile
from research.phase6.source_lag_result import ROOT,verify,verify_inputs,require

ZIP_SHA='ca77279140a0d98592ced523556446e71c4ff941012b95e024ca3ed0ce1fb76e'
MEMBERS=set('atomic-guard-proof.json default-parity.json atomic-verification.json differential-verification.json indexed-execution-proof.json no-order-proof.json original-integration-verification.json preactivation-proof.json preactivation-session-proof.json previous-original-context.json source-lag-proof.json source-lag-verification.json temporal-verification.json'.split())


def load(archive=None):
    archive=Path(archive) if archive is not None else ROOT/'ci-artifact.zip'
    raw=archive.read_bytes();require(len(raw)==10611 and hashlib.sha256(raw).hexdigest()==ZIP_SHA,'Changed source-lag CI artifact')
    verify_inputs()
    with zipfile.ZipFile(archive) as z:
        require(len(z.infolist())==13 and set(z.namelist())=={'proof/'+n for n in MEMBERS} and all(m.file_size<1024*1024 for m in z.infolist()),'Wrong bounded proof archive members')
        read=lambda name:json.loads(z.read('proof/'+name))
        for name in ('source-lag-proof.json','previous-original-context.json'):
            require(read(name)==json.loads((ROOT/name).read_bytes()),'Java21/local evidence differs '+name)
        require(verify(read('source-lag-proof.json'))==read('source-lag-verification.json')==json.loads((ROOT/'verification.json').read_bytes()),'Source-lag verification differs')
        old=Path('research/experiments/preactivation-20261020')
        for name in ('preactivation-proof.json','preactivation-session-proof.json','indexed-execution-proof.json'):
            require(read(name)==json.loads((old/name).read_bytes()),'Previous generated behavior changed '+name)
        from research.phase6.preactivation_result import verify as temporal
        from research.phase6.indexed_execution_result import verify as indexed
        from research.phase6.atomic_guard_result import verify as atomic
        from research.phase6.no_order_result import verify as differential
        require(temporal(old)==read('temporal-verification.json'),'Prior temporal verifier differs')
        require(indexed(read('indexed-execution-proof.json'))==read('original-integration-verification.json'),'Indexed proof differs')
        require(atomic(read('atomic-guard-proof.json'))==read('atomic-verification.json'),'Atomic proof differs')
        require(differential(read('no-order-proof.json'))==read('differential-verification.json'),'Counterexample proof differs')
        require(read('default-parity.json')==json.loads(Path('research/experiments/session-bridge-20261019/default-before.json').read_bytes()),'Default oracle changed')
    return dict(scope='VERIFIED_JAVA21_SOURCE_LAG_PROOF_ONLY_NOT_RUNTIME_AUTHORIZATION',sourceCommit='7d88f0655bb9c794937c9c0548f26ff21256930e',runId=39450218277,jobId=118722737363,artifactId=12277499794,artifactSha256=ZIP_SHA,artifactBytes=10611,verifiedMembers=13,matcherDifferentials=5144,distinctFutureContinuations=5144,nativeProofEqualsLocal=True,priorAtomicDefaultAndIndexedProofsUnchanged=True,newAtomicSessionGuardImplemented=False,newRuntimeShortcutEnabled=False,originalTapeReplayed=False,marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False,decision='NO_GO')


if __name__=='__main__':print(json.dumps(load(),indent=2))
