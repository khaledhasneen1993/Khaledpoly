import copy
import gzip
import io
import json
from pathlib import Path
import unittest
import zipfile
from research.phase6.expanded_receipt_pool import build,next_missing,ROOT,PARENT,verify_native,verify_stop
from research.phase6.full_runner_diagnosis import first_missing

class ExpandedReceiptPoolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pool=build();cls.summary=json.loads((ROOT/'summary.json').read_text())
        cls.native=json.loads((ROOT/'native-proof.json').read_text())

    def test_all642_parent_bindings_preserved_and_one_exact_group_added(self):
        parent=json.loads(gzip.decompress(PARENT.read_bytes()))
        old=[b for b in self.pool['bindings'] if b['origin']!='PROVEN_ORIGINAL_FIRST_BLOCKER97']
        self.assertEqual(old,parent['bindings']);self.assertEqual(len(self.pool['bindings']),643)
        self.assertEqual(self.pool['expectedComponentCount'],1532)
        self.assertEqual(self.pool['routeComponentCounts'],{'DIRECT':354,'MINT':1161,'MERGE':17})
        saved=json.loads(gzip.decompress((ROOT/'pool.json.gz').read_bytes()));self.assertEqual(self.pool,saved)

    def test_next_unknown_is_original628_not_dropped_or_replaced(self):
        row=next_missing(self.pool);self.assertEqual(row['seq'],628);self.assertEqual(row['eventIndex'],0)
        self.assertEqual(row,self.summary['nextMissing']);self.assertFalse(self.pool['fullAccountReplayAuthorized'])

    def test_all_native643_identities_and1532_tuples_match(self):
        proof=verify_native(self.native,self.summary);self.assertEqual(proof['componentTuples'],1532)
        self.assertFalse(proof['marketNetPnlRecomputed'])
        bad=copy.deepcopy(self.native);bad['sourceIdentitiesSha256']='0'*64
        with self.assertRaisesRegex(ValueError,'parity'):verify_native(bad,self.summary)
        bad=copy.deepcopy(self.native);bad['pool']['consumedBindings']=642
        with self.assertRaisesRegex(ValueError,'consumption'):verify_native(bad,self.summary)

    def stop_fixture(self):
        # Synthetic verifier fixture; actual original628 account diagnostic is still pending CI.
        with zipfile.ZipFile('research/experiments/full-native-runner-20261020/original-diagnosis.zip') as z:
            p=json.loads(z.read('original-diagnosis/candidate/failure.json'))
        p['labels'].update(bindings=643,actualComponents=1532,consumedBindings=1)
        p['sessionAfterSuspension']['settlementExperiment']=p['labels']
        p['sessionAfterSuspension']['settlementVolumeConservation']=dict(uniqueMakerComponents=16,venueQuantity=200,queueAbsorbed=0,allocatedQuantity=0,unusedQuantity=200)
        cfg=json.loads(Path('research/phase2/research-config.json').read_text())
        return p,first_missing(),cfg

    def test_next_stop_checks_counts_identity_original_config_and_conservation(self):
        p,e,c=self.stop_fixture();self.assertEqual(verify_stop(p,e,True,c)['consumedBindings'],1)
        p['sessionAfterSuspension']['settlementVolumeConservation']['unusedQuantity']=199
        with self.assertRaisesRegex(ValueError,'volume'):verify_stop(p,e,True,c)
        p,e,c=self.stop_fixture();p['labels']['consumedBindings']=0
        with self.assertRaisesRegex(ValueError,'identity/count'):verify_stop(p,e,True,c)

    def test_no_scope_or_synthetic_account_promotion(self):
        bad=copy.deepcopy(self.native);bad['pool']['aggregateFallbackAllowed']=True
        with self.assertRaisesRegex(ValueError,'scope'):verify_native(bad,self.summary)
        bad=copy.deepcopy(self.native);bad['separateSyntheticUnknownGuard']['session']['cash']=500
        with self.assertRaisesRegex(ValueError,'synthetic'):verify_native(bad,self.summary)
        p,e,c=self.stop_fixture();p['marketNetPnlRecomputed']=True
        with self.assertRaisesRegex(ValueError,'PnL'):verify_stop(p,e,True,c)

if __name__=='__main__':unittest.main()
