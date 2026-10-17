"""Scenario bounds are not venue evidence."""
from pathlib import Path
import sys
import unittest
import copy
from decimal import Decimal as D
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'research/phase3/tests'))
from test_research import fixture,BASE
from research.phase5.portfolio_admission import plan
from research.phase5.book_impact import scenario
from research.phase3.polybot_sdk.advanced import candidates
from research.phase3.polybot_sdk.features import FeatureStore
from research.phase3.polybot_sdk.model import validate

class QualityUpgradeTest(unittest.TestCase):
    def universe(self):
        s=fixture();s['markets'].append(dict(s['markets'][0],condition='second',first='c',second='d'))
        s['books']['c']=copy.deepcopy(s['books']['a']);s['books']['d']=copy.deepcopy(s['books']['b'])
        rows=candidates(validate(s,BASE),FeatureStore(),'complete-set')
        scenarios={'up':{t:'.1' for t in 'abcd'},'down':{t:'-1' for t in 'abcd'}}
        return s,rows,scenarios,{'market':'one','second':'two'}
    def test_joint_selection_is_one_atomic_proposal(self):
        s,rows,cases,groups=self.universe()
        out=plan(s,rows,cases,groups,at_ms=BASE)
        self.assertEqual(len(out['selection']['selectedCandidateIds']),2)
        self.assertEqual(len(out['envelope']['proposals']),1)
        self.assertEqual(len(out['envelope']['proposals'][0]['legs']),4)
        self.assertFalse(out['liveAllowed'])
    def test_correlated_loss_and_existing_exposure_reduce_selection(self):
        s,rows,cases,groups=self.universe()
        self.assertEqual(plan(s,rows,cases,groups,at_ms=BASE,risk_cap='5')['envelope']['proposals'][0]['legs'].__len__(),2)
        s['account']['holdings']['a']={'shares':'10','basis':'4'}
        out=plan(s,rows,cases,groups,at_ms=BASE,risk_cap='5')
        self.assertEqual(out['selection']['selectedCandidateIds'],[])
        del cases['up']['a']
        with self.assertRaises(ValueError): plan(s,rows,cases,groups,at_ms=BASE)
    def test_depth_impact_is_weighted_and_never_mutates_or_fills(self):
        s=fixture();s['books']['a']['asks']=[{'price':'.6','size':'5'},{'price':'.7','size':'10'}]
        before=copy.deepcopy(s)
        r=scenario(s,'a',True,'10',at_ms=BASE)
        self.assertEqual(D(r['assumedVwap']),D('.65'))
        self.assertEqual(D(r['assumedSlippagePerShare']),D('.05'))
        self.assertEqual(r['fillsCreated'],0);self.assertEqual(s,before)
        self.assertFalse(scenario(s,'a',True,'20',at_ms=BASE)['complete'])
        s['books']['a']['depthTruncated']=True
        with self.assertRaises(ValueError): scenario(s,'a',True,'10',at_ms=BASE)
