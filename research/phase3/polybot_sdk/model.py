"""Strict, causal observations of the existing PAPER account. All money uses Decimal."""
from decimal import Decimal, InvalidOperation
import json
import time


def number(value):
    if isinstance(value, bool) or value is None:
        raise ValueError('Expected a finite decimal')
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('Invalid decimal') from exc
    if not result.is_finite():
        raise ValueError('Nonfinite decimal')
    return result


def integer(value):
    n = number(value)
    if n != n.to_integral_value():
        raise ValueError('Expected integer')
    return int(n)


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Nonfinite JSON number')
    return json.loads(raw, parse_float=Decimal, object_pairs_hook=pairs,
                      parse_constant=invalid)


def dumps(value):
    def encode(item):
        if isinstance(item, Decimal):
            return str(item)
        raise TypeError(type(item).__name__)
    return json.dumps(value, default=encode, sort_keys=True, separators=(',', ':'),
                      allow_nan=False)


def validate(data, now_ms=None):
    """Return a detached observation or fail closed. Explicit time is for replay only."""
    d = decode(dumps(data))
    if (type(d.get('schema')) is not int or d['schema'] != 1
            or d.get('mode') != 'PAPER' or d.get('researchOnly') is not True
            or d.get('executionEnabled') is not False or d.get('liveAllowed') is not False
            or d.get('truncated') is not False):
        raise ValueError('Unsupported or unsafe snapshot')
    now = int(time.time() * 1000) if now_ms is None else integer(now_ms)
    generated, source = integer(d['generatedMs']), integer(d['inputMs'])
    age, meta_age = integer(d['maxBookAgeMs']), integer(d['metadataMaxAgeMs'])
    if not (0 < age <= 2000 and 0 < meta_age <= 60000 and 0 <= source <= generated <= now + 1000
            and now - generated <= age and generated - source <= age):
        raise ValueError('Stale or noncausal snapshot')
    if not isinstance(d['sessionId'], str) or not d['sessionId'] or integer(d['sequence']) < 1:
        raise ValueError('Missing observation identity')
    a = d['account']
    if not isinstance(a['id'], str) or not a['id'] or type(a['halted']) is not bool:
        raise ValueError('Invalid account')
    cash, available = number(a['cash']), number(a['availableCash'])
    if not 0 <= available <= cash or integer(a['pendingTakers']) < 0:
        raise ValueError('Invalid account balance')
    for h in a['holdings'].values():
        if number(h['shares']) < 0 or number(h['basis']) < 0:
            raise ValueError('Negative holding')
    reserved_cash, reserved_sell = Decimal(0), {}
    for o in a['orders'].values():
        remaining, price = number(o['remaining']), number(o['price'])
        if remaining < 0 or not 0 < price < 1 or type(o['buy']) is not bool:
            raise ValueError('Invalid reservation')
        if o['buy']:
            reserved_cash += price * remaining
        else:
            reserved_sell[o['token']] = reserved_sell.get(o['token'], Decimal(0)) + remaining
    if cash - reserved_cash != available:
        raise ValueError('Cash reservation mismatch')
    for token, quantity in reserved_sell.items():
        if quantity > number(a['holdings'].get(token, {}).get('shares', 0)):
            raise ValueError('Uncovered sell reservation')
    conditions, tokens = set(), set()
    if len(d['markets']) > 256 or len(d['books']) > 512:
        raise ValueError('Observation exceeds bounds')
    for m in d['markets']:
        if (not m['condition'] or m['condition'] in conditions or m['first'] == m['second']
                or any(not t or t in tokens for t in (m['first'], m['second']))):
            raise ValueError('Ambiguous market identity')
        conditions.add(m['condition'])
        tokens.update((m['first'], m['second']))
        if (not 0 < number(m['tick']) < 1 or number(m['minSize']) <= 0
                or not 0 <= number(m['feeRate']) <= 1 or not 0 <= integer(m['feeExponent']) <= 8
                or not 0 <= integer(m['startMs']) < integer(m['endMs'])
                or not 0 <= integer(m['observedMs']) <= generated
                or type(m['accepting']) is not bool or not m['evidence']):
            raise ValueError('Invalid market metadata')
    for book in d['books'].values():
        if not 0 <= integer(book['sourceMs']) <= integer(book['receivedMs']) <= generated:
            raise ValueError('Noncausal book')
        if type(book['depthTruncated']) is not bool:
            raise ValueError('Missing depth status')
        for side in ('bids', 'asks'):
            levels = book[side]
            if len(levels) > 50:
                raise ValueError('Depth exceeds bound')
            prices = [number(x['price']) for x in levels]
            if (any(not 0 < p < 1 for p in prices)
                    or any(number(x['size']) <= 0 for x in levels)
                    or len(set(prices)) != len(prices)
                    or prices != sorted(prices, reverse=side == 'bids')):
                raise ValueError('Invalid book levels')
        if book['bids'] and book['asks'] and number(book['bids'][0]['price']) >= number(book['asks'][0]['price']):
            raise ValueError('Crossed book')
    return d
