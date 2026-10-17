"""Causal, independently reported CEX spot signal experiments from sealed PUBLIC tapes.

No trade orders, no buy/sell recommendations and no prediction of Polymarket
resolution. Delayed or blocked sources ABSTAIN rather than imputing values.
"""
import argparse
from collections import deque
from decimal import Decimal
from pathlib import Path
import re

from research.phase3.polybot_sdk.features import fingerprint
from research.phase3.polybot_sdk.model import decode, dumps, integer, number
from research.phase3.polybot_sdk.runtime import private_write

VENUES = ('binance-spot', 'bybit-spot')
MAX_EVENTS = 100000
MAX_BATCH = 1000


def parse_sample(row):
    """Return original exchange prints without inventing direction when absent."""
    venue, symbol = row.get('venue'), row.get('symbol')
    if venue not in VENUES or not isinstance(symbol, str) or not re.fullmatch(r'[A-Z0-9]{3,20}USDT', symbol):
        raise ValueError('Unknown venue or symbol')
    received = integer(row['receivedMs'])
    if not 0 < received <= integer(row['polledMs']) + 1000:
        raise ValueError('Noncausal receipt timestamp')
    payload = row['payload']
    if fingerprint(payload) != row.get('payloadSha256'):
        raise ValueError('Unverifiable raw exchange response')
    if venue == 'binance-spot':
        if not isinstance(payload, list):
            raise ValueError('Invalid Binance payload')
        records = payload
    else:
        if integer(payload['retCode']) != 0 or payload['result']['category'] != 'spot':
            raise ValueError('Invalid Bybit spot payload')
        records = payload['result']['list']
    if not isinstance(records, list) or len(records) > MAX_BATCH:
        raise ValueError('Oversized or invalid exchange sample')
    parsed = []
    seen = set()
    for rec in records:
        if venue == 'binance-spot':
            identity, price, size, timestamp = rec['a'], rec['p'], rec['q'], rec['T']
            flag = rec.get('m')
            aggressive_side = ('SELL' if flag else 'BUY') if type(flag) is bool else None
        else:
            if rec['symbol'] != symbol:
                raise ValueError('Bybit symbol mismatch')
            identity, price, size, timestamp = rec['execId'], rec['price'], rec['size'], rec['time']
            flag = rec.get('side')
            aggressive_side = flag if flag in ('Buy', 'Sell') else None
            aggressive_side = aggressive_side.upper() if aggressive_side else None
        trade_id = str(identity)
        source = integer(timestamp)
        px, qty = number(price), number(size)
        if (not trade_id or len(trade_id) > 160 or trade_id in seen or source <= 0
                or source > received or px <= 0 or qty <= 0):
            raise ValueError('Invalid trade identity, time, price or quantity')
        seen.add(trade_id)
        parsed.append({'id':trade_id, 'sourceMs':source, 'receivedMs':received,
                       'price':px, 'quantity':qty, 'side':aggressive_side})
    return venue, symbol, sorted(parsed, key=lambda x:(x['sourceMs'],x['id']))


