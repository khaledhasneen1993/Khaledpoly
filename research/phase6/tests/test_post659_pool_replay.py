import unittest

from research.phase6.post659_pool_build import render
from research.phase6.post659_pool_replay import EXPECTED_BINDINGS,EXPECTED_COMPONENTS,require_native


class Post659PoolReplayTest(unittest.TestCase):
    def test_retained_native661_is_required(self):
        self.assertEqual((EXPECTED_BINDINGS,EXPECTED_COMPONENTS),(661,1564))
        self.assertEqual(require_native()['originalIdentities'],661)

    def test_only_exact659_helper_identity_is_replaced(self):
        old='x 977b090ad0737c6c43fe9dd8d0fd7b96f2da94534f29b31f7b935f769232355b y Exact frozen real659 pool required z'
        spec={'poolLogicalSha256':'f9f2c6646f403f9a3ea0112e1a72dcf5685e90dec70fb4334e4967242be7a121'};new=render(old,spec)
        self.assertIn(spec['poolLogicalSha256'],new);self.assertIn('Exact frozen real661 pool required',new)
        self.assertNotIn('Exact frozen real659 pool required',new)


if __name__=='__main__':unittest.main()
