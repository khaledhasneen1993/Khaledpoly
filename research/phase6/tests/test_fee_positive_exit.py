import copy
from pathlib import Path
import unittest
from unittest.mock import patch
from research.phase6.queue_aware_fee_positive_exit import prepare


class FeePositiveExitTest(unittest.TestCase):
    def test_same_conditional_inputs_only_scope_and_fixed_rule_change(self):
        baseline=dict(scope='baseline',initialQuantity='5',initialBasisPerShare='.48',config=dict(minimumEdge='.01'),bindings=[dict(seq=1)])
        original=copy.deepcopy(baseline)
        with patch('research.phase6.queue_aware_fee_positive_exit.baseline',return_value=baseline):r=prepare()
        self.assertEqual(baseline,original)
        for key in original:
            if key!='scope':self.assertEqual(r[key],original[key])
        self.assertTrue(r['executionNetEdgeMustBeRechecked']);self.assertTrue(r['baselineAndCandidateUseIdenticalConditionalStateAndSource'])

    def test_native_candidate_keeps_positive_execution_fee_check_and_old_probe_unchanged(self):
        s=Path('research/phase6/Qw0FeePositiveExitProbe.java').read_text()
        self.assertIn('original.completeValue().max(original.sellValue()).compareTo(minimum)>=0',s)
        self.assertIn('p.purpose().equals("POSITIVE_EDGE_EXIT")&&pnl.compareTo(d(cfg.path("minimumEdge")).multiply(quantity))<0',s)
        old=Path('research/phase6/Qw0RecoveryExitProbe.java').read_text()
        self.assertNotIn('TAKER_SELL',old);self.assertIn('PairPolicy.hedge(',old)
        self.assertIn('stopEvent=ix;stopped=true;break replay;',s)


if __name__=='__main__':unittest.main()
