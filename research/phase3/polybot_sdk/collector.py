"""Bounded PUBLIC spot trade sampling. This measures polling, not latency arbitrage."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import math
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener
from .client import NoRedirect
from .features import normalize_trades
from .model import decode, dumps
from .runtime import private_write


def retry_delay(header, now=None):
    try:
        delay = float(header)
        if math.isfinite(delay) and delay >= 0:
            return delay
    except (TypeError, ValueError):
        pass
    try:
        dt = parsedate_to_datetime(header)
        if dt.tzinfo is None:
            return 60
        current = datetime.now(timezone.utc).timestamp() if now is None else now
        return max(0, dt.timestamp() - current)
    except (TypeError, ValueError, OverflowError):
        return 60


class PublicCollector:
    def __init__(self, venue, symbol='BTCUSDT'):
        if venue not in ('binance-spot', 'bybit-spot') or not re.fullmatch('[A-Z0-9]{3,20}USDT', symbol):
            raise ValueError('Unsupported public market')
        self.venue, self.symbol = venue, symbol
        self._opener = build_opener(NoRedirect())
        self.not_before, self.failures = 0, 0
        root = ('https://data-api.binance.vision/api/v3/aggTrades?symbol=' + symbol + '&limit=100'
                if venue == 'binance-spot' else 'https://api.bybit.com/v5/market/recent-trade?category=spot&symbol=' + symbol + '&limit=60')
        self._url = root
        self._last_source = -1

    def poll(self, now_ms=None):
        now = int(time.time() * 1000) if now_ms is None else now_ms
        if now < self.not_before:
            return {'status': 'BACKOFF', 'retryAtMs': self.not_before}, []
        try:
            with self._opener.open(Request(self._url, headers={'User-Agent': 'khaledpoly-paper-research/0.2'}, method='GET'), timeout=5) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
            received = int(time.time() * 1000) if now_ms is None else now_ms
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError('Public response exceeds bound')
            payload = decode(raw)
            if self.venue == 'bybit-spot' and payload.get('retCode') == 10006:
                self.not_before = received + 60000
                return {'status': 'RATE_LIMIT', 'retryAtMs': self.not_before}, []
            rows = normalize_trades(self.venue, self.symbol, payload, received)
            rows = [row for row in rows if row.source_ms > self._last_source]
            if rows:
                self._last_source = max(row.source_ms for row in rows)
            self.failures = 0
            return {'status': 'SAMPLED_PUBLIC_TRADES', 'receivedMs': received, 'payload': payload,
                    'payloadSha256': hashlib.sha256(dumps(payload).encode()).hexdigest(),
                    'coverage': 'SAMPLED_NOT_COMPLETE_TRADE_TAPE'}, rows
        except HTTPError as exc:
            self.failures += 1
            if exc.code in (418, 429, 403):
                delay = max(600 if exc.code == 403 else 60, retry_delay(exc.headers.get('Retry-After')))
            elif exc.code >= 500:
                delay = min(60, 2 ** min(self.failures, 6))
            else:
                raise
            self.not_before = now + int(delay * 1000)
            return {'status': 'HTTP_BACKOFF', 'httpStatus': exc.code, 'retryAtMs': self.not_before}, []
        except (URLError, TimeoutError, OSError):
            self.failures += 1
            self.not_before = now + min(60000, 1000 * 2 ** min(self.failures, 6))
            return {'status': 'NETWORK_GAP', 'retryAtMs': self.not_before}, []


def collect(directory, seconds=60, interval=5, symbol='BTCUSDT'):
    if not math.isfinite(seconds) or not 0 < seconds <= 86400 or not math.isfinite(interval) or not 1 <= interval <= 60:
        raise ValueError('Invalid public collector duration/interval')
    path = Path(directory)
    path.mkdir(parents=True, mode=0o700, exist_ok=False)
    private_write(path / 'manifest.json', {'mode': 'PUBLIC_RECORD_ONLY', 'symbol': symbol,
                  'seconds': str(seconds), 'interval': str(interval), 'coverage': 'SAMPLED', 'liveAllowed': False})
    collectors = [PublicCollector(v, symbol) for v in ('binance-spot', 'bybit-spot')]
    deadline, rows, errors, complete = time.monotonic() + seconds, 0, 0, False
    try:
        with open(path / 'features.jsonl', 'x') as features, open(path / 'public.jsonl', 'x') as raw:
            for p in (path / 'features.jsonl', path / 'public.jsonl'):
                os.chmod(p, 0o600)
            while time.monotonic() < deadline:
                for client in collectors:
                    status, observations = client.poll()
                    status.update({'venue': client.venue, 'symbol': symbol})
                    raw.write(dumps(status) + '\n')
                    errors += status['status'] not in ('SAMPLED_PUBLIC_TRADES', 'BACKOFF')
                    for observation in observations:
                        features.write(dumps(observation.record()) + '\n')
                        rows += 1
                for output in (features, raw):
                    output.flush()
                    os.fsync(output.fileno())
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    time.sleep(min(interval, remaining))
        complete = True
    finally:
        report = {'complete': complete, 'featureRows': rows, 'errors': errors, 'coverage': 'SAMPLED',
                  'decision': 'NO_GO', 'liveAllowed': False}
        private_write(path / 'report.json', report)
    return report
