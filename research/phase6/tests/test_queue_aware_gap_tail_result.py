import copy
import unittest
from pathlib import Path
from research.phase6.queue_aware_gap_tail_result import load,verify
from research.phase6.queue_aware_reduction_context import prepare


class TailResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.spec,cls.evidence,cls.summary=load()

    def test_all14_exact_integer_routes_not_fills(self):
        r=verify(self.spec,self.evidence,self.summary)
        self.assertEqual(r['actualBPriceCompatibleSharesRaw'],0)
        self.assertEqual(r['actualASellPriceCompatibleSharesRaw'],23000000)
        self.assertTrue(r['necessaryVolumeIsNotQueueAllocation']);self.assertFalse(r['netPnlRecomputed'])

    def test_unknown_is_not_zero_and_positive_volume_not_fabricated(self):
        bad=dict(self.evidence);del bad[next(iter(bad))]
        with self.assertRaisesRegex(ValueError,'unknown is not zero'):verify(self.spec,bad,self.summary)
        bad=copy.deepcopy(self.summary);bad['hedgeSellPriceCompatibleSharesRaw']+=1
        with self.assertRaisesRegex(ValueError,'components differ'):verify(self.spec,self.evidence,bad)

    def test_complete162_all_source_groups_no_execution_claim(self):
        _,m,e=prepare();self.assertEqual(len(m['bindings']),162)
        self.assertEqual(m['horizonMs'],1792269760873)
        self.assertFalse(m['activeReductionQueueAndLifecycleEvaluated'])
        self.assertFalse(e['tailVerification']['candidateAccountSimulated'])

    def test_separate_gate_stops_at_new_fill_and_preserves_old_safety_stop(self):
        s=Path('research/phase6/Qw0ActiveReductionProbe.java').read_text()
        self.assertIn('stoppedOnReductionFill=true;stopSeq=seq;stopEvent=ix;break replay;',s)
        self.assertIn('buy?RoundingMode.UP:RoundingMode.DOWN',s)
        self.assertIn('Frozen original maker reduction changed to taker completion',s)
        self.assertIn('Hedge executable before GAP requires additional complete receipt/action evidence',Path('research/phase6/Qw0ThroughGapProbe.java').read_text())


if __name__=='__main__':unittest.main()
