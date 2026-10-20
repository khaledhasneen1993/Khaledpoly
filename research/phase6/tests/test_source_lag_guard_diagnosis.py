import copy
import json
from pathlib import Path
import unittest
import zipfile
from research.phase6.source_lag_guard_diagnosis import ROOT,load,frontier,reconstruct


class OriginalSourceLagGuardDiagnosisTest(unittest.TestCase):
    def test_exact_original_frontiers(self):
        r=load();self.assertEqual(r['results']['candidate']['sequence'],9035)
        self.assertEqual(r['results']['baseline']['orders'][0]['sourceAfterActivationMs'],18)
        self.assertEqual(r['results']['candidate']['orders'][0]['sourceAfterActivationMs'],8)
        self.assertFalse(r['marketNetPnlRecomputed'])

    def test_queue_or_temporal_promotion_rejected(self):
        rows,_,_=reconstruct();cfg=json.loads(Path('research/phase2/research-config.json').read_bytes())
        with zipfile.ZipFile(ROOT/'ci-artifact.zip') as z:
            f=json.loads(z.read('development/candidate/failure.json'));audit=[json.loads(x) for x in z.read('development/candidate/failure-audit.jsonl').splitlines()]
        for key,value in [('initialQueueAhead',0),('activatedMs',1792269594511),('eligiblePrintVolume',1)]:
            with self.subTest(key=key):
                changed=copy.deepcopy(f);changed['sessionAfterSuspension']['makerExecutionDiagnostics'][0][key]=value
                with self.assertRaises(ValueError):frontier(changed,audit,rows,cfg,'candidate')
