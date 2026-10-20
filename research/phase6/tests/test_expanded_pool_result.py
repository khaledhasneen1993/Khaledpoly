from pathlib import Path
import tempfile
import unittest
from research.phase6.expanded_pool_result import ROOT,verify

class ExpandedPoolResultTest(unittest.TestCase):
    def test_actual_native643_and_original628_stop_revalidate(self):
        p=verify();self.assertEqual(p['nativeIdentities'],643);self.assertEqual(p['nativeComponentTuples'],1532)
        self.assertEqual(p['nextOriginalCoordinate'],[628,0]);self.assertTrue(p['original97ConsumedOnce'])
        self.assertTrue(p['original16ComponentsConserved']);self.assertFalse(p['marketNetPnlRecomputed'])

    def test_original_prefix_has_no_orders_but_does_not_authorize_optimization(self):
        p=verify();self.assertEqual(p['prefixAccountCounts'],{k:dict(orderHistory=0,holdings=0,executions=0) for k in ('baseline','candidate')})
        self.assertFalse(p['generalNoOrderOptimizationProven']);self.assertFalse(p['completeAccountComparisonPerformed'])

    def test_changed_or_incomplete_archive_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'bad.zip';p.write_bytes((ROOT/'ci-artifact.zip').read_bytes()[:-1])
            with self.assertRaisesRegex(ValueError,'artifact'):verify(p)

if __name__=='__main__':unittest.main()
