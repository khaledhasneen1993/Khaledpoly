"""Bounded public source probes never certify a venue, strategy or fills."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from research.phase4 import probe

HASH = 'a' * 64


class SourceProbeTest(unittest.TestCase):
    def test_available_sources_remain_explicitly_unqualified(self):
        def fake_http(url):
            if url.endswith('/time'):
                return '1800000000', HASH
            if '/tags/slug/' in url:
                slug = url.split('/')[-1]
                return {'id': '5', 'slug': slug}, HASH
            return {'events': [{'id': 'one'}], 'next_cursor': 'other'}, HASH
        class FakeCollector:
            def __init__(self, venue):
                self.venue = venue
            def poll(self):
                return {'status': 'SAMPLED_PUBLIC_TRADES'}, []
        with patch('research.phase4.probe._http', fake_http), patch(
                'research.phase4.probe.PublicCollector', FakeCollector):
            result = probe.public_source_probe()
        self.assertEqual(result['reachableSources'], 5)
        self.assertTrue(result['allSourcesReachable'])
        self.assertFalse(result['continuousRecording'])
        self.assertFalse(result['venueFillEvidence'])
        self.assertEqual(result['decision'], 'NO_GO')
        self.assertEqual(result['sources']['gamma-sports']['eventCount'], 1)

    def test_blocked_and_invalid_source_cannot_look_successful(self):
        def fake_http(url):
            if url.endswith('/time'):
                raise HTTPError(url, 403, 'denied', {}, None)
            if 'sports' in url:
                return {'slug': 'sports', 'id': 'invalid'}, HASH
            if 'politics' in url:
                return {'slug': 'politics', 'id': '12'}, HASH
            return {'markets': []}, HASH
        class FakeCollector:
            def __init__(self, venue):
                self.venue = venue
            def poll(self):
                return ({'status': 'HTTP_BACKOFF', 'httpStatus': 403,
                         'sourceAccessBlocked': True}, [])
        with patch('research.phase4.probe._http', fake_http), patch(
                'research.phase4.probe.PublicCollector', FakeCollector):
            result = probe.public_source_probe()
        self.assertEqual(result['sources']['polymarket-clob-time']['httpStatus'], 403)
        self.assertEqual(result['sources']['gamma-sports']['status'], 'INVALID_RESPONSE')
        self.assertEqual(result['sources']['gamma-politics']['status'], 'INVALID_RESPONSE')
        self.assertEqual(result['reachableSources'], 0)
        self.assertFalse(result['allSourcesReachable'])


if __name__ == '__main__':
    unittest.main()
