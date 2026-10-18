import json
from pathlib import Path
import unittest
from research.phase6.depth_quote_screen import screen


class DepthQuoteScreenTest(unittest.TestCase):
    def test_preregistered_state_screen_reproduces_without_size_or_risk_relaxation(self):
        r=json.loads(json.dumps(screen(),default=str))
        self.assertEqual(r,json.loads(Path('research/experiments/depth-quote-20261018/state-screen.json').read_text()))
        self.assertEqual(r['candidatePricedStates'],11);self.assertEqual(r['additionalPricedStates'],10)
        self.assertEqual(r['fillsCreated'],0);self.assertFalse(r['candidateStateTrajectorySimulated'])
        self.assertFalse(r['independentPaperQualificationAllowed'])
        for row in r['states']:
            if any(k in row['actualLegacyReason'] for k in ('MIN_SIZE','MIN_SIZE_AND_NET_EDGE','RESTING')):
                self.assertIsNone(row['proposal'])
            if row['proposal']:
                self.assertEqual(row['proposal']['quantity'],row['originalQuantity'])
                self.assertEqual(row['proposal']['requiredEdge'],row['originalRequiredEdge'])


if __name__=='__main__':unittest.main()
