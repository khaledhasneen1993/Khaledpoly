import copy
from decimal import Decimal as D
import hashlib
import json
import unittest
from research.phase6.native_pool_result import ROOT,verify
from research.phase6.native_pool_inputs import prepare


class NativePoolResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.args=[json.loads((ROOT/n).read_text(),parse_float=D) for n in ('native-pool-proof.json','default-after.json','build-provenance.json')]

    def test_all_native_source_tuples_and_synthetic_fail_closed_bridge(self):
        p=verify(*self.args);self.assertEqual(p['originalIdentities'],642);self.assertEqual(p['conservedComponentTuples'],1516)
        self.assertFalse(p['marketNetPnlRecomputed']);self.assertTrue(p['completeDefaultOffParity'])

    def test_exact_raw_identity_preimages_all642_not_tx_only_substitutes(self):
        raw,source=prepare();self.assertEqual(hashlib.sha256(raw).hexdigest(),self.args[0]['poolLogicalSha256'])
        encoded=(json.dumps(source,separators=(',',':'))+'\n').encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest(),self.args[0]['sourceIdentitiesSha256'])
        self.assertEqual(len(source['observations']),642)

    def test_no_partial_consumption_digest_drift_or_scope_promotion(self):
        for key,value in [('originalObservations',641),('sourceIdentitiesSha256','0'*64),('portionsLogicalSha256','0'*64),
                          ('marketNetPnlRecomputed',True),('fullAccountMarketComparisonPerformed',True),('modelMarketFillsCreated',1)]:
            args=copy.deepcopy(self.args);args[0][key]=value
            with self.assertRaises(ValueError):verify(*args)
        args=copy.deepcopy(self.args);args[0]['poolReader']['consumedBindings']=641
        with self.assertRaisesRegex(ValueError,'consumption'):verify(*args)
        args=copy.deepcopy(self.args);args[0]['poolReader']['aggregateFallbackAllowed']=True
        with self.assertRaisesRegex(ValueError,'scope'):verify(*args)

    def test_no_queue_fee_risk_or_unknown_halt_relaxation(self):
        for key,value in [('queueMultiplier',1),('feeMultiplier',0),('maxExitLoss',100)]:
            args=copy.deepcopy(self.args);args[0]['syntheticSession']['session']['configuration'][key]=value
            with self.assertRaisesRegex(ValueError,'risk/fee/queue'):verify(*args)
        args=copy.deepcopy(self.args);args[0]['syntheticSession']['session']['halted']=False
        with self.assertRaisesRegex(ValueError,'halt/cancel'):verify(*args)
        args=copy.deepcopy(self.args);args[0]['syntheticSession']['session']['settlementVolumeConservation']['queueAbsorbed']=0
        with self.assertRaisesRegex(ValueError,'queue/volume'):verify(*args)

    def test_default_core_and_source_profile_cannot_change(self):
        args=copy.deepcopy(self.args);args[1]['cash']=500
        with self.assertRaisesRegex(ValueError,'default-off'):verify(*args)
        args=copy.deepcopy(self.args);args[2]['defaultCoreFilesModified']=1
        with self.assertRaisesRegex(ValueError,'source build'):verify(*args)


if __name__=='__main__':unittest.main()
