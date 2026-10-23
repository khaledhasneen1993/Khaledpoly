import copy
import tempfile
import unittest
from unittest.mock import patch

from research.phase6.post659_next_receipts import selection,collect


class Post659NextReceiptsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.spec=selection()

    def test_exact_retained_targets(self):
        self.assertEqual([x['seq'] for x in self.spec['transactions']],[9801,83216]);self.assertEqual(self.spec['maxNewReceiptRequests'],2)
        self.assertEqual(len(set(self.spec['conditions'])),1)
        self.assertEqual(self.spec['sourceReplayArtifactSha256'],'bddf259f8d999668f3cafcdadb99479d3c7c66f361f9a5d9ffc1812e23657cda')

    def test_changed_selection_no_network(self):
        bad=copy.deepcopy(self.spec);bad['maxNewReceiptRequests']=3
        with tempfile.TemporaryDirectory() as tmp,patch('research.phase6.post659_next_receipts.selection',return_value=self.spec):
            with self.assertRaises(ValueError):collect(bad,tmp,read=lambda *_:self.fail('network'))


if __name__=='__main__':unittest.main()
