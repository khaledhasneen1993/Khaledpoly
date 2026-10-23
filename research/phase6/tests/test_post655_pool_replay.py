import unittest

from research.phase6.post655_pool_build import render
from research.phase6.post655_pool_replay import EXPECTED_BINDINGS,EXPECTED_COMPONENTS,require_native


class Post655PoolReplayTest(unittest.TestCase):
    def test_retained_native657_is_required(self):
        self.assertEqual((EXPECTED_BINDINGS,EXPECTED_COMPONENTS),(657,1559))
        self.assertEqual(require_native()['originalIdentities'],657)

    def test_only_exact655_helper_identity_is_replaced(self):
        old='x 6dcf2f28956569965373d60ff040c2737d4c8412d812ac50def2b5608fb2881f y Exact frozen real655 pool required z'
        spec={'poolLogicalSha256':'bb479f14c58ead5e1b7dc7234dc98f5e9abb06cd586b138bd351a66b9d864f93'};new=render(old,spec)
        self.assertIn(spec['poolLogicalSha256'],new);self.assertIn('Exact frozen real657 pool required',new)
        self.assertNotIn('Exact frozen real655 pool required',new)


if __name__=='__main__':unittest.main()
