"""Historical joint-price risk. Missing intervals are not interpolated."""
from decimal import Decimal as D, ROUND_CEILING
from .model import number, integer


def historical_risk(snapshot, panel, interval_ms=1000, min_samples=100, confidence=D('.99')):
    confidence = number(confidence)
    if not 0 < confidence < 1 or not 1 <= interval_ms <= 60000 or min_samples < 2:
        raise ValueError('Invalid risk sampling contract')
    holdings = {t: number(h['shares']) for t, h in snapshot['account']['holdings'].items() if number(h['shares']) > 0}
    worst = sum((number(h['basis']) for h in snapshot['account']['holdings'].values()), D(0))
    worst += sum((number(o['remaining']) * number(o['price']) for o in snapshot['account']['orders'].values() if o['buy']), D(0))
    result = {'status': 'INSUFFICIENT_JOINT_HISTORY', 'var': None, 'expectedShortfall': None, 'correlations': None,
              'samples': 0, 'confidence': confidence, 'intervalMs': interval_ms, 'worstCaseAcquisitionExposure': worst,
              'futureLossBound': False, 'executionEnabled': False}
    if not holdings:
        result.update(status='NO_FILLED_POSITIONS', var=D(0), expectedShortfall=D(0), correlations={})
        return result
    rows, previous = [], -1
    for at, prices in panel:
        at = integer(at)
        if len(rows) >= 10001 or not previous < at <= int(snapshot['generatedMs']):
            raise ValueError('Risk history is unbounded or noncausal')
        previous = at
        values = {t: number(p) for t, p in prices.items()}
        if any(not 0 < p < 1 for p in values.values()):
            raise ValueError('Invalid historical price')
        rows.append((at, values))
    changes, losses = {t: [] for t in holdings}, []
    for left, right in zip(rows, rows[1:]):
        if right[0] - left[0] != interval_ms or any(t not in left[1] or t not in right[1] for t in holdings):
            continue
        increments = {t: right[1][t] - left[1][t] for t in holdings}
        for t, delta in increments.items():
            changes[t].append(delta)
        losses.append(-sum((holdings[t] * delta for t, delta in increments.items()), D(0)))
    result['samples'] = len(losses)
    if len(losses) < min_samples or not rows or int(snapshot['generatedMs']) - rows[-1][0] > 2000:
        return result
    losses.sort()
    index = max(0, int((confidence * len(losses)).to_integral_value(rounding=ROUND_CEILING)) - 1)
    var = losses[index]
    tail = losses[index:]
    correlations = {}
    for first, xs in changes.items():
        correlations[first] = {}
        mx = sum(xs) / len(xs)
        for second, ys in changes.items():
            my = sum(ys) / len(ys)
            xx = sum((x - mx) ** 2 for x in xs)
            yy = sum((y - my) ** 2 for y in ys)
            denominator = (xx * yy).sqrt()
            correlations[first][second] = (sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denominator if denominator else None)
    result.update(status='HISTORICAL_ESTIMATE', var=max(D(0), var),
                  expectedShortfall=max(D(0), sum(tail) / len(tail)), correlations=correlations)
    return result
