import copy
import json
import unittest
import zipfile
from pathlib import Path
from research.phase6.indexed_replay_diagnosis import ROOT,load,verify_frontier
from research.phase6.complete_source_index import reconstruct

class IndexedReplayDiagnosisTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows,_,_=reconstruct();cls.config=json.loads(Path('research/phase2/research-config.json').read_bytes())
        with zipfile.ZipFile(ROOT/'ci-artifact.zip') as z:
            cls.failure=json.loads(z.read('development/candidate/failure.json'))
            cls.audit=[json.loads(line) for line in z.read('development/candidate/failure-audit.jsonl').splitlines()]

    def test_actual_original_frontiers_not_economic_result(self):
        proof=load();self.assertTrue(proof['original628PassedInBothReplays'])
        self.assertEqual(proof['results']['candidate']['arrivalAfterSubmissionMs'],[20,20])
        self.assertEqual(proof['results']['baseline']['arrivalAfterSubmissionMs'],[54,54])
        self.assertFalse(proof['marketNetPnlRecomputed']);self.assertFalse(proof['completeAccountComparisonPerformed'])

    def test_reject_invented_frontier_or_consumption(self):
        for mutate in [lambda p:p['labels']['sourceIndex'].update(consumedOriginalPreimages=88),
                       lambda p:p['labels']['lastAttemptedOriginalObservation'].update(seq=8019),
                       lambda p:p['labels'].update(unknownVenueQuantity=0)]:
            p=copy.deepcopy(self.failure);mutate(p)
            with self.assertRaises(ValueError):verify_frontier(p,self.audit,self.rows,self.config,'candidate')

    def test_active_timing_or_missing_cancellation_cannot_pass(self):
        audit=copy.deepcopy(self.audit)
        for row in audit:
            if row['kind']=='ORDER':row['data']['at']-=300
        with self.assertRaises(ValueError):verify_frontier(self.failure,audit,self.rows,self.config,'candidate')
        audit=[r for r in self.audit if r['kind']!='ORDER_TERMINAL']
        with self.assertRaises(ValueError):verify_frontier(self.failure,audit,self.rows,self.config,'candidate')

    def test_prefix_profit_fill_or_fee_claim_cannot_pass(self):
        for field,value in [('cash',501),('realized',1),('fees',1),('executions',['invented'])]:
            p=copy.deepcopy(self.failure);p['ledgerAfterSuspension'][field]=value
            with self.assertRaises(ValueError):verify_frontier(p,self.audit,self.rows,self.config,'candidate')

if __name__=='__main__':unittest.main()
