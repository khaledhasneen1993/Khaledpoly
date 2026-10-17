"""Embargo and linked-group holdout isolation."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from research.phase5.walk_forward import evaluate_folds
START=1800000000000
FOLDS=[{'trainBeforeMs':START+1000,'testStartMs':START+3000,'testEndMs':START+10000}]

def trade(id,market,group,start,strategy='one'):
    return {'tradeId':id,'marketId':market,'groupId':group,'strategyId':strategy,
        'openedMs':start,'closedMs':start+100,'notionalUsd':'50',
        'grossPnlUsd':'1','feeBpsPerSide':'10','slippageBpsPerSide':'5',
        'provenance':'PAPER_MODEL'}

class WalkForwardTest(unittest.TestCase):
    def test_cross_linked_group_is_purged_even_across_strategies(self):
        rows=[trade('a','A','linked',START+100),
              trade('b','B','linked',START+4000,strategy='two'),
              trade('c','C','independent',START+4000)]
        r=evaluate_folds(rows,FOLDS,min_test_groups=1)
        data=r['folds'][0]
        self.assertEqual(data['purgedOrOutOfWindowRows'],2)
        self.assertEqual(data['testRows'],1)
        self.assertEqual(data['trainRows'],0)
        self.assertFalse(r['strategyQualified'])
        self.assertFalse(data['strategiesShareSameTestMarketGroups'])

    def test_embargo_rows_are_purged_not_train(self):
        rows=[trade('a','A','train',START+100),
              trade('b','B','embargo',START+2000),
              trade('c','C','test',START+4000)]
        r=evaluate_folds(rows,FOLDS,min_test_groups=1)
        data=r['folds'][0]
        self.assertEqual(data['trainRows'],1)
        self.assertEqual(data['testRows'],1)
        self.assertEqual(data['purgedOrOutOfWindowRows'],1)
        self.assertEqual(data['embargoMs'],2000)

    def test_nonincreasing_windows_and_negative_embargo_fail(self):
        rows=[trade('a','A','G',START+100)]
        with self.assertRaisesRegex(ValueError,'No positive embargo'):
            evaluate_folds(rows,[{'trainBeforeMs':START+3000,
                    'testStartMs':START+2000,'testEndMs':START+4000}])
        with self.assertRaisesRegex(ValueError,'must not overlap'):
            evaluate_folds(rows,FOLDS+[{'trainBeforeMs':START+2000,
                    'testStartMs':START+9000,'testEndMs':START+14000}])

    def test_insufficient_group_count_never_qualifies(self):
        r=evaluate_folds([trade('a','A','G',START+4000)],FOLDS,min_test_groups=30)
        self.assertFalse(r['folds'][0]['strategies']['one']['sufficientHeldoutGroups'])
        self.assertFalse(r['prospectiveHoldoutObserved'])
        self.assertEqual(r['decision'],'NO_GO')

if __name__=='__main__':
    unittest.main()
