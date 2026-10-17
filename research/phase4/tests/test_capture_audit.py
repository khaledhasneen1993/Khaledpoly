"""Phase 4 closed-session audit: hashes, coverage, time, fail-closed semantics."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from research.phase3.polybot_sdk.model import dumps
from research.phase3.polybot_sdk.features import fingerprint
from research.phase4.audit import inspect_session, audit_capture

START = 1800000000000


def make_session(root, start=START, duration=10000, block_bybit=False):
    root.mkdir()
    sample = []
    for venue in ('binance-spot', 'bybit-spot'):
        payload = [] if venue == 'binance-spot' else {
            'retCode': 0, 'result': {'category': 'spot', 'list': []}}
        sample.append({'status': 'SAMPLED_PUBLIC_TRADES', 'venue': venue, 'symbol': 'BTCUSDT',
                       'polledMs': start+100, 'payload': payload,
                       'payloadSha256': fingerprint(payload), 'uniqueTrades': 0,
                       'duplicateTrades': 0, 'olderTrades': 0,
                       'coverage': 'SAMPLED_NOT_COMPLETE_TRADE_TAPE'})
    if block_bybit:
        sample.append({'status': 'HTTP_BACKOFF', 'venue': 'bybit-spot', 'symbol': 'BTCUSDT',
                       'polledMs': start+200, 'sourceAccessBlocked': True})
    (root / 'public.jsonl').write_text(''.join(dumps(row) + '\n' for row in sample))
    (root / 'features.jsonl').write_text('')
    (root / 'manifest.json').write_text(dumps({
        'schema': 2, 'mode': 'PUBLIC_RECORD_ONLY', 'symbol': 'BTCUSDT',
        'seconds': str(duration/1000), 'interval': '5', 'startedAtMs': start,
        'coverage': 'SAMPLED', 'liveAllowed': False}))
    metrics = {v: {'sampledPolls': 1, 'backoffPolls': 0,
                    'errorPolls': int(block_bybit and v == 'bybit-spot'),
                    'featureRows': 0, 'duplicateTrades': 0, 'olderTrades': 0,
                    'sourceAccessBlocked': bool(block_bybit and v == 'bybit-spot')}
               for v in ('binance-spot', 'bybit-spot')}
    (root / 'report.json').write_text(dumps({
        'complete': True, 'featureRows': 0, 'errors': int(block_bybit),
        'coverage': 'SAMPLED', 'startedAtMs': start, 'endedAtMs': start+duration,
        'elapsedMonotonicMs': duration, 'fileSha256': {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in ('public.jsonl', 'features.jsonl')},
        'perVenue': metrics, 'completeTradeTape': False,
        'sevenDayHoldoutQualified': False, 'decision': 'NO_GO', 'liveAllowed': False}))
    return root


class CaptureAuditTest(unittest.TestCase):
    def test_closed_session_integrity_and_explicit_no_go(self):
        with tempfile.TemporaryDirectory() as folder:
            session = make_session(Path(folder) / 'first')
            examined = inspect_session(session)
            self.assertEqual(examined['perVenue']['binance-spot']['sampledPolls'], 1)
            report = audit_capture([session])
            self.assertIn('INSUFFICIENT_CAPTURE_DAYS', report['issues'])
            self.assertFalse(report['strategyQualified'])
            self.assertFalse(report['completeTradeTape'])

    def test_edited_tape_is_rejected_not_silently_tolerated(self):
        with tempfile.TemporaryDirectory() as folder:
            session = make_session(Path(folder) / 'first')
            with (session / 'public.jsonl').open('a') as stream:
                stream.write('{}\n')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                inspect_session(session)

    def test_blocked_bybit_is_preserved_and_prevents_qualification(self):
        with tempfile.TemporaryDirectory() as folder:
            session = make_session(Path(folder) / 'first', block_bybit=True)
            result = audit_capture([session], min_days=1)
            self.assertIn('bybit-spot:SOURCE_ACCESS_BLOCKED', result['issues'])


    def test_successful_sampling_gap_is_not_hidden_by_healthy_polls(self):
        with tempfile.TemporaryDirectory() as folder:
            session = make_session(Path(folder) / 'first', duration=86400000)
            report = audit_capture([session], min_days=1)
            self.assertIn('binance-spot:TERMINAL_SUCCESS_GAP', report['issues'])
            self.assertIn('bybit-spot:TERMINAL_SUCCESS_GAP', report['issues'])
            self.assertFalse(report['continuousSamplingWindow'])

    def test_duplicate_session_input_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            session = make_session(Path(folder) / 'first')
            with self.assertRaisesRegex(ValueError, 'unique'):
                audit_capture([session, session])

    def test_overlapping_archive_segments_are_not_mistaken_for_continuity(self):
        with tempfile.TemporaryDirectory() as folder:
            first = make_session(Path(folder) / 'first', start=START, duration=10000)
            second = make_session(Path(folder) / 'second', start=START+5000, duration=10000)
            report = audit_capture([first, second])
            self.assertIn('OVERLAPPING_SESSIONS', report['issues'])
            self.assertFalse(report['continuousSamplingWindow'])


if __name__ == '__main__':
    unittest.main()
