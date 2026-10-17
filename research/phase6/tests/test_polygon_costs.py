"""Polygon settlement batching remains a measured-parameter hypothesis."""
from pathlib import Path
import sys
import unittest
from decimal import Decimal as D

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from research.phase6.polygon_costs import compare_batching


class PolygonBatchTest(unittest.TestCase):
    def test_batching_reduces_fixed_gas_but_does_not_broadcast(self):
        result=compare_batching(4,100000,25000,1000000000,'1',
                                {1:0,2:1000,4:2000},'0')
        cost={x['maxBatchSize']:D(x['scenarioTotalUsd']) for x in result['scenarios']}
        self.assertGreater(cost[1],cost[2])
        self.assertGreater(cost[2],cost[4])
        self.assertEqual(result['lowestAssumedCostBatchSize'],4)
        self.assertFalse(result['broadcast'])
        self.assertFalse(result['executionEnabled'])

    def test_high_delay_cost_can_reverse_batch_preference(self):
        r=compare_batching(4,100000,25000,1000000000,'1',
                           {1:0,4:2000},'.01')
        self.assertEqual(r['lowestAssumedCostBatchSize'],1)
        self.assertFalse(r['actualSettlementFinalityMeasured'])

    def test_invalid_redeem_bundle_is_not_accepted(self):
        with self.assertRaises(ValueError):
            compare_batching(4,100,20,100,'1',{65:100},'0')
        with self.assertRaises(ValueError):
            compare_batching(4,100,20,100,'1',{2:-1},'0')
        with self.assertRaises(ValueError):
            compare_batching(4,100,20,-1,'1',{1:0},'0')

if __name__=='__main__':
    unittest.main()
