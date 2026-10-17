"""Censored binary outcomes, purged market holdout, and an unqualified logistic baseline."""
from dataclasses import dataclass
import hashlib
import math
from .model import dumps, integer

FEATURES = ('spread', 'queue_ahead', 'inventory_imbalance', 'source_age_ms', 'seconds_to_expiry', 'volatility')
DOMAINS = ((0, 1), (0, 1e12), (-1, 1), (0, 86400000), (0, 315360000), (0, 1))
TARGETS = ('fill', 'second_leg', 'adverse_selection')


@dataclass(frozen=True)
class Example:
    order: str
    market: str
    submitted: int
    ended: int
    features: tuple
    label: int
    provenance: str
    fill_delay_ms: object
    group: object


def vector(values):
    if set(values) != set(FEATURES):
        raise ValueError('Unknown/missing model feature')
    result = tuple(float(values[key]) for key in FEATURES)
    if any(not math.isfinite(v) or not low <= v <= high for v, (low, high) in zip(result, DOMAINS)):
        raise ValueError('Model feature outside its domain')
    return result


def example(row, target='fill', horizon_ms=5000):
    if target not in TARGETS or not 1 <= horizon_ms <= 600000:
        raise ValueError('Unknown target or horizon')
    for key in ('orderId', 'marketId'):
        if not isinstance(row[key], str) or not row[key].strip():
            raise ValueError('Missing label identity')
    start, observed, end = (integer(row[k]) for k in ('submittedMs', 'featureObservedMs', 'labelEndMs'))
    if not 0 <= observed <= start <= end or row['provenance'] not in ('VENUE_EXECUTION', 'PAPER_MODEL'):
        raise ValueError('Noncausal labels or unrecognized provenance')
    fill = None if row.get('fillMs') is None else integer(row['fillMs'])
    cancel = None if row.get('cancelMs') is None else integer(row['cancelMs'])
    paired = None if row.get('secondLegMs') is None else integer(row['secondLegMs'])
    if any(x is not None and not start <= x <= end for x in (fill, cancel, paired)):
        raise ValueError('Outcome outside observation window')
    if fill is not None and cancel is not None and fill >= cancel:
        raise ValueError('A cancel wins ties with a fill')
    if paired is not None and (fill is None or paired < fill):
        raise ValueError('Second leg requires an earlier first fill')
    group = row.get('groupId')
    if group is not None and (not isinstance(group, str) or not group.strip()):
        raise ValueError('Invalid intent group identity')
    x = vector(row['features'])
    if target == 'adverse_selection':
        markout = row.get('markout')
        at = row.get('markoutObservedMs')
        if fill is None or markout is None or at is None:
            return None
        at, value = integer(at), float(markout)
        if not math.isfinite(value) or not fill + horizon_ms <= at <= end:
            raise ValueError('Markout lacks a complete post-fill horizon')
        label = int(value < 0)
    else:
        event = fill if target == 'fill' else paired
        if event is not None and event <= start + horizon_ms:
            label = 1
        elif end < start + horizon_ms or (cancel is not None and cancel < start + horizon_ms):
            return None  # An early cancellation is censored, never a failed fill.
        else:
            label = 0
    return Example(row['orderId'], row['marketId'], start, end, x, label, row['provenance'],
                   None if fill is None else fill - start, group)


def sigmoid(value):
    return 1 / (1 + math.exp(-max(-40, min(40, value))))


