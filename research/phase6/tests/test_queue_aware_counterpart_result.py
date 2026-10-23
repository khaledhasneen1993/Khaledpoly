import copy
import unittest
from research.phase6.queue_aware_counterpart_result import load,verify


class CounterpartResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.spec,cls.evidence,cls.summary=load()

    def test_complete_actual_integer_receipt_reproduction_not_fills(self):
        r=verify(self.spec,self.evidence,self.summary)
        self.assertEqual(r['completeOriginalObservations'],30)
        self.assertEqual(r['actualPriceCompatibleSharesRaw'],0)
        self.assertFalse(r['counterpartAfterHorizonAudited']);self.assertFalse(r['netPnlRecomputed'])

    def test_missing_receipt_and_fake_positive_volume_fail(self):
        bad=dict(self.evidence);del bad[self.spec['transactions'][0]['transactionHash']]
        with self.assertRaisesRegex(ValueError,'unknown is not zero'):verify(self.spec,bad,self.summary)
        bad=copy.deepcopy(self.summary);bad['actualPriceCompatibleSharesRaw']=5000000
        with self.assertRaisesRegex(ValueError,'reconstruction'):verify(self.spec,self.evidence,bad)


if __name__=='__main__':unittest.main()
