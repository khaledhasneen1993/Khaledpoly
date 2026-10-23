import unittest

from research.phase6.post657_pool_build import render
from research.phase6.post657_pool_replay import EXPECTED_BINDINGS,EXPECTED_COMPONENTS,require_native


class Post657PoolReplayTest(unittest.TestCase):
    def test_retained_native659_is_required(self):
        self.assertEqual((EXPECTED_BINDINGS,EXPECTED_COMPONENTS),(659,1562))
        self.assertEqual(require_native()['originalIdentities'],659)

    def test_only_exact657_helper_identity_is_replaced(self):
        old='x bb479f14c58ead5e1b7dc7234dc98f5e9abb06cd586b138bd351a66b9d864f93 y Exact frozen real657 pool required z'
        spec={'poolLogicalSha256':'977b090ad0737c6c43fe9dd8d0fd7b96f2da94534f29b31f7b935f769232355b'};new=render(old,spec)
        self.assertIn(spec['poolLogicalSha256'],new);self.assertIn('Exact frozen real659 pool required',new)
        self.assertNotIn('Exact frozen real657 pool required',new)


if __name__=='__main__':unittest.main()
