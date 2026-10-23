from decimal import Decimal as D
import unittest
from research.phase6.queue_aware_unhedged_timing import wait_ms


class UnhedgedTimingTest(unittest.TestCase):
    def test_original_cap_and_expiry_budget(self):
        self.assertEqual(wait_ms(140000,30000,D(0)),5000)
        self.assertEqual(wait_ms(12000,30000,D(0)),3000)
        self.assertEqual(wait_ms(-1,30000,D(0)),0)

    def test_causal_volatility_shortens_wait_with_floor(self):
        self.assertEqual(wait_ms(140000,30000,D('.01')),2500)
        self.assertEqual(wait_ms(140000,30000,D('.002')),4166)

    def test_invalid_original_inputs_fail(self):
        for remaining,unhedged,vol in [(1000,0,D(0)),(1000,30000,D('-.1'))]:
            with self.assertRaises(ValueError):wait_ms(remaining,unhedged,vol)


if __name__=='__main__':unittest.main()
