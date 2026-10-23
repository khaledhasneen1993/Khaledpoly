import copy
import unittest

from research.phase6.post657_next_receipts_result import load,verify


class Post657NextReceiptsResultTest(unittest.TestCase):
    def test_retained_routes_respect_queue(self):
        result=verify(*load());self.assertEqual(result['conservedMakerComponents'],3);self.assertEqual(result['modelFillsCreated'],0)
        candidate,baseline=result['results'];self.assertEqual((candidate['priceCompatibleVenueSharesRaw'],candidate['minimumQueueAheadSharesRaw'],candidate['queueCleared']),(9_550_000,1_182_300_000,False));self.assertEqual(baseline['priceCompatibleVenueSharesRaw'],0)

    def test_report_promotion_rejected(self):
        spec,raws,report=load();bad=copy.deepcopy(report);bad['marketNetPnlRecomputed']=True
        with self.assertRaises(ValueError):verify(spec,raws,bad)

    def test_raw_mutation_rejected(self):
        spec,raws,report=load();bad=dict(raws);tx=spec['transactions'][0]['transactionHash'];bad[tx]=bad[tx]+b'\n'
        with self.assertRaises(ValueError):verify(spec,bad,report)


if __name__=='__main__':unittest.main()
