import tempfile
from pathlib import Path
import unittest

from research.phase6.post649_pool_build import materialize,LABELS
from research.phase6.post649_pool_inputs import prepare
from research.phase6.post649_pool_replay import EXPECTED_BINDINGS,EXPECTED_COMPONENTS,require_native


class Post649PoolReplayTest(unittest.TestCase):
    def test_retained_native651_is_required(self):
        self.assertEqual((EXPECTED_BINDINGS,EXPECTED_COMPONENTS),(651,1550))
        self.assertEqual(require_native()['originalIdentities'],651)

    def test_inputs_and_generated_helper_pin_exact651(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs=Path(tmp)/'inputs';summary=prepare(inputs)
            self.assertEqual((summary['poolBindings'],summary['actualComponents']),(651,1550))
            source=Path(tmp)/'source';result=materialize(source);text=(source/LABELS).read_text()
            self.assertEqual(result['poolLogicalSha256'],'a6b28410c97ccd40a44e012aad3b9b647e77d00897ededc286ed884fc3ab7b9e')
            self.assertIn(result['poolLogicalSha256'],text);self.assertIn('Exact frozen real651 pool required',text)
            self.assertNotIn('Exact frozen real649 pool required',text)


if __name__=='__main__':unittest.main()
