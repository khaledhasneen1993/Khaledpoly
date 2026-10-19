from decimal import Decimal
import json
from pathlib import Path
import unittest
from research.phase6.queue_aware_quote_screen import screen


class QueueAwareScreenTest(unittest.TestCase):
    def test_frozen_same34_comparison_and_actual_size_rejections(self):
        r=screen()
        saved=json.loads(Path('research/experiments/queue-aware-quote-20261019/state-screen.json').read_text())
        self.assertEqual(json.loads(json.dumps(r,default=str)),saved)
        self.assertEqual((r['witnessCount'],r['actualLegacySubmittedStates'],r['baselineDQ3PricedStates'],r['candidatePricedStates']),
                         (34,1,11,7))
        self.assertEqual((r['additionalLawfulStatesVsLegacy'],r['changedPricedPairsVsDQ3']),(6,6))
        size_rejected=[s for s in r['states'] if set(s['actualLegacyReason'])&{'MIN_SIZE','MIN_SIZE_AND_NET_EDGE'}]
        self.assertEqual(len(size_rejected),19);self.assertTrue(all(s['proposal'] is None for s in size_rejected))
        # Broader metric20 also includes a below-size snapshot already RESTING.
        self.assertEqual(r['originalSizeBlockedStatesStillBlocked'],20)
        for s in r['states']:
            p=s['proposal']
            if p:
                self.assertEqual(p['quantity'],s['originalQuantity'])
                self.assertGreaterEqual(p['requiredEdge'],p['originalRequiredEdge'])
                self.assertGreaterEqual(p['netEdgeTotal'],p['quantity']*p['requiredEdge'])
        self.assertFalse(r['candidateAccountSimulated']);self.assertEqual(r['fillsCreated'],0)
        self.assertFalse(r['netPnlRecomputed'])


if __name__=='__main__':unittest.main()
