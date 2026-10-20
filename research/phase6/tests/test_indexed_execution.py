import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from research.phase6.indexed_execution_result import ROOT,verify
from research.phase6.indexed_execution_build import FREEZE,materialize,render_session,render_runner

class IndexedExecutionTest(unittest.TestCase):
    def proof(self):return json.loads((ROOT/'indexed-execution-proof.json').read_bytes())

    def test_integrated_prefix_is_not_original_market_replay(self):
        result=verify(self.proof());self.assertEqual(result['integrationChecks'],9)
        self.assertFalse(result['fullOriginalTapeReplayed'])

    def test_no_profit_original_replay_or_unknown_volume_promotion(self):
        for field,value in [('fullOriginalTapeReplayed',True),('marketNetPnlRecomputed',True),
            ('completeAccountComparisonPerformed',True),('independentPaperQualificationAllowed',True),
            ('liveAllowed',True),('unknownVenueQuantity',0)]:
            p=self.proof();p[field]=value
            with self.assertRaises(ValueError):verify(p)
        p=self.proof();p['expired']['knownExpiredComponentQuantityNotApplied']=0
        with self.assertRaises(ValueError):verify(p)
        p=self.proof();p['ordinary']['sourceIndex']['completeOriginalConsumption']=True
        with self.assertRaises(ValueError):verify(p)

    def test_frozen_generated_sources_default_core_and_frame_code_unchanged(self):
        before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('polybot-core/src/main/java').rglob('*.java')}
        spec=json.loads(FREEZE.read_bytes())
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'source';r=materialize(out);self.assertTrue(r['identityAndAtomicWitnessIntegrated'])
            for path,expected in spec['generatedSourcesSha256'].items():
                target=out/path if path.endswith('ResearchSession.java') else (out/path).with_name('IndexedOriginalTapeReplay.java')
                self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),expected)
        self.assertEqual(before,{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('polybot-core/src/main/java').rglob('*.java')})

    def test_changed_source_or_incomplete_guard_evidence_rejected(self):
        for render in (render_session,render_runner):
            with self.assertRaises(ValueError):render('changed')
        p=self.proof();p['checks'].pop()
        with self.assertRaises(ValueError):verify(p)
        p=self.proof();p['prefixSha256']='0'*64
        with self.assertRaises(ValueError):verify(p)

if __name__=='__main__':unittest.main()
