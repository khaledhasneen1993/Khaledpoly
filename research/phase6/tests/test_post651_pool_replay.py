import unittest

from research.phase6.post651_pool_build import render
from research.phase6.post651_pool_replay import EXPECTED_BINDINGS,EXPECTED_COMPONENTS,require_native


class Post651PoolReplayTest(unittest.TestCase):
    def test_retained_native653_is_required(self):
        self.assertEqual((EXPECTED_BINDINGS,EXPECTED_COMPONENTS),(653,1553))
        self.assertEqual(require_native()['originalIdentities'],653)

    def test_only_exact651_helper_identity_is_replaced(self):
        old='x a6b28410c97ccd40a44e012aad3b9b647e77d00897ededc286ed884fc3ab7b9e y Exact frozen real651 pool required z'
        spec={'poolLogicalSha256':'a6faa2118ba0fdc721a6eb83876886169f0c68980c0c88e04c1cb82ce6835f3c'};new=render(old,spec)
        self.assertIn(spec['poolLogicalSha256'],new);self.assertIn('Exact frozen real653 pool required',new)
        self.assertNotIn('Exact frozen real651 pool required',new)


if __name__=='__main__':unittest.main()
