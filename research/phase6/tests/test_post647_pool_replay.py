import tempfile
from pathlib import Path
import unittest

from research.phase6.post647_pool_build import materialize,LABELS
from research.phase6.post647_pool_inputs import prepare
from research.phase6.post647_pool_replay import EXPECTED_BINDINGS,EXPECTED_COMPONENTS,require_native


class Post647PoolReplayTest(unittest.TestCase):
    def test_retained_native649_is_required(self):
        self.assertEqual((EXPECTED_BINDINGS,EXPECTED_COMPONENTS),(649,1540))
        self.assertEqual(require_native()['originalIdentities'],649)

    def test_inputs_and_generated_helper_pin_exact649(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs=Path(tmp)/'inputs';summary=prepare(inputs)
            self.assertEqual((summary['poolBindings'],summary['actualComponents']),(649,1540))
            source=Path(tmp)/'source';result=materialize(source);text=(source/LABELS).read_text()
            self.assertEqual(result['poolLogicalSha256'],'377a4394ec3542dfa085f33771a238e030142303b327ef8a14caf3b93de6481a')
            self.assertIn(result['poolLogicalSha256'],text);self.assertIn('Exact frozen real649 pool required',text)
            self.assertNotIn('Exact frozen real643 pool required',text)


if __name__=='__main__':unittest.main()
