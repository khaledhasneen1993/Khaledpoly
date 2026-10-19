import copy
import json
import unittest
from research.phase6.dq3_activation_result import ROOT,load,verify


class ActivationResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.context,cls.result=load()

    def test_exact_source_pre_event_book_and_actual_engine_outcomes(self):
        r=verify(self.context,self.result)
        self.assertEqual(r,json.loads((ROOT/'activation-result/verification.json').read_text()))
        self.assertEqual([x['preEventBook']['originalSequence'] for x in r['results']],[244225,245661,246893])
        self.assertEqual([x['initialQueueAhead'] for x in r['results']],['1292.48','1292.48',None])
        self.assertEqual([x.get('minimumQueueNotCleared') for x in r['results']],['331.759078','331.759078',None])
        self.assertFalse(r['netPnlRecomputed']);self.assertEqual(r['fillsCreated'],0)

    def test_decision_snapshot_incoming_book_and_unknown_timing_cannot_replace_seed(self):
        for field,value in [('initialQueueAhead',1680),('initialQueueAhead',2),('eligiblePrintVolume',1),('price',.48)]:
            changed=copy.deepcopy(self.result);changed['results'][0]['diagnostic'][field]=value
            with self.assertRaises(ValueError):verify(self.context,changed)
        for field,value in [('sameFirstDueInput',False),('tickChangeSinceSubmission',True),('activationOutcomeSequence',244225)]:
            changed=copy.deepcopy(self.result);changed['results'][0][field]=value
            with self.assertRaises(ValueError):verify(self.context,changed)


if __name__=='__main__':unittest.main()
