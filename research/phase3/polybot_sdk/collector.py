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
from .model import decode, dumps, integer
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



class TradeWatermark:
    """Accept equal-millisecond NEW trade IDs without replaying stale samples.

    A watermark advances only after payload validation. Remember IDs at its
    current timestamp; older timestamps are deliberately not backfilled by
    sampled polling. Exceeding the bound fails closed rather than duplicating.
    """

    def __init__(self, max_ids_at_timestamp=16384):
        if not 1 <= max_ids_at_timestamp <= 65536:
            raise ValueError('Invalid trade watermark bound')
        self.max_ids_at_timestamp = max_ids_at_timestamp
        self.source_ms = -1
        self.ids_at_timestamp = set()

    def accept(self, venue, payload, observations):
        if venue == 'binance-spot':
            records, identity, clock = payload, 'a', 'T'
        elif venue == 'bybit-spot':
            records, identity, clock = payload['result']['list'], 'execId', 'time'
        else:
            raise ValueError('Unsupported trade venue')
        ordered = sorted(records, key=lambda row: integer(row[clock]))
        if len(ordered) != len(observations):
            raise ValueError('Trade identity/observation count mismatch')
        fresh, duplicates, older = [], 0, 0
        for record, observation in zip(ordered, observations):
            source_ms = integer(record[clock])
            trade_id = str(record[identity])
            if source_ms != observation.source_ms or not trade_id:
                raise ValueError('Trade identity/observation mismatch')
            if source_ms < self.source_ms:
                older += 1
                continue
            if source_ms > self.source_ms:
                self.source_ms = source_ms
                self.ids_at_timestamp.clear()
            if trade_id in self.ids_at_timestamp:
                duplicates += 1
                continue
            if len(self.ids_at_timestamp) >= self.max_ids_at_timestamp:
                raise ValueError('Trade ID watermark bound exceeded')
            self.ids_at_timestamp.add(trade_id)
            fresh.append(observation)
        return fresh, duplicates, older


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
        self._watermark = TradeWatermark()

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
            validated = normalize_trades(self.venue, self.symbol, payload, received)
            rows, duplicates, older = self._watermark.accept(self.venue, payload, validated)
            self.failures = 0
            return {'status': 'SAMPLED_PUBLIC_TRADES', 'receivedMs': received, 'payload': payload,
                    'payloadSha256': hashlib.sha256(dumps(payload).encode()).hexdigest(),
                    'uniqueTrades': len(rows), 'duplicateTrades': duplicates, 'olderTrades': older,
                    'lastSourceMs': self._watermark.source_ms,
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
            return {'status': 'HTTP_BACKOFF', 'httpStatus': exc.code, 'retryAtMs': self.not_before,
                    'sourceAccessBlocked': exc.code == 403}, []
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
    per_venue = {v: {'sampledPolls': 0, 'backoffPolls': 0, 'errorPolls': 0,
                     'featureRows': 0, 'duplicateTrades': 0, 'olderTrades': 0,
                     'sourceAccessBlocked': False} for v in ('binance-spot', 'bybit-spot')}
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
                    metric = per_venue[client.venue]
                    if status['status'] == 'SAMPLED_PUBLIC_TRADES':
                        metric['sampledPolls'] += 1
                    elif status['status'] == 'BACKOFF':
                        metric['backoffPolls'] += 1
                    else:
                        metric['errorPolls'] += 1
                    metric['sourceAccessBlocked'] |= status.get('sourceAccessBlocked', False)
                    metric['duplicateTrades'] += status.get('duplicateTrades', 0)
                    metric['olderTrades'] += status.get('olderTrades', 0)
                    metric['featureRows'] += len(observations)
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
                  'perVenue': per_venue, 'completeTradeTape': False, 'sevenDayHoldoutQualified': False,
                  'decision': 'NO_GO', 'liveAllowed': False}
        private_write(path / 'report.json', report)
    return report
