"""Correlated joint scenario VaR/ES regressions."""
from pathlib import Path
import sys
import unittest
from decimal import Decimal

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from research.phase5.portfolio_risk import measure

def portfolio():
    return [{'id':'p1','groupId':'settlementA','exposureUsd':'100'},
            {'id':'p2','groupId':'settlementB','exposureUsd':'100'}]

def scenarios():
    return [{'scenarioId':str(i),'observedMs':1800000000000+i*1000,
             'pnlReturnByGroup':{'settlementA':'-1' if i==3 else '0',
                                 'settlementB':'-1' if i==3 else '0'}} for i in range(4)]

class PortfolioRiskTest(unittest.TestCase):
    def test_joint_loss_both_groups_is_not_independent_var(self):
        result=measure(portfolio(),scenarios(),confidence='.8',min_scenarios=3)
        self.assertEqual(Decimal(result['historicalVaRUsd']),Decimal(200))
        self.assertEqual(Decimal(result['historicalExpectedShortfallUsd']),Decimal(200))
        self.assertEqual(Decimal(result['largestCorrelatedGroupExposureUsd']),Decimal(100))
        self.assertEqual(Decimal(result['worstObservedScenarioLossUsd']),Decimal(200))
        self.assertFalse(result['riskQualified'])
        self.assertFalse(result['liveAllowed'])

    def test_incomplete_joint_vector_and_duplicates_are_rejected(self):
        incomplete=scenarios()
        del incomplete[0]['pnlReturnByGroup']['settlementB']
        with self.assertRaisesRegex(ValueError,'Incomplete correlated'):
            measure(portfolio(),incomplete)
        repeated=scenarios()
        repeated[1]['scenarioId']='0'
        with self.assertRaisesRegex(ValueError,'scenario ID'):
            measure(portfolio(),repeated)

    def test_underpowered_synthetic_scenarios_never_claim_risk_acceptance(self):
        report=measure(portfolio(),scenarios(),confidence='.95',min_scenarios=100)
        self.assertFalse(report['sufficientScenarioCount'])
        self.assertFalse(report['independentOracleSettlementsVerified'])
        self.assertEqual(report['decision'],'NO_GO')

    def test_unbounded_payoff_and_bad_timestamp_fail_closed(self):
        out=scenarios()
        out[1]['pnlReturnByGroup']['settlementA']='Infinity'
        with self.assertRaises(ValueError):
            measure(portfolio(),out)
        out=scenarios()
        out[2]['observedMs']=out[0]['observedMs']
        with self.assertRaisesRegex(ValueError,'timestamps'):
            measure(portfolio(),out)

if __name__=='__main__':
    unittest.main()