class SignalState:
    def __init__(self, lookback=5, max_age_ms=2000, min_bps=5, min_imbalance='0.35'):
        if (type(lookback) is not int or not 3 <= lookback <= 200
                or type(max_age_ms) is not int or not 50 <= max_age_ms <= 60000):
            raise ValueError('Invalid lookback/freshness policy')
        self.lookback, self.max_age_ms = lookback, max_age_ms
        self.min_bps = number(min_bps)
        self.min_imbalance = number(min_imbalance)
        if not 0 < self.min_bps <= 10000 or not 0 < self.min_imbalance < 1:
            raise ValueError('Invalid research signal thresholds')
        self.rows = deque(maxlen=lookback)
        self.source_watermark = -1
        self.ids_at_watermark = set()
        self.last_receipt = -1

    def event(self, row):
        stamp = integer(row['polledMs'])
        if stamp < self.last_receipt:
            raise ValueError('Nonmonotonic poll receipt')
        self.last_receipt = stamp
        if row.get('status') != 'SAMPLED_PUBLIC_TRADES':
            self.rows.clear()  # Source gap means historical window cannot be silently bridged.
            return {'status':'ABSTAIN_SOURCE_GAP','atMs':stamp}
        venue, symbol, prints = parse_sample(row)
        for trade in prints:
            source, trade_id = trade['sourceMs'], trade['id']
            if source < self.source_watermark:
                continue
            if source > self.source_watermark:
                self.source_watermark = source
                self.ids_at_watermark.clear()
            if trade_id in self.ids_at_watermark:
                continue
            if len(self.ids_at_watermark) >= 16384:
                raise ValueError('Unbounded same-millisecond trade IDs')
            self.ids_at_watermark.add(trade_id)
            self.rows.append(trade)
        if not self.rows or stamp - self.rows[-1]['sourceMs'] > self.max_age_ms:
            self.rows.clear()
            return {'status':'ABSTAIN_STALE_SOURCE','atMs':stamp}
        if len(self.rows) < self.lookback:
            return {'status':'ABSTAIN_INSUFFICIENT_PRINTS','atMs':stamp}
        if self.rows[-1]['sourceMs'] - self.rows[0]['sourceMs'] > self.max_age_ms:
            return {'status':'ABSTAIN_WINDOW_GAP','atMs':stamp}
        first, last = self.rows[0], self.rows[-1]
        momentum_bps = (last['price'] / first['price'] - 1) * 10000
        direction = ('UP' if momentum_bps >= self.min_bps else
                     'DOWN' if momentum_bps <= -self.min_bps else 'NEUTRAL')
        sides_known = all(p['side'] in ('BUY','SELL') for p in self.rows)
        if sides_known:
            signed = sum((p['quantity'] if p['side']=='BUY' else -p['quantity'] for p in self.rows), Decimal(0))
            total = sum((p['quantity'] for p in self.rows), Decimal(0))
            imbalance = signed / total
            flow = ('BUY' if imbalance >= self.min_imbalance else
                    'SELL' if imbalance <= -self.min_imbalance else 'NEUTRAL')
        else:
            imbalance, flow = None, 'ABSTAIN_MISSING_SIDE'
        return {'status':'RESEARCH_SIGNALS_UNQUALIFIED','atMs':stamp,
                'momentumDirection':direction, 'momentumBps':str(momentum_bps),
                'aggressiveFlow':flow, 'volumeImbalance':str(imbalance) if imbalance is not None else None,
                'sourceEndMs':last['sourceMs'], 'windowPrints':len(self.rows),
                'predictionQualified':False, 'fillEvidence':False,
                'executionEnabled':False}


def run_archives(paths, lookback=5, max_age_ms=2000):
    if not paths or len(set(str(Path(p).resolve()) for p in paths)) != len(paths):
        raise ValueError('Provide distinct PUBLIC tapes')
    states, counts, samples = {}, {}, 0
    for path in paths:
        p = Path(path)
        if p.name != 'public.jsonl':
            raise ValueError('Expected sealed PUBLIC collector public.jsonl file')
        from research.phase4.audit import inspect_session
        inspect_session(p.parent)  # Re-check SHA256, identity, venue accounting.
        with p.open(encoding='utf-8') as handle:
            for line in handle:
                samples += 1
                if samples > MAX_EVENTS:
                    raise ValueError('Signal replay exceeds event bound')
                row = decode(line)
                key = row['venue'], row['symbol']
                if key not in states:
                    states[key] = SignalState(lookback, max_age_ms)
                    counts[str(key)] = {}
                signal = states[key].event(row)
                bucket = counts[str(key)]
                label = signal['status']
                if label == 'RESEARCH_SIGNALS_UNQUALIFIED':
                    label += ':' + signal['momentumDirection'] + '/' + signal['aggressiveFlow']
                bucket[label] = bucket.get(label, 0) + 1
    return {'schema':1, 'scope':'PUBLIC_SPOT_SIGNAL_ABLATION_NOT_A_STRATEGY',
            'archiveCount':len(paths), 'publicPolls':samples,'perVenueSymbol':counts,
            'predictionQualified':False, 'venueFillEvidence':False,
            'strategyQualified':False, 'decision':'NO_GO', 'liveAllowed':False}


def main():
    cli=argparse.ArgumentParser(description='Read-only CEX spot signal diagnostics')
    cli.add_argument('tapes',nargs='+')
    cli.add_argument('--lookback',type=int,default=5)
    cli.add_argument('--max-age-ms',type=int,default=2000)
    cli.add_argument('--output',required=True)
    opts=cli.parse_args()
    report=run_archives(opts.tapes,opts.lookback,opts.max_age_ms)
    private_write(opts.output,report)
    print(dumps(report))


if __name__=='__main__':
    main()
