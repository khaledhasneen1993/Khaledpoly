"""Fail closed on forged, missing or cross-purpose public PAPER evidence."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from research.phase6.public_smoke_gate import audit, SPEC
from research.phase3.polybot_sdk.model import dumps


def fixtures():
    base = {'scope': 'PUBLIC_INTEGRATION_SMOKE_NOT_QUALIFICATION',
            'decision': 'NO_GO', 'liveAllowed': False,
            'phase4CaptureIntegrity': 'PASS', 'signalCollectorExit': 0,
            'paperExecutionMode': False, 'newStrategiesExecuted': False,
            'observedPaperAccount': None,
            'signalRowsByVenue': {'binance-spot': 0, 'bybit-spot': 0}}
    paper = dict(base, paperExecutionMode=True,
                 observedPaperAccount={'id': 'paper-only'},
                 executionReplayParity='MATCH_REPORT_AND_ACTION_AUDIT',
                 executionReplay={'decision': 'NO_GO'},
                 virtualExecutionReceipts={'PAPER_SUBMITTED': 0},
                 executionLabels={})
    signal = {'scope': 'PUBLIC_SPOT_SIGNAL_ABLATION_NOT_A_STRATEGY',
              'decision': 'NO_GO', 'liveAllowed': False,
              'strategyQualified': False, 'predictionQualified': False,
              'venueFillEvidence': False, 'perVenueSymbol': {}}
    forward = {'scope': 'PUBLIC_CEX_FORWARD_PRICE_DIAGNOSTICS',
               'decision': 'NO_GO', 'liveAllowed': False,
               'netTradeProfitabilityProven': False,
               'prospectivelyPreregistered': False,
               'dataSource': 'PUBLIC_PRINT_NOT_EXECUTABLE_QUOTE',
               'perVenueStrategy': {}}
    return {'capture': base, 'paper': paper, 'signals': signal, 'forward': forward}


class SmokeGateTest(unittest.TestCase):
    def write(self, root, rows):
        for name, (relative, _) in SPEC.items():
            path = Path(root) / relative
            path.parent.mkdir(exist_ok=True, parents=True)
            path.write_text(dumps(rows[name]) + '\n', encoding='utf-8')

    def test_unqualified_sources_and_virtual_paper_are_allowed_as_software_only(self):
        with tempfile.TemporaryDirectory() as root:
            self.write(root, fixtures())
            result = audit(root)
            self.assertEqual(result['verifiedArtifacts'], 4)
            self.assertEqual(result['virtualPaperExecutionReplayParity'],
                             'MATCH_REPORT_AND_ACTION_AUDIT')
            self.assertFalse(result['realMoneyExecutionEnabled'])
            self.assertEqual(result['decision'], 'NO_GO')

    def test_missing_report_never_counts_as_pass(self):
        with tempfile.TemporaryDirectory() as root:
            self.write(root, fixtures())
            (Path(root) / SPEC['paper'][0]).unlink()
            with self.assertRaisesRegex(ValueError, 'Missing'):
                audit(root)

    def test_forged_profits_or_live_claims_fail_closed(self):
        for name, field, value in (
            ('signals', 'strategyQualified', True),
            ('forward', 'netTradeProfitabilityProven', True),
            ('capture', 'liveAllowed', True),
            ('paper', 'executionReplayParity', 'NOT_MATCHED'),
        ):
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as root:
                    data = fixtures()
                    data[name][field] = value
                    self.write(root, data)
                    with self.assertRaises(ValueError):
                        audit(root)

    def test_capture_cannot_impersonate_paper_execution(self):
        with tempfile.TemporaryDirectory() as root:
            data = fixtures()
            data['capture']['paperExecutionMode'] = True
            self.write(root, data)
            with self.assertRaisesRegex(ValueError, 'Read-only'):
                audit(root)

    def test_bybit_inaccessible_is_neither_fabricated_nor_fatal_to_ci(self):
        with tempfile.TemporaryDirectory() as root:
            data = fixtures()
            data['capture']['signalRowsByVenue'] = {'binance-spot': 12, 'bybit-spot': 0}
            self.write(root, data)
            self.assertTrue(audit(root)['sourceBlockOrMissingDataStillPossible'])


if __name__ == '__main__':
    unittest.main()
