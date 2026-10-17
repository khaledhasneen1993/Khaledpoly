"""Exact candidate subset search respects correlated event/scenario limits."""
from decimal import Decimal
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from research.phase5.portfolio_optimizer import optimize


def candidate(identity,group,expected,payoffs,cost='5'):
    return {'id':identity,'groupId':group,'acquisitionCostUsd':cost,
            'expectedNetPnlUsd':expected,'pnlByScenarioUsd':payoffs,
            'provenance':'PAPER_SCENARIO'}


class ExactPortfolioResearchTest(unittest.TestCase):
    def test_optimizer_avoids_greedy_and_correlated_joint_loss(self):
        rows=[
            candidate('big','groupA','5',{'up':'8','down':'-5'},cost='10'),
            candidate('a','groupA','3',{'up':'3','down':'-2'},cost='5'),
            candidate('b','groupB','3',{'up':'3','down':'-2'},cost='5'),
        ]
        out=optimize(rows,buying_power_usd='10',group_cap_usd='10',
                     maximum_joint_loss_usd='4',max_positions=2)
        self.assertEqual(out['selectedCandidateIds'],['a','b'])
        self.assertEqual(Decimal(out['assumedExpectedNetPnlUsd']),Decimal(6))
        self.assertEqual(Decimal(out['worstAssumedJointLossUsd']),Decimal(4))
        self.assertTrue(out['optimizationExactForInputScenarios'])
        self.assertFalse(out['strategyQualified'])
        self.assertFalse(out['liveAllowed'])

    def test_shared_group_budget_blocks_two_candidates(self):
        rows=[candidate('a','one','3',{'x':'2','y':'-1'}),
              candidate('b','one','4',{'x':'2','y':'-1'})]
        r=optimize(rows,buying_power_usd='50',group_cap_usd='5',
                   maximum_joint_loss_usd='5')
        self.assertEqual(r['selectedCandidateIds'],['b'])

    def test_missing_scenario_alignment_fails_closed(self):
        rows=[candidate('a','one','3',{'x':'2','y':'-1'}),
              candidate('b','two','4',{'x':'2','z':'-1'})]
        with self.assertRaisesRegex(ValueError,'Unaligned'):
            optimize(rows,buying_power_usd='20',group_cap_usd='10',
                     maximum_joint_loss_usd='10')

    def test_no_forecast_edge_is_still_qualified(self):
        r=optimize([candidate('bad','one','-1',{'x':'2','y':'-5'})],
                   buying_power_usd='10',group_cap_usd='10',
                   maximum_joint_loss_usd='1')
        self.assertEqual(r['selectedCandidateIds'],[])
        self.assertEqual(Decimal(r['assumedExpectedNetPnlUsd']),Decimal(0))
        self.assertEqual(r['decision'],'NO_GO')

    def test_existing_group_exposure_is_not_available_twice(self):
        rows=[candidate('a','one','3',{'x':'2','y':'-1'})]
        r=optimize(rows,buying_power_usd='10',group_cap_usd='10',
                   maximum_joint_loss_usd='5',
                   existing_group_exposure={'one':'8'})
        self.assertEqual(r['selectedCandidateIds'],[])

if __name__=='__main__':
    unittest.main()
