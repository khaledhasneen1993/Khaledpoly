import copy
from decimal import Decimal as D
import json
import unittest
from research.phase6.dq3_last_cancel import ROOT,load,evidence


class LastCancelEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.context,cls.activation,_=load()

    def test_exact_pre_event_seed_and_post_frame_first_risk_callback(self):
        e=evidence(self.context,self.activation)
        self.assertEqual(json.loads(json.dumps(e,default=str)),json.loads((ROOT/'last-activation-result/evidence.json').read_text()))
        self.assertEqual(e['initialQueueAhead'],'200');self.assertEqual(e['restingQuantity'],'5.00')
        self.assertEqual(e['riskWitness']['quantity'],D('.5'))  # Entry sizing is NOT resting order size.
        self.assertEqual(D(e['netEdgeTotal']),D('.19'))
        self.assertEqual(D(e['requiredEdge']),D('.0400009719998870480'))
        self.assertEqual(e['expectedCancelDueMs'],1792269786346)
        self.assertEqual(e['firstPossibleTargetPrintArrivalMs'],1792269786398)
        self.assertFalse(e['candidateAccountSimulated']);self.assertFalse(e['netPnlRecomputed'])

    def test_unknown_timing_and_fake_queue_or_activation_rejected(self):
        for field,value in [('sameFirstDueInput',False),('activationOutcomeSequence',299650),('tickChangeSinceSubmission',True)]:
            a=copy.deepcopy(self.activation);a['results'][0][field]=value
            with self.assertRaises(ValueError):evidence(self.context,a)
        a=copy.deepcopy(self.activation);a['results'][0]['diagnostic']['initialQueueAhead']=1
        with self.assertRaises(ValueError):evidence(self.context,a)


if __name__=='__main__':unittest.main()
