import copy
from decimal import Decimal as D
import json
from pathlib import Path
import tempfile
import unittest
from research.phase6.strategy_profile_build import materialize
from research.phase6.frozen_policy_result import ROOT,verify


class FrozenStrategyProfileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.args=[json.loads((ROOT/n).read_text(),parse_float=D) for n in ['rule-parity.json','strategy-proof.json','default-after.json']]

    def test_all_reference_rules_and_canonical_synthetic_flow(self):
        r=verify(*self.args);self.assertEqual(r['developmentWitnessProposals'],34);self.assertFalse(r['marketNetPnlRecomputed'])

    def test_no_quote_objective_or_choice_drift(self):
        a=copy.deepcopy(self.args);n=next(x for x in a[0]['quotes'] if x is not None);n['firstBid']=D('.01')
        with self.assertRaisesRegex(ValueError,'Frozen quote'):verify(*a)
        a=copy.deepcopy(self.args);a[0]['exits'][0]['action']='WAIT'
        with self.assertRaisesRegex(ValueError,'exit choice'):verify(*a)

    def test_no_lower_queue_fee_risk_or_execution_guard(self):
        for key,value in [('queueMultiplier','1'),('feeMultiplier','0'),('maxExitLoss','100')]:
            a=copy.deepcopy(self.args);a[1]['positive']['session']['configuration'][key]=value
            with self.assertRaisesRegex(ValueError,'configuration changed'):verify(*a)
        a=copy.deepcopy(self.args);a[1]['netEdgeRejected']['session']['decisionReasons']['TAKER_NET_EDGE']=0
        with self.assertRaisesRegex(ValueError,'execution-net'):verify(*a)

    def test_no_default_change_or_scope_escalation(self):
        a=copy.deepcopy(self.args);a[2]['cash']=500
        with self.assertRaisesRegex(ValueError,'Default-off'):verify(*a)
        for key in ['marketNetPnlRecomputed','fullAccountMarketComparisonPerformed','independentPaperQualificationAllowed','liveAllowed']:
            a=copy.deepcopy(self.args);a[1][key]=True
            with self.assertRaisesRegex(ValueError,'Synthetic-only'):verify(*a)

    def test_isolated_policy_build_changes_no_default_core(self):
        path=Path('polybot-core/src/main/java/com/polybot/hft/paper/ResearchSession.java');before=path.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'variant';r=materialize(root)
            self.assertEqual(r['defaultCoreFilesModified'],0)
            source=(root/path).read_text();self.assertIn('FrozenResearchPolicies.propose',source);self.assertIn('POSITIVE_EDGE_EXIT',source)
        self.assertEqual(path.read_bytes(),before)


if __name__=='__main__':unittest.main()
