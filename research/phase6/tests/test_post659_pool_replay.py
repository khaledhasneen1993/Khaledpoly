import unittest

from research.phase6.post659_pool_replay import EXPECTED_BINDINGS,EXPECTED_COMPONENTS,require_native


class Post659PoolReplayTest(unittest.TestCase):
    def test_retained_native661_is_required(self):
        self.assertEqual((EXPECTED_BINDINGS,EXPECTED_COMPONENTS),(661,1564))
        self.assertEqual(require_native()['originalIdentities'],661)


if __name__=='__main__':unittest.main()
