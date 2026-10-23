import copy
from pathlib import Path
import unittest
from unittest.mock import patch
from research.phase6.queue_aware_recovery_result import load,verify
from research.phase6.queue_aware_recovery_exit import prepare


class RecoveryResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.spec,cls.evidence,cls.summary=load()

    def test_all451_and_1038_actual_integer_components(self):
        r=verify(self.spec,self.evidence,self.summary)
        self.assertEqual(r['uniqueActualMakerComponents'],1038);self.assertFalse(r['candidateAccountSimulated'])

    def test_missing_receipt_and_fabricated_component_fail(self):
        bad=dict(self.evidence);del bad[next(iter(bad))]
        with self.assertRaisesRegex(ValueError,'unknown is not zero'):verify(self.spec,bad,self.summary)
        bad=copy.deepcopy(self.summary);bad['results'][0]['parts'][0]['sharesRaw']+=1
        with self.assertRaisesRegex(ValueError,'components/scope differ'):verify(self.spec,self.evidence,bad)

    def test_preparation_preserves_original_seed_and_first_exit_stop(self):
        with patch('research.phase6.queue_aware_recovery_exit.load',return_value=(self.spec,self.evidence,self.summary)):
            r=prepare()
        self.assertEqual(r['nextDecisionMs'],1792269761068);self.assertEqual(len(r['bindings']),451)
        self.assertEqual(r['initialQuantity'],'5');self.assertTrue(r['stopImmediatelyOnFirstNewAllocation'])
        s=Path('research/phase6/Qw0RecoveryExitProbe.java').read_text()
        self.assertIn('stopEvent=ix;stopped=true;break replay;',s)
        self.assertIn('FIRST_NEW_ATOMIC_TAKER_FOK_STOP_BEFORE_MERGE_OR_STRATEGY',s)
        self.assertIn('Insufficient conditional cash; no funding fabrication',s)


if __name__=='__main__':unittest.main()
