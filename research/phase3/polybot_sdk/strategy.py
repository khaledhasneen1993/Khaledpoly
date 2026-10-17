"""Maker proposals only; prices and budgets are hypothetical, never orders or fills."""
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING
from .model import number


def propose(snapshot, per_order=Decimal('25'), per_group=Decimal('25'), gross_limit=Decimal('100'), groups=None):
    per_order, per_group, gross_limit = map(number, (per_order, per_group, gross_limit))
    if min(per_order, per_group, gross_limit) <= 0:
        raise ValueError('Risk limits must be positive')
    groups = {} if groups is None else groups
    if not isinstance(groups, dict):
        raise ValueError('Correlation groups must be an object')
    if any(not isinstance(k, str) or not isinstance(v, str) or not v for k, v in groups.items()):
        raise ValueError('Invalid correlation group mapping')
    a, now = snapshot['account'], int(snapshot['generatedMs'])
    if a['halted'] or int(a['pendingTakers']) > 0:
        return {'admitted': [], 'rejected': [], 'reason': 'ACCOUNT_BLOCKED'}
    token_group = {t: groups.get(m['condition'], m['condition']) for m in snapshot['markets'] for t in (m['first'], m['second'])}
    group_exposure, exposure = {}, Decimal(0)
    def add(token, amount):
        group = token_group.get(token, 'UNCLASSIFIED')
        group_exposure[group] = group_exposure.get(group, Decimal(0)) + amount
    for token, holding in a['holdings'].items():
        basis = number(holding['basis'])
        exposure += basis
        add(token, basis)
    reserved_sell = {}
    for order in a['orders'].values():
        amount = number(order['remaining'])
        if order['buy']:
            cost = number(order['price']) * amount
            exposure += cost
            add(order['token'], cost)
        else:
            reserved_sell[order['token']] = reserved_sell.get(order['token'], Decimal(0)) + amount
    cash, admitted, rejected = number(a['availableCash']), [], []
    # Fixed market and token order makes a given observation reproducible.
    for m in sorted(snapshot['markets'], key=lambda m: m['condition']):
        if (not m['accepting'] or not int(m['startMs']) <= now < int(m['endMs'])
                or now - int(m['observedMs']) > int(snapshot['metadataMaxAgeMs'])):
            continue
        group = groups.get(m['condition'], m['condition'])
        for token in (m['first'], m['second']):
            book = snapshot['books'].get(token)
            if (not book or book['depthTruncated'] or not book['bids'] or not book['asks']
                    or now - int(book['sourceMs']) > int(snapshot['maxBookAgeMs'])):
                continue
            if any(o['token'] == token and number(o['remaining']) > 0 for o in a['orders'].values()):
                rejected.append({'token': token, 'reason': 'EXISTING_ORDER'})
                continue
            bid, ask = number(book['bids'][0]['price']), number(book['asks'][0]['price'])
            tick, minimum = number(m['tick']), number(m['minSize'])
            owned = number(a['holdings'].get(token, {}).get('shares', 0))
            fair = (bid + ask) / 2 - min(Decimal('.1'), owned * Decimal('.001'))
            half = max(tick, (ask - bid) / 2 - tick)
            prices = (min(bid + tick, ((fair - half) / tick).to_integral_value(rounding=ROUND_FLOOR) * tick),
                      max(bid + tick, ((fair + half) / tick).to_integral_value(rounding=ROUND_CEILING) * tick))
            for buy, price in zip((True, False), prices):
                size = min(Decimal(5), number(book['bids' if buy else 'asks'][0]['size']) * Decimal('.1'))
                if not buy:
                    size = min(size, owned - reserved_sell.get(token, Decimal(0)))
                if (int(book['sourceMs']) + int(snapshot['maxBookAgeMs']) <= now
                        or price % tick != 0):
                    continue
                if size < minimum or not 0 < price < 1 or (buy and price >= ask) or (not buy and price <= bid):
                    continue
                cost = price * size
                if cost > per_order or (buy and (cost > cash or exposure + cost > gross_limit or group_exposure.get(group, Decimal(0)) + cost > per_group)):
                    rejected.append({'token': token, 'reason': 'RISK_LIMIT'})
                    continue
                if buy:
                    cash -= cost
                    exposure += cost
                    add(token, cost)
                else:
                    reserved_sell[token] = reserved_sell.get(token, Decimal(0)) + size
                admitted.append({'strategy': 'inventory-mm-shadow', 'condition': m['condition'], 'token': token,
                                 'buy': buy, 'price': price, 'size': size,
                                 'expiresMs': min(now + 250, int(m['endMs']), int(book['sourceMs']) + int(snapshot['maxBookAgeMs']))})
    return {'admitted': admitted, 'rejected': rejected, 'proposalCashRemaining': cash,
            'worstCaseAcquisitionExposure': exposure, 'groupExposure': group_exposure,
            'reason': 'UNVALIDATED_SHADOW_ONLY'}


def evaluate(snapshot, groups=None, strategy='inventory-mm-shadow', feature_evidence=None, fill_model=None):
    from .features import FeatureStore, Observation
    from .advanced import candidates, allocate
    store = FeatureStore()
    for row in sorted(feature_evidence or [], key=lambda r: (int(r['receivedMs']), r['venue'], r['symbol'], r['kind'])):
        store.add(Observation.parse(row))
    allocation = (propose(snapshot, groups=groups) if strategy == 'inventory-mm-shadow'
                  else allocate(snapshot, candidates(snapshot, store, strategy, fill_model), groups=groups))
    evidence = [x.record() for x in store.available(int(snapshot['generatedMs']))]

    return {'mode': 'PAPER', 'researchOnly': True, 'executionEnabled': False, 'liveAllowed': False,
            'observation': snapshot, 'strategy': strategy, 'featureEvidence': evidence,
            'cexSignal': store.divergence('BTCUSDT', int(snapshot['generatedMs'])), 'allocation': allocation,
            'fills': None, 'netPnl': None, 'decision': 'NO_GO',
            'note': 'Proposals are neither orders nor fills. Acquisition exposure is not mark-to-market VaR.'}
