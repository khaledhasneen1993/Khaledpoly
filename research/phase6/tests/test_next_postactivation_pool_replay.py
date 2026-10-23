import tempfile
from pathlib import Path
import unittest

from research.phase6.next_postactivation_pool_build import materialize,LABELS
from research.phase6.next_postactivation_pool_inputs import prepare
from research.phase6.next_postactivation_pool_replay import EXPECTED_BINDINGS,EXPECTED_COMPONENTS,require_native


class NextPostActivationPoolReplayTest(unittest.TestCase):
    def test_retained_native647_is_required(self):
        self.assertEqual((EXPECTED_BINDINGS,EXPECTED_COMPONENTS),(647,1536))
        self.assertEqual(require_native()['originalIdentities'],647)

    def test_inputs_and_generated_helper_pin_exact647(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs=Path(tmp)/'inputs';summary=prepare(inputs)
            self.assertEqual((summary['poolBindings'],summary['actualComponents']),(647,1536))
            source=Path(tmp)/'source';result=materialize(source);text=(source/LABELS).read_text()
            self.assertEqual(result['poolLogicalSha256'],'aa3f42e1cfff24fd5c9f3750136f56a4e23d7cd333a9d949e4224b176c4a4da4')
            self.assertIn(result['poolLogicalSha256'],text);self.assertIn('Exact frozen real647 pool required',text)
            self.assertNotIn('Exact frozen real643 pool required',text)


if __name__=='__main__':unittest.main()
