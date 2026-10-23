"""Independent retained643 native/source-prefix proof, not an account-performance result."""
import io
import json
from pathlib import Path
import zipfile
from research.phase6.expanded_receipt_pool import ROOT,build,next_missing,verify_native,verify_stop
from research.phase6.first_blocker_receipt import digest
from research.phase6.full_runner_diagnosis import STORED_SHA

SHA='37f62ac28456837a107eb021c7f7716e57fb9662f05902dcab89d253e685513e'

def verify(path=ROOT/'ci-artifact.zip'):
    raw=Path(path).read_bytes()
    if digest(raw)!=SHA:raise ValueError('Changed expanded643 CI artifact')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if len(set(z.namelist()))!=len(z.infolist()) or any(m.file_size>1024*1024 for m in z.infolist()):raise ValueError('Invalid bounded proof archive')
        read=lambda name:json.loads(z.read(name))
        summary=json.loads((ROOT/'summary.json').read_text())
        if read('summary.json')!=summary:raise ValueError('Changed original643 source summary')
        native=verify_native(read('native-proof.json'),summary)
        if read('default-after.json')!=json.loads(Path('research/experiments/session-bridge-20261019/default-before.json').read_text()):raise ValueError('Default-off report differs')
        expected=next_missing(build());config=json.loads(Path('research/phase2/research-config.json').read_text())
        results={};accounts={}
        for policy in ('baseline','candidate'):
            proof=read('original-diagnosis/'+policy+'/failure.json')
            results[policy]=verify_stop(proof,expected,policy=='candidate',config)
            ledger=proof['ledgerAfterSuspension'];accounts[policy]=dict(orderHistory=len(ledger['orders']),holdings=len(ledger['holdings']),executions=len(ledger['executions']))
        saved=read('original-diagnosis/verification.json')
        if (saved['scope']!='SAME_ORIGINAL_SOURCE_EXPANDED643_NEXT_BLOCKER_NOT_ACCOUNT_COMPARISON'
                or saved['results']!=results or results['baseline']!=results['candidate']
                or saved['inputStoredSha256']!=STORED_SHA or saved['poolLogicalSha256']!=summary['poolLogicalSha256']):raise ValueError('Same-source expanded prefix proof differs')
        for flag in ('fullOriginalTapeCoverageProven','completeAccountComparisonPerformed','marketNetPnlRecomputed','independentPaperQualificationAllowed','liveAllowed'):
            if saved[flag] is not False:raise ValueError('Failed prefix cannot qualify account performance')
    return dict(scope='VERIFIED_EXPANDED643_NATIVE_AND_ORIGINAL628_STOP_NOT_ACCOUNT_RESULT',
        nativeIdentities=native['originalIdentities'],nativeComponentTuples=native['componentTuples'],
        original97ConsumedOnce=True,original16ComponentsConserved=True,nextOriginalCoordinate=[expected['seq'],expected['eventIndex']],
        sameSourceAndCoverageBothPolicies=True,prefixAccountCounts=accounts,
        generalNoOrderOptimizationProven=False,marketNetPnlRecomputed=False,
        completeAccountComparisonPerformed=False,independentPaperQualificationAllowed=False,liveAllowed=False)

if __name__=='__main__':print(json.dumps(verify(),indent=2))
