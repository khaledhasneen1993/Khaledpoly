"""Availability-time joins. A forecast is an external claim, never a venue fact."""
from collections import deque
from dataclasses import dataclass
import hashlib
import re
from .model import number, integer, dumps


def fingerprint(payload):
    return hashlib.sha256(dumps(payload).encode()).hexdigest()


@dataclass(frozen=True)
class Observation:
    venue: str
    symbol: str
    kind: str
    value: object
    source_ms: int
    received_ms: int
    evidence_sha256: str

    def __post_init__(self):
        if (any(not isinstance(s, str) or not s.strip() for s in (self.venue, self.symbol, self.kind))
                or not 0 <= integer(self.source_ms) <= integer(self.received_ms)
                or not re.fullmatch('[0-9a-f]{64}', self.evidence_sha256)):
            raise ValueError('Invalid causal feature evidence')
        object.__setattr__(self, 'source_ms', integer(self.source_ms))
        object.__setattr__(self, 'received_ms', integer(self.received_ms))
        object.__setattr__(self, 'value', number(self.value))

    def record(self):
        return {'venue': self.venue, 'symbol': self.symbol, 'kind': self.kind, 'value': number(self.value),
                'sourceMs': integer(self.source_ms), 'receivedMs': integer(self.received_ms),
                'evidenceSha256': self.evidence_sha256}

    @classmethod
    def parse(cls, row):
        return cls(row['venue'], row['symbol'], row['kind'], number(row['value']),
                   integer(row['sourceMs']), integer(row['receivedMs']), row['evidenceSha256'])


class FeatureStore:
    def __init__(self, max_keys=4096, history=256):
        if not 1 <= max_keys <= 4096 or not 2 <= history <= 4096:
            raise ValueError('Invalid feature bounds')
        self._keys, self._history, self._rows, self._clock = max_keys, history, {}, -1
        self.regressions = 0

    def add(self, observation):
        if observation.received_ms < self._clock:
            raise ValueError('Feature arrival clock regression')
        self._clock = observation.received_ms
        key = observation.venue, observation.symbol, observation.kind
        rows = self._rows.get(key)
        if rows and observation.source_ms <= rows[-1].source_ms:
            self.regressions += 1
            return  # Replayed old responses cannot refresh feature freshness.
        if rows is None:
            if len(self._rows) >= self._keys:
                raise ValueError('Feature key bound exceeded')
            rows = self._rows[key] = deque(maxlen=self._history)
        rows.append(observation)

    def available(self, at, ttl=2000):
        if not 0 < ttl <= 60000:
            raise ValueError('Invalid feature TTL')
        result = []
        for key in sorted(self._rows):
            rows = [x for x in self._rows[key] if x.source_ms <= at and x.received_ms <= at and at - x.source_ms < ttl]
            if rows:
                result.append(rows[-1])
        return result

    def latest(self, venue, symbol, kind, at, ttl=2000):
        return next((x for x in self.available(at, ttl) if (x.venue, x.symbol, x.kind) == (venue, symbol, kind)), None)

    def divergence(self, symbol, at):
        prices = [self.latest(v, symbol, 'trade_price', at) for v in ('binance-spot', 'bybit-spot')]
        if any(p is None or number(p.value) <= 0 for p in prices):
            return {'status': 'INSUFFICIENT_FRESH_DATA', 'basisBps': None, 'arbitrageProven': False}
        return {'status': 'RESEARCH_SIGNAL', 'basisBps': (number(prices[0].value) / number(prices[1].value) - 1) * 10000,
                'arbitrageProven': False, 'polymarketProbability': None}


def normalize_trades(venue, symbol, payload, received_ms):
    if not re.fullmatch('[A-Z0-9]{3,20}USDT', symbol):
        raise ValueError('Invalid research symbol')
    if venue == 'binance-spot':
        if not isinstance(payload, list):
            raise ValueError('Invalid Binance aggregate trades')
        rows = [(str(x['a']), x['p'], x['q'], x['T']) for x in payload]
    elif venue == 'bybit-spot':
        if integer(payload['retCode']) != 0:
            raise ValueError('Bybit response is not successful')
        data = payload['result']
        if data['category'] != 'spot' or any(x['symbol'] != symbol for x in data['list']):
            raise ValueError('Bybit symbol/category mismatch')
        rows = [(str(x['execId']), x['price'], x['size'], x['time']) for x in data['list']]
    else:
        raise ValueError('Unsupported public venue')
    if len(rows) > 1000:
        raise ValueError('Public trade batch exceeds bound')
    evidence, seen, result = fingerprint(payload), set(), []
    for trade_id, price, size, timestamp in sorted(rows, key=lambda r: integer(r[3])):
        if not trade_id or trade_id in seen or number(price) <= 0 or number(size) <= 0:
            raise ValueError('Invalid or duplicate public trade')
        seen.add(trade_id)
        result.append(Observation(venue, symbol, 'trade_price', number(price), integer(timestamp), integer(received_ms), evidence))
    return result
