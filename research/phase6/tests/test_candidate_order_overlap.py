import unittest
from research.phase6.candidate_order_overlap import analyze


class CandidateOverlapTest(unittest.TestCase):
    def test_causal_source_activation_and_terminal_boundaries(self):
        candidate = dict(route='COMPLEMENT_BUY_CANDIDATE', improvementTicks=1, token='a', sourceMs=20, at=22, printPrice='.5')
        order = dict(buy=True, token='a', activatedMs=10, terminalMs=30, price='.5', id='one',
                     terminalReason='CANCEL', initialQueueAhead=10, remainingQueueAhead=10)
        census = dict(examples=[candidate], logicalTapeSha256='x')
        run = lambda: analyze(census, dict(makerExecutionDiagnostics=[order]))
        self.assertEqual(run()['priceRelationOrderObservations'], {'AT_PRINT':1})
        order['price'] = '.6'
        self.assertEqual(run()['priceRelationOrderObservations'], {'MORE_AGGRESSIVE_BUY':1})
        order['price'] = '.4'
        self.assertEqual(run()['priceRelationOrderObservations'], {'LESS_AGGRESSIVE_BUY':1})
        for activation, terminal in [(20,30),(21,30),(10,22),(None,30),(10,None)]:
            order.update(activatedMs=activation, terminalMs=terminal)
            self.assertEqual(run()['rowsWithActiveTargetBuy'],0)
