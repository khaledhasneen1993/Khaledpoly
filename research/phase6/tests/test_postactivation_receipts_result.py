import copy
from pathlib import Path
import tempfile
import unittest
from research.phase6.postactivation_receipts_result import ROOT,load,verify


class TwoRealReceiptResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.values=load()

    def test_actual_parts_do_not_match_recorded_quotes(self):
        r=verify(*self.values);self.assertEqual(r['conservedMakerComponents'],2);self.assertFalse(r['marketNetPnlRecomputed'])
        self.assertEqual(r['results'][0]['routeSharesRaw'],{'DIRECT':3846154});self.assertEqual(r['results'][1]['routeSharesRaw'],{'MINT':9000000})

    def test_report_promotion_and_volume_mutation_rejected(self):
        for key,value in [('marketNetPnlRecomputed',True),('modelFillsCreated',1),('nativePoolExtended',True),('liveAllowed',True),('rpcCalls',{})]:
            with self.subTest(key=key):
                spec,raws,report=copy.deepcopy(self.values);report[key]=value
                with self.assertRaises(ValueError):verify(spec,raws,report)
        spec,raws,report=copy.deepcopy(self.values);report['results'][0]['route']['matchingGroups'][0]['sharesRaw']+=1
        with self.assertRaises(ValueError):verify(spec,raws,report)

    def test_corrupt_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.zip';p.write_bytes((ROOT/'ci-artifact.zip').read_bytes()+b'x')
            with self.assertRaises(ValueError):load(p)
