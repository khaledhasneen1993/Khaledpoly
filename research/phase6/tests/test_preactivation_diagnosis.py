import copy
import json
import unittest
import zipfile
from pathlib import Path
from research.phase6.preactivation_diagnosis import ROOT,load,frontier,reconstruct


class OriginalTemporalDiagnosisTest(unittest.TestCase):
    def test_original_results(self):
        r=load();self.assertFalse(r['marketNetPnlRecomputed']);self.assertEqual(r['results']['candidate']['sequence'],8739)

    def test_active_queue_or_source_mutation_rejected(self):
        rows,_,_=reconstruct();cfg=json.loads(Path('research/phase2/research-config.json').read_bytes())
        with zipfile.ZipFile(ROOT/'ci-artifact.zip') as z:
            f=json.loads(z.read('development/candidate/failure.json'));audit=[json.loads(x) for x in z.read('development/candidate/failure-audit.jsonl').splitlines()]
        for key,value in [('initialQueueAhead',0),('activatedMs',1792269594437),('eligiblePrintVolume',1)]:
            with self.subTest(key=key):
                changed=copy.deepcopy(f);changed['sessionAfterSuspension']['makerExecutionDiagnostics'][0][key]=value
                with self.assertRaises(ValueError):frontier(changed,audit,rows,cfg,'candidate')
