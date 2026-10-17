"""Phase 4: replay-safe sampling and fail-closed data-source accounting."""
from io import BytesIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from research.phase3.polybot_sdk.collector import PublicCollector, TradeWatermark, collect
from research.phase3.polybot_sdk.features import normalize_trades
from research.phase3.polybot_sdk.model import decode, dumps

BASE = 1800000000000


class Response:
    def __init__(self, payload):
        self.payload = dumps(payload).encode('utf-8')

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, *_):
        return self.payload


class Opener:
    def __init__(self, *payloads):
        self.responses = iter(payloads)

    def open(self, *_args, **_kwargs):
        payload = next(self.responses)
        if isinstance(payload, Exception):
            raise payload
        return Response(payload)


def binance(trade_id, timestamp):
    return {'a': trade_id, 'p': '60000', 'q': '.1', 'T': timestamp}


def bybit(trades):
    return {'retCode': 0, 'result': {'category': 'spot', 'list': [
        {'execId': trade_id, 'symbol': 'BTCUSDT', 'price': '60000',
         'size': '.1', 'time': str(timestamp)} for trade_id, timestamp in trades]}}


class CollectorIntegrityTest(unittest.TestCase):
    def test_equal_millisecond_new_binance_ids_are_preserved_once(self):
        c = PublicCollector('binance-spot')
        c._opener = Opener([binance(1, BASE-2), binance(2, BASE-2)],
                           [binance(2, BASE-2), binance(3, BASE-2), binance(4, BASE-1)],
                           [binance(1, BASE-2), binance(4, BASE-1)])
        first, rows1 = c.poll(BASE)
        second, rows2 = c.poll(BASE + 5)
        third, rows3 = c.poll(BASE + 10)
        self.assertEqual([len(rows1), len(rows2), len(rows3)], [2, 2, 0])
        self.assertEqual(second['duplicateTrades'], 1)
        self.assertEqual(third['olderTrades'], 1)
        self.assertEqual(third['duplicateTrades'], 1)
        self.assertEqual(first['coverage'], 'SAMPLED_NOT_COMPLETE_TRADE_TAPE')
        self.assertEqual(second['lastSourceMs'], BASE - 1)

    def test_bybit_equal_timestamp_and_strict_out_of_order(self):
        c = PublicCollector('bybit-spot')
        c._opener = Opener(bybit([('a', BASE-3), ('b', BASE-3)]),
                           bybit([('c', BASE-3), ('d', BASE-2)]))
        _, rows1 = c.poll(BASE)
        _, rows2 = c.poll(BASE+5)
        self.assertEqual([len(rows1), len(rows2)], [2, 2])
        self.assertEqual(c._watermark.source_ms, BASE-2)

    def test_fail_closed_on_invalid_trade_and_watermark_bound(self):
        c = PublicCollector('binance-spot')
        c._opener = Opener([binance(1, BASE-2), binance(1, BASE-2)])
        with self.assertRaises(ValueError):
            c.poll(BASE)
        self.assertEqual(c._watermark.source_ms, -1)
        watermark = TradeWatermark(max_ids_at_timestamp=1)
        payload = [binance(1, BASE-2), binance(2, BASE-2)]
        with self.assertRaisesRegex(ValueError, 'bound exceeded'):
            watermark.accept('binance-spot', payload,
                             normalize_trades('binance-spot', 'BTCUSDT', payload, BASE))

    def test_access_forbidden_is_visible_and_cooldown_preserved(self):
        c = PublicCollector('bybit-spot')
        c._opener = Opener(HTTPError('url', 403, 'forbidden', {}, BytesIO()))
        status, rows = c.poll(BASE)
        self.assertEqual(rows, [])
        self.assertTrue(status['sourceAccessBlocked'])
        self.assertEqual(status['retryAtMs'], BASE + 600000)
        self.assertEqual(c.poll(BASE+1)[0]['status'], 'BACKOFF')

    def test_public_report_separates_venues_and_never_claims_complete_tape(self):
        class FakeCollector:
            def __init__(self, venue, symbol):
                self.venue = venue

            def poll(self):
                if self.venue == 'binance-spot':
                    return {'status': 'SAMPLED_PUBLIC_TRADES', 'duplicateTrades': 3}, []
                return {'status': 'HTTP_BACKOFF', 'httpStatus': 403,
                        'sourceAccessBlocked': True}, []
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'session'
            with patch('research.phase3.polybot_sdk.collector.PublicCollector', FakeCollector):
                report = collect(output, seconds=.01, interval=1)
            self.assertTrue(report['complete'])
            self.assertFalse(report['completeTradeTape'])
            self.assertFalse(report['sevenDayHoldoutQualified'])
            self.assertEqual(report['decision'], 'NO_GO')
            self.assertEqual(report['perVenue']['binance-spot']['duplicateTrades'], 3)
            self.assertEqual(report['perVenue']['bybit-spot']['errorPolls'], 1)
            self.assertTrue(report['perVenue']['bybit-spot']['sourceAccessBlocked'])
            self.assertEqual(decode((output / 'report.json').read_text()), report)
            raw = [decode(x) for x in (output / 'public.jsonl').read_text().splitlines()]
            self.assertEqual(len(raw), 2)


if __name__ == '__main__':
    unittest.main()
