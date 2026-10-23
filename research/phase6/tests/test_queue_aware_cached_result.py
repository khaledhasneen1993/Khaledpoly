import json
import unittest
from research.phase6.queue_aware_cached_traffic import QROOT,analyze


class QueueAwareCachedResultTest(unittest.TestCase):
    def test_exact_complete_cached_gate_new_quote_not_original_binding(self):
        r=analyze()
        self.assertEqual(r,json.loads((QROOT/'cached-traffic.json').read_text()))
        self.assertEqual(r['selectedStarts'],7);self.assertEqual(r['positiveActualPricedTargetLegs'],1)
        supported=[s for s in r['states'] if s['completeActualPriceCompatibleSharesRaw']>0]
        self.assertEqual([s['originalSequence'] for s in supported],[243583])
        s=supported[0];self.assertEqual(s['completeTargetObservations'],39)
        self.assertEqual(s['completeActualPriceCompatibleSharesRaw'],607752076)
        self.assertEqual(s['qw0TargetQuote']['price'],'0.48')
        self.assertEqual(s['originalCensusQuotes'][0]['price'],'0.49')
        self.assertTrue(all(s['originalPublicObservationBindingUnmodified'] for s in r['states']))
        self.assertEqual((r['newPublicReads'],r['newTapeScans'],r['fillsCreated']),(0,0,0))
        self.assertFalse(r['activationQueueOrRestingCancelProven']);self.assertFalse(r['netPnlRecomputed'])


if __name__=='__main__':unittest.main()
