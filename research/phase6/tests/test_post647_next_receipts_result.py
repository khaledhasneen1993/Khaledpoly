import copy
from pathlib import Path
import tempfile
import unittest

from research.phase6.post647_next_receipts_result import ROOT,load,verify


class Post647NextReceiptsResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.values=load()

    def test_actual_parts_do_not_match_recorded_quotes(self):
        result=verify(*self.values);self.assertEqual(result['conservedMakerComponents'],4);self.assertFalse(result['marketNetPnlRecomputed'])
        self.assertEqual([x['routeSharesRaw'] for x in result['results']],[{'DIRECT':38461539},{'MINT':28760000}])
        self.assertTrue(all(x['noRecordedOrderPassesNecessaryMatchingConditions'] for x in result['results']))

    def test_report_promotion_and_volume_mutation_rejected(self):
        for key,value in [('marketNetPnlRecomputed',True),('modelFillsCreated',1),('nativePoolExtended',True),('liveAllowed',True),('rpcCalls',{})]:
            spec,raws,report=copy.deepcopy(self.values);report[key]=value
            with self.assertRaises(ValueError):verify(spec,raws,report)
        spec,raws,report=copy.deepcopy(self.values);report['results'][0]['route']['matchingGroups'][0]['sharesRaw']+=1
        with self.assertRaises(ValueError):verify(spec,raws,report)

    def test_corrupt_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.zip';path.write_bytes((ROOT/'ci-artifact.zip').read_bytes()+b'x')
            with self.assertRaises(ValueError):load(path)


if __name__=='__main__':unittest.main()
