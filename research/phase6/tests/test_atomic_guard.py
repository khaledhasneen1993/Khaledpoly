import copy
import json
from pathlib import Path
import tempfile
import unittest
from research.phase6.atomic_guard_result import ROOT,verify
from research.phase6.atomic_guard_build import FREEZE,materialize,render


class AtomicGuardTest(unittest.TestCase):
    def test_guard_proof_still_not_runtime_execution(self):
        p=verify(json.loads((ROOT/'atomic-guard-proof.json').read_bytes()))
        self.assertEqual(p['rejectionGuards'],22);self.assertFalse(p['identityConsumerIntegrated'])

    def test_proof_rejects_health_lifetime_or_scope_promotion(self):
        original=json.loads((ROOT/'atomic-guard-proof.json').read_bytes())
        for field,value in [('sessionLedgerMatcherCheckpointLocksHeld',False),('witnessInvalidAfterReturnOrException',False),
            ('fourConcurrentMonitorUsersBlockedThenReleased',False),('crossThreadWitnessRejected',False),
            ('persistentWriteFailuresAndClosedStateRejected',False),('runtimeExecutionSkipImplemented',True),
            ('identityConsumerIntegrated',True),('marketNetPnlRecomputed',True),('liveAllowed',True)]:
            p=copy.deepcopy(original);p[field]=value
            with self.assertRaises(ValueError):verify(p)
        p=copy.deepcopy(original);p['rejectionGuards'].pop()
        with self.assertRaises(ValueError):verify(p)

    def test_exact_generated_source_changes_only_and_default_source_unchanged(self):
        import hashlib
        spec=json.loads(FREEZE.read_bytes())
        before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('polybot-core/src/main/java').rglob('*.java')}
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'build';result=materialize(out)
            self.assertEqual(result['generatedFilesChanged'],4)
            for path,sha in spec['generatedSourcesSha256'].items():self.assertEqual(hashlib.sha256((out/path).read_bytes()).hexdigest(),sha)
        self.assertEqual(before,{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('polybot-core/src/main/java').rglob('*.java')})

    def test_changed_or_duplicate_source_anchors_rejected(self):
        with self.assertRaises(ValueError):render('unexpected','')
        for path in json.loads(FREEZE.read_bytes())['prefixSourcesSha256']:
            with self.assertRaises(ValueError):render(path,'')


if __name__=='__main__':unittest.main()
