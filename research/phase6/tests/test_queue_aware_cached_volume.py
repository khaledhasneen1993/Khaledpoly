import unittest
from research.phase6.queue_aware_cached_traffic import actual_priced_volume


class CachedVolumeTest(unittest.TestCase):
    def test_exact_integer_component_prices_not_aggregate_public_price(self):
        parts=[dict(makerToken='a',makerSide='BUY',sharesRaw=1000001,collateralRaw=480001),
               dict(makerToken='a',makerSide='BUY',sharesRaw=1000000,collateralRaw=470000),
               dict(makerToken='b',makerSide='BUY',sharesRaw=1000000,collateralRaw=100000)]
        self.assertEqual(actual_priced_volume(parts,'a','.48'),1000000)
        self.assertEqual(actual_priced_volume(parts,'a','.47'),1000000)
        self.assertEqual(actual_priced_volume(parts,'a','.46'),0)
        self.assertEqual(actual_priced_volume(parts,'a','.49'),2000001)


if __name__=='__main__':unittest.main()
