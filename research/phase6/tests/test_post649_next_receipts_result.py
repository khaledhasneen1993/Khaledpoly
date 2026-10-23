import copy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from research.phase6.post649_next_receipts_result import load,verify


class Post649NextReceiptsResultTest(unittest.TestCase):
    def test_retained_routes_are_not_bot_fills(self):
        result=verify(*load());self.assertEqual(result['conservedMakerComponents'],10);self.assertEqual(result['modelFillsCreated'],0)
        self.assertTrue(all(x['noRecordedOrderPassesNecessaryMatchingConditions'] for x in result['results']))

    def test_report_promotion_rejected(self):
        spec,raws,report=load();bad=copy.deepcopy(report);bad['marketNetPnlRecomputed']=True
        with self.assertRaises(ValueError):verify(spec,raws,bad)

    def test_raw_mutation_rejected(self):
        spec,raws,report=load();bad=dict(raws);tx=spec['transactions'][0]['transactionHash'];bad[tx]=bad[tx]+b'\n'
        with self.assertRaises(ValueError):verify(spec,bad,report)


if __name__=='__main__':unittest.main()
