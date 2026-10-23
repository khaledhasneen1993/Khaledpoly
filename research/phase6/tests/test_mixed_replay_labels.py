import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from research.phase6.mixed_replay_labels import export
from research.phase6.mixed_replay_labels_proof import portions_sha,verify


class MixedLabelsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=export()
        cls.report=dict(experiment='CONSERVED-MIXED-LAB0',bindings=451,consumedBindings=451,actualComponents=1038,
            originalObservations=451,duplicateAggregateSuppressed=0,labelsSha256=hashlib.sha256((json.dumps(cls.root,indent=2)+'\n').encode()).hexdigest(),
            portionsLogicalSha256=portions_sha(cls.root),adapterOnlyNotAccountReplay=True,
            modelFillsCreated=0,candidateAccountSimulated=False,netPnlRecomputed=False,newPublicReads=0,
            independentPaperQualificationAllowed=False,liveAllowed=False)

    def check(self,report):
        with patch('research.phase6.mixed_replay_labels_proof.export',return_value=self.root):return verify(report)

    def test_all451_both_public_sides_and_all_actual_routes(self):
        self.assertEqual(len(self.root['bindings']),451)
        self.assertEqual({b['side'] for b in self.root['bindings']},{'BUY','SELL'})
        self.assertEqual(self.root['routeComponentCounts'],dict(DIRECT=208,MINT=821,MERGE=9))
        self.assertEqual(sum(self.root['routeComponentCounts'].values()),1038)
        self.assertEqual(self.check(self.report)['actualComponents'],1038)

    def test_price_side_quantity_identity_hash_or_subset_cannot_pass(self):
        for key,value in [('portionsLogicalSha256','0'*64),('labelsSha256','0'*64),('actualComponents',1037),('consumedBindings',450)]:
            bad=dict(self.report);bad[key]=value
            with self.assertRaisesRegex(ValueError,'parity/scope'):self.check(bad)
        bad=copy.deepcopy(self.root);bad['bindings'][0]['matches'][0]['maker']['takingRaw']+=1
        self.assertNotEqual(portions_sha(bad),self.report['portionsLogicalSha256'])

    def test_no_scope_escalation_or_simulated_market_fills(self):
        for key in ['candidateAccountSimulated','netPnlRecomputed','independentPaperQualificationAllowed','liveAllowed']:
            bad=dict(self.report);bad[key]=True
            with self.assertRaisesRegex(ValueError,'parity/scope'):self.check(bad)
        bad=dict(self.report);bad['modelFillsCreated']=1
        with self.assertRaisesRegex(ValueError,'parity/scope'):self.check(bad)

    def test_legacy_frozen_adapter_still_unchanged(self):
        path='polybot-core/src/main/java/com/polybot/hft/paper/SettlementReplayLabels.java'
        self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(),'1715071b6caa5171fd482a612f07cde9eb385479d13203ee09f9e9f245adf052')
        known=Path('research/experiments/settlement-lab0-20261018/replay-labels.json')
        self.assertEqual(json.loads(known.read_text())['experiment'],'CS-MINT-LAB0')
        source=Path(path).read_text()
        self.assertIn('root.path("bindings").size()>100',source)
        self.assertIn('!n.path("side").asText().equals("BUY")',source)
        self.assertIn('RoundingMode.HALF_EVEN',source)
        self.assertNotIn('CONSERVED-MIXED-LAB0',source)


if __name__=='__main__':unittest.main()