def train(rows, holdout_start_ms, target='fill', horizon_ms=5000, min_train=1000, min_holdout=200, min_class=20):
    if min(min_train, min_holdout, min_class) < 1:
        raise ValueError('Minimum evidence counts must be positive')
    raw, examples, seen = [], [], set()
    for row in rows:
        if len(raw) >= 100000:
            raise ValueError('Model dataset exceeds 100000 rows')
        raw.append(row)
        identity = row['orderId'], row['marketId']
        if identity in seen:
            raise ValueError('Duplicate order label')
        seen.add(identity)
        e = example(row, target, horizon_ms)
        if e is not None:
            examples.append(e)
    parents, linked = {}, {}
    def root(market):
        parents.setdefault(market, market)
        while parents[market] != market:
            parents[market] = parents[parents[market]]
            market = parents[market]
        return market
    for e in examples:
        root(e.market)
        if e.group is not None:
            if e.group in linked:
                parents[root(e.market)] = root(linked[e.group])
            else:
                linked[e.group] = e.market
    markets = {}
    for e in examples:
        markets.setdefault(root(e.market), []).append(e)
    cut = integer(holdout_start_ms)
    training, holdout, purged = [], [], 0
    for group in markets.values():
        if max(e.ended for e in group) < cut:
            training.extend(group)
        elif min(e.submitted for e in group) >= cut:
            holdout.extend(group)
        else:
            purged += len(group)
    result = {'status': 'INSUFFICIENT_EVIDENCE', 'target': target, 'horizonMs': horizon_ms,
              'features': list(FEATURES), 'trainingRows': len(training), 'holdoutRows': len(holdout),
              'purgedRows': purged, 'censoredRows': len(raw) - len(examples),
              'datasetSha256': hashlib.sha256(dumps(raw).encode()).hexdigest(),
              'holdoutStartMs': cut, 'model': None, 'modelQualified': False, 'preRegistrationVerified': False,
              'researchOnly': True, 'executionEnabled': False, 'liveAllowed': False}
    classes_ok = lambda data: min(sum(e.label == v for e in data) for v in (0, 1)) >= min_class
    if (len(training) < min_train or len(holdout) < min_holdout or not classes_ok(training)
            or not classes_ok(holdout) or len({e.provenance for e in examples}) != 1):
        return result
    means = [sum(e.features[j] for e in training) / len(training) for j in range(len(FEATURES))]
    scales = [(sum((e.features[j] - means[j]) ** 2 for e in training) / len(training)) ** .5 or 1 for j in range(len(FEATURES))]
    standardize = lambda x: [max(-10, min(10, (v - m) / s)) for v, m, s in zip(x, means, scales)]
    xs, weights, bias = [standardize(e.features) for e in training], [0.] * len(FEATURES), 0.
    for _ in range(150):
        gradients, intercept = [0.] * len(FEATURES), 0.
        for x, e in zip(xs, training):
            error = sigmoid(bias + sum(w * v for w, v in zip(weights, x))) - e.label
            intercept += error
            for j in range(len(FEATURES)):
                gradients[j] += error * x[j]
        bias -= .05 * intercept / len(training)
        weights = [w - .05 * (g / len(training) + .001 * w) for w, g in zip(weights, gradients)]
    probabilities = [sigmoid(bias + sum(w * v for w, v in zip(weights, standardize(e.features)))) for e in holdout]
    base_rate = sum(e.label for e in training) / len(training)
    bins = []
    for bucket in range(10):
        pairs = [(p, e.label) for p, e in zip(probabilities, holdout) if min(9, int(p * 10)) == bucket]
        bins.append({'bin': bucket, 'count': len(pairs), 'meanPredicted': sum(p for p, _ in pairs) / len(pairs) if pairs else None,
                     'observedRate': sum(y for _, y in pairs) / len(pairs) if pairs else None})
    delays = sorted(e.fill_delay_ms for e in training if e.fill_delay_ms is not None)
    result.update({'status': 'RESEARCH_MODEL_UNQUALIFIED', 'provenance': examples[0].provenance,
                   'model': {'means': means, 'scales': scales, 'weights': weights, 'bias': bias},
                   'holdoutBrier': sum((p - e.label) ** 2 for p, e in zip(probabilities, holdout)) / len(holdout),
                   'baselineBrier': sum((base_rate - e.label) ** 2 for e in holdout) / len(holdout), 'calibration': bins,
                   'trainingFillDelayP50Ms': delays[len(delays) // 2] if delays else None})
    return result


def predict(artifact, values):
    if artifact.get('status') != 'RESEARCH_MODEL_UNQUALIFIED' or not artifact.get('model'):
        return {'probability': None, 'qualified': False, 'executionEnabled': False}
    if artifact.get('features') != list(FEATURES) or artifact.get('modelQualified') is not False:
        raise ValueError('Unsupported model contract')
    model, x = artifact['model'], vector(values)
    if any(len(model[k]) != len(FEATURES) for k in ('weights', 'means', 'scales')):
        raise ValueError('Model dimension mismatch')
    all_values = [float(model['bias'])] + [float(v) for k in ('weights', 'means', 'scales') for v in model[k]]
    if any(not math.isfinite(v) for v in all_values) or any(float(s) <= 0 for s in model['scales']):
        raise ValueError('Invalid model parameters')
    z = [max(-10, min(10, (v - float(m)) / float(s))) for v, m, s in zip(x, model['means'], model['scales'])]
    return {'probability': sigmoid(float(model['bias']) + sum(float(w) * v for w, v in zip(model['weights'], z))),
            'qualified': False, 'executionEnabled': False}
