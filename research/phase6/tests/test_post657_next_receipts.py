import copy
import tempfile
import unittest
from unittest.mock import patch

from research.phase6.post657_next_receipts import selection,collect


class Post657NextReceiptsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.spec=selection()

    def test_exact_retained_targets(self):
        self.assertEqual([x['seq'] for x in self.spec['transactions']],[9662,83208]);self.assertEqual(self.spec['maxNewReceiptRequests'],2)
        self.assertEqual(len(set(self.spec['conditions'])),2)
        self.assertEqual(self.spec['sourceReplayArtifactSha256'],'5612085b6dd82f6922100a83adf6b6e60f35b7aac85a0decd4041261fa3ca5d5')

    def test_changed_selection_no_network(self):
        bad=copy.deepcopy(self.spec);bad['maxNewReceiptRequests']=3
        with tempfile.TemporaryDirectory() as tmp,patch('research.phase6.post657_next_receipts.selection',return_value=self.spec):
            with self.assertRaises(ValueError):collect(bad,tmp,read=lambda *_:self.fail('network'))


if __name__=='__main__':unittest.main()
