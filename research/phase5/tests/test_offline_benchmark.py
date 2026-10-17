"""Offline Phase 5: data leakage, cost, and provenance regressions."""
from pathlib import Path
from decimal import Decimal
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from research.phase5.offline_benchmark import evaluate

CUT=2000000000000

def trade(identity,market,strategy,at,gross='5',group=None,basis='PAPER_MODEL'):
    return {'tradeId':identity,'marketId':market,
            'groupId':group or market,'strategyId':strategy,
            'openedMs':at,'closedMs':at+100,
            'notionalUsd':'100','grossPnlUsd':gross,
            'feeBpsPerSide':'10','slippageBpsPerSide':'5','provenance':basis}

class StrategyAccountingTest(unittest.TestCase):
    def test_costs_stress_and_no_false_qualification(self):
        rows=[trade('one','marketA','s1',CUT-1000),
              trade('two','marketB','s1',CUT+1000)]
        result=evaluate(rows,CUT,minimum_heldout_groups=1)
        held=result['strategyResults']['s1']['heldout']
        self.assertEqual(held['trades'],1)
        self.assertEqual(held['grossPnlUsd'],'5')
        self.assertEqual(Decimal(held['transactionCostsUsd']),Decimal('0.30'))
        self.assertEqual(Decimal(held['netPnlUsd']),Decimal('4.70'))
        self.assertEqual(Decimal(held['stressedNetPnlUsd']),Decimal('4.60'))
        self.assertFalse(result['strategyQualified'])
        self.assertFalse(result['preregisteredHoldoutVerified'])
        self.assertEqual(result['decision'],'NO_GO')

    def test_group_linkage_purges_cross_cutoff_lookahead(self):
        rows=[trade('one','marketA','s1',CUT-1000,group='shared'),
              trade('two','marketB','s2',CUT+1000,group='shared'),
              trade('three','marketC','s1',CUT+1000)]
        r=evaluate(rows,CUT,minimum_heldout_groups=1)
        self.assertEqual(r['purgedRows'],2)
        self.assertEqual(r['heldoutRows'],1)
        self.assertFalse(r['crossStrategyComparableMarketGroups'])

    def test_mixed_paper_venue_evidence_is_rejected(self):
        rows=[trade('one','A','s1',CUT+1),
              trade('two','B','s1',CUT+2,basis='VENUE_EXECUTION')]
        with self.assertRaisesRegex(ValueError,'pool PAPER'):
            evaluate(rows,CUT)

    def test_duplicates_invalid_clock_and_negative_costs_fail(self):
        sample=trade('same','A','s1',CUT+1)
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            evaluate([sample,sample],CUT)
        malformed=trade('ok','A','s1',CUT+1)
        malformed['closedMs']=CUT-5
        with self.assertRaisesRegex(ValueError,'Noncausal'):
            evaluate([malformed],CUT)
        fee=trade('new','B','s1',CUT+1)
        fee['feeBpsPerSide']='-1'
        with self.assertRaisesRegex(ValueError,'Out-of-domain'):
            evaluate([fee],CUT)

if __name__=='__main__':
    unittest.main()
