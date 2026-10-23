import copy
import unittest

from research.phase6.post661_next_receipts_result import load,verify


class Post661NextReceiptsResultTest(unittest.TestCase):
    def test_retained_routes_keep_necessary_conditions_distinct_from_fills(self):
        result=verify(*load());self.assertEqual(result['conservedMakerComponents'],10);self.assertEqual(result['modelFillsCreated'],0)
        candidate,baseline=result['results'];self.assertEqual((candidate['priceCompatibleVenueSharesRaw'],candidate['minimumQueueAheadSharesRaw'],candidate['necessaryQueueClearanceThresholdExceeded']),(0,None,False));self.assertEqual((baseline['priceCompatibleVenueSharesRaw'],baseline['minimumQueueAheadSharesRaw'],baseline['necessaryQueueClearanceThresholdExceeded']),(35_882_353,0,True));self.assertFalse(baseline['counterfactualQueueAllocationProven'])

    def test_report_promotion_rejected(self):
        spec,raws,report=load();bad=copy.deepcopy(report);bad['marketNetPnlRecomputed']=True
        with self.assertRaises(ValueError):verify(spec,raws,bad)

    def test_raw_mutation_rejected(self):
        spec,raws,report=load();bad=dict(raws);tx=spec['transactions'][0]['transactionHash'];bad[tx]=bad[tx]+b'\n'
        with self.assertRaises(ValueError):verify(spec,bad,report)


if __name__=='__main__':unittest.main()
