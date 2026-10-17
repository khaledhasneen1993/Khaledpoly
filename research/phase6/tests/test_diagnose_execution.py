import unittest
from research.phase6.diagnose_execution import diagnose


class DiagnoseExecutionTest(unittest.TestCase):
    def test_missing_telemetry_fails_instead_of_inventing_evidence(self):
        with self.assertRaises(ValueError): diagnose({'fills': 0})

    def test_distinguishes_no_print_from_queue_blocked_and_filled(self):
        rows = []
        for identity, active, volume, remaining, observations in (
                ('none', None, '0', '5', {}),
                ('queue', 100, '19', '5', {'ELIGIBLE_PRINT': 2, 'QUEUE_NOT_EXHAUSTED': 2}),
                ('fill', 100, '25', '0', {'ELIGIBLE_PRINT': 1})):
            rows.append(dict(id=identity, activatedMs=active, activeMs=0 if active is None else 100,
                             eligiblePrintVolume=volume, initialQueueAhead=None if active is None else '20',
                             remainingShares=remaining, printObservations=observations, terminalReason='TEST'))
        result = diagnose({'makerExecutionDiagnostics': rows, 'fills': 1})
        self.assertEqual(result['ordersWithoutSameTokenPrint'], 1)
        self.assertEqual(result['ordersWithEligiblePrint'], 2)
        self.assertEqual(result['ordersWithEligibleVolumeNotExceedingInitialQueue'], 1)
        self.assertEqual(result['printObservations']['ELIGIBLE_PRINT'], 3)
        self.assertEqual(result['decision'], 'NO_GO')
        with self.assertRaises(ValueError): diagnose({'makerExecutionDiagnostics': rows + rows})
