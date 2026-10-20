import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from research.phase6.expanded_receipt_pool import build as parent_build
from research.phase6.postactivation_receipt_pool import build,identities,verify_native,ROOT,ORIGIN
from research.phase6.postactivation_pool_build import materialize,LABELS
from research.phase6.postactivation_pool_replay import EXPECTED_BINDINGS,EXPECTED_COMPONENTS,require_native


class PostActivationReceiptPoolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pool=build();cls.parent=parent_build()

    def test_all643_parent_bindings_are_exact_and_only_two_are_added(self):
        self.assertEqual([b for b in self.pool['bindings'] if b.get('origin')!=ORIGIN],self.parent['bindings'])
        added=[b for b in self.pool['bindings'] if b.get('origin')==ORIGIN]
        self.assertEqual([(b['seq'],b['eventIndex']) for b in added],[(9035,0),(82964,0)])
        self.assertEqual([len(b['matches']) for b in added],[1,1])
        self.assertEqual([b['matches'][0]['matchType'] for b in added],['DIRECT','MINT'])
        self.assertEqual(self.pool['routeComponentCounts'],{'DIRECT':355,'MINT':1162,'MERGE':17})
        self.assertEqual((len(self.pool['bindings']),self.pool['expectedComponentCount']),(645,1534))

    def test_exact_source_preimages_cover_all645_in_pool_order(self):
        source=identities(self.pool);self.assertEqual(source['scope'],'EXACT645_ORIGINAL_IDENTITY_INPUTS_NOT_EXECUTION_TAPE')
        self.assertEqual([(r['seq'],r['eventIndex']) for r in source['observations']],[(b['seq'],b['eventIndex']) for b in self.pool['bindings']])
        target={r['seq']:r for r in source['observations'] if r['seq'] in (9035,82964)}
        self.assertEqual(target[9035]['data']['tradeId'][:11],'{"market":"')
        self.assertEqual(target[82964]['data']['sourceMs'],1792269639603)

    def test_native_proof_rejects_incomplete_or_promoted_scope(self):
        if not (ROOT/'native-proof.json').exists():self.skipTest('retained CI proof not committed yet')
        summary=json.loads((ROOT/'summary.json').read_text());proof=json.loads((ROOT/'native-proof.json').read_text())
        self.assertEqual(verify_native(proof,summary)['componentTuples'],1534)
        bad=copy.deepcopy(proof);bad['pool']['consumedBindings']=644
        with self.assertRaisesRegex(ValueError,'consumption'):verify_native(bad,summary)
        bad=copy.deepcopy(proof);bad['marketNetPnlRecomputed']=True
        with self.assertRaisesRegex(ValueError,'performance'):verify_native(bad,summary)

    def test_generated_helper_pins_new_pool_and_preserves_source_lag_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'generated';r=materialize(out);text=(out/LABELS).read_text()
            self.assertIn(r['poolLogicalSha256'],text);self.assertNotIn('real643 pool required',text)
            self.assertIn('SOURCE_LAG0',text);self.assertEqual(r['expectedReceiptBindings'],645)

    def test_new_replay_orchestrator_requires_retained_native645_and_never_643(self):
        self.assertEqual((EXPECTED_BINDINGS,EXPECTED_COMPONENTS),(645,1534))
        if (ROOT/'native-proof.json').exists():self.assertEqual(require_native()['originalIdentities'],645)
        else:
            with self.assertRaises(FileNotFoundError):require_native()


if __name__=='__main__':unittest.main()
