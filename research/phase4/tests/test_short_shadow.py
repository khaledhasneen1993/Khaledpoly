"""Phase-four invariant: a positive-length shadow window samples once."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from research.phase3.polybot_sdk.runtime import shadow_run


class ShortShadowRunTest(unittest.TestCase):
    def test_first_sample_cannot_be_lost_during_startup(self):
        class Client:
            def snapshot(self):
                return {'sessionId':'test','account':{'id':'paper-only'},
                        'sequence':1,'generatedMs':1800000000000}
        with tempfile.TemporaryDirectory() as tmp:
            with patch('research.phase3.polybot_sdk.runtime.evaluate',
                       return_value={'kind':'synthetic'}):
                output=shadow_run(Client(),Path(tmp)/'session',
                                  seconds=.000001,interval=1)
            self.assertTrue(output['complete'])
            self.assertEqual(output['snapshots'],1)
            self.assertEqual(output['decision'],'NO_GO')
            self.assertFalse(output['liveAllowed'])


if __name__=='__main__':
    unittest.main()
