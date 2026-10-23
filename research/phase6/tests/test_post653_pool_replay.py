import unittest

from research.phase6.post653_pool_build import render
from research.phase6.post653_pool_replay import EXPECTED_BINDINGS,EXPECTED_COMPONENTS,require_native


class Post653PoolReplayTest(unittest.TestCase):
    def test_retained_native655_is_required(self):
        self.assertEqual((EXPECTED_BINDINGS,EXPECTED_COMPONENTS),(655,1557))
        self.assertEqual(require_native()['originalIdentities'],655)

    def test_only_exact653_helper_identity_is_replaced(self):
        old='x a6faa2118ba0fdc721a6eb83876886169f0c68980c0c88e04c1cb82ce6835f3c y Exact frozen real653 pool required z'
        spec={'poolLogicalSha256':'6dcf2f28956569965373d60ff040c2737d4c8412d812ac50def2b5608fb2881f'};new=render(old,spec)
        self.assertIn(spec['poolLogicalSha256'],new);self.assertIn('Exact frozen real655 pool required',new)
        self.assertNotIn('Exact frozen real653 pool required',new)


if __name__=='__main__':unittest.main()
