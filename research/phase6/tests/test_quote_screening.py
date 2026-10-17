import copy
import unittest
from research.phase6.compare_quote_candidate import screening


class QuoteScreeningTest(unittest.TestCase):
    def reports(self):
        baseline = dict(configuration={'makerImprovementTicks': 1, 'queueMultiplier': 2}, inputSha256='a'*64,
                        recordingClosedCleanly=True, netRealizedPnl=0, submittedOrders=44, fills=0,
                        pairCompletions=[], holdings={}, riskBreaches=0, halted=False, maxDrawdown=0,
                        residualExpiryWorstCaseNotional=0)
        candidate = copy.deepcopy(baseline); candidate['configuration']['makerImprovementTicks'] = 0
        return baseline, candidate

    def test_more_fills_or_positive_realized_with_residual_is_not_success(self):
        baseline, candidate = self.reports(); candidate['fills'] = 100
        self.assertFalse(screening(baseline, candidate)['candidateWorthIndependentTest'])
        candidate.update(netRealizedPnl=1, pairCompletions=[{'quantity': 1}], holdings={'x': {'shares': 5}})
        self.assertFalse(screening(baseline, candidate)['candidateWorthIndependentTest'])
        candidate['holdings'] = {}; result = screening(baseline, candidate)
        self.assertTrue(result['candidateWorthIndependentTest']); self.assertEqual(result['decision'], 'NO_GO')

    def test_changed_queue_different_tape_or_incomplete_data_rejected(self):
        for change in ('queue', 'tape', 'incomplete'):
            baseline, candidate = self.reports()
            if change == 'queue': candidate['configuration']['queueMultiplier'] = 1
            if change == 'tape': candidate['inputSha256'] = 'b'*64
            if change == 'incomplete': candidate['recordingClosedCleanly'] = False
            with self.assertRaises(ValueError): screening(baseline, candidate)
