"""Restartable segment capture without network access or venue execution."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from research.phase3.polybot_sdk.model import decode, dumps
from research.phase4 import recorder
from research.phase4.audit import inspect_session


class FakePublicCollector:
    def __init__(self, venue, symbol):
        from research.phase3.polybot_sdk.collector import TradeWatermark
        self.venue, self.symbol = venue, symbol
        self._watermark = TradeWatermark()

    def poll(self):
        from research.phase3.polybot_sdk.features import fingerprint
        data = ([] if self.venue == 'binance-spot' else
                {'retCode': 0, 'result': {'category': 'spot', 'list': []}})
        return {'status': 'SAMPLED_PUBLIC_TRADES', 'payload': data,
                'payloadSha256': fingerprint(data), 'uniqueTrades': 0,
                'duplicateTrades': 0, 'olderTrades': 0,
                'coverage': 'SAMPLED_NOT_COMPLETE_TRADE_TAPE'}, []


SHA = 'a' * 40


class RecorderTest(unittest.TestCase):
    def perform(self, directory, **opts):
        with patch('research.phase3.polybot_sdk.collector.PublicCollector', FakePublicCollector):
            return recorder.run_capture(directory, source_revision=SHA, segment_seconds=5,
                                        interval=1, max_new_segments=1, **opts)

    def test_frozen_plan_resume_and_cross_segment_watermark(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'capture'
            first = self.perform(path)
            self.assertEqual(first['newSegments'], 1)
            self.assertEqual(first['decision'], 'NO_GO')
            second = self.perform(path)
            self.assertEqual(second['sessions'], 2)
            self.assertEqual(second['newSegments'], 1)
            self.assertNotIn('WATERMARK_DISCONTINUITY', second['issues'])
            self.assertEqual(second['frozenPlan']['sourceRevision'], SHA)
            self.assertFalse(second['qualifiesCompleteMarketTape'])
            self.assertEqual(len(list((path / 'segments').iterdir())), 2)
            with self.assertRaisesRegex(ValueError, 'Frozen capture plan differs'):
                self.perform(path, symbol='ETHUSDT')
            latest = decode((path / 'latest-audit.json').read_text())
            self.assertEqual(latest['sessions'], 2)

    def test_incomplete_segment_requires_explicit_preservation(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'capture'
            self.perform(path)
            interrupted = path / 'segments' / 'segment-000002'
            interrupted.mkdir()
            (interrupted / 'public.jsonl').write_text('incomplete')
            with self.assertRaisesRegex(ValueError, 'Interrupted segment'):
                self.perform(path)
            report = self.perform(path, quarantine_incomplete=True)
            self.assertIn('RECOVERED_INTERRUPTED_SEGMENT', report['issues'])
            self.assertTrue((path / 'interrupted' / 'segment-000002').exists())
            self.assertTrue((path / 'segments' / 'segment-000003').exists())
            self.assertFalse(report['continuousSamplingWindow'])

    def test_completed_but_corrupt_segment_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'capture'
            self.perform(path)
            tape = path / 'segments' / 'segment-000001' / 'public.jsonl'
            with tape.open('a') as stream:
                stream.write('{}\n')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                self.perform(path, quarantine_incomplete=True)

    def test_clean_commit_required_outside_explicit_test_injection(self):
        with patch('research.phase4.recorder.current_clean_commit',
                   side_effect=ValueError('dirty checkout')):
            with tempfile.TemporaryDirectory() as root:
                with self.assertRaisesRegex(ValueError, 'dirty'):
                    recorder.run_capture(Path(root) / 'capture', max_new_segments=1)


if __name__ == '__main__':
    unittest.main()
