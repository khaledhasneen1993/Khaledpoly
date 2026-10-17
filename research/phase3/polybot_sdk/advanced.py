"""Event and complete-set candidates, then deterministic atomic portfolio admission."""
from decimal import Decimal as D, ROUND_FLOOR
from .model import number


def usable(snapshot, market, token):
    now = int(snapshot['generatedMs'])
    book = snapshot['books'].get(token)
    return (not snapshot['account']['halted'] and int(snapshot['account']['pendingTakers']) == 0
            and market['accepting'] and int(market['startMs']) <= now < int(market['endMs'])
            and now - int(market['observedMs']) <= int(snapshot['metadataMaxAgeMs'])
            and book is not None and not book['depthTruncated'] and book['bids'] and book['asks']
            and now - int(book['sourceMs']) < int(snapshot['maxBookAgeMs']))


def leg(snapshot, market, token, price, size=D(5)):
    book, now = snapshot['books'][token], int(snapshot['generatedMs'])
    return {'token': token, 'condition': market['condition'], 'buy': True, 'price': price, 'size': size,
            'expiresMs': min(now + 250, int(market['endMs']), int(book['sourceMs']) + int(snapshot['maxBookAgeMs']))}


def candidates(snapshot, features, strategy, fill_model=None):
    now, result = int(snapshot['generatedMs']), []
    if strategy not in ('event-probability', 'complete-set'):
        raise ValueError('Unknown advanced strategy')
    for market in snapshot['markets']:
        condition, tick = market['condition'], number(market['tick'])
        tokens = market['first'], market['second']
        if not all(usable(snapshot, market, token) for token in tokens):
            continue
        if strategy == 'event-probability':
            probability = features.latest('forecast', condition, 'first_outcome_probability', now)
            resolution = features.latest('forecast', condition, 'resolution_risk', now)
            if probability is None or resolution is None or number(resolution.value) != 0 or not 0 < number(probability.value) < 1:
                continue
            for token, fair in zip(tokens, (number(probability.value), 1 - number(probability.value))):
                book = snapshot['books'][token]
                price = min(number(book['bids'][0]['price']) + tick, number(book['asks'][0]['price']) - tick,
                            ((fair - D('.02')) / tick).to_integral_value(rounding=ROUND_FLOOR) * tick)
                if price <= 0:
                    continue
                item = leg(snapshot, market, token, price)
                item['expiresMs'] = min(item['expiresMs'], probability.source_ms + 2000, resolution.source_ms + 2000)
                result.append({'id': strategy + ':' + condition + ':' + token, 'strategy': strategy,
                               'edge': fair - price, 'fillProbability': None, 'legs': [item],
                               'forecastQualified': False})
        else:
            legs = []
            for token in tokens:
                book = snapshot['books'][token]
                price = min(number(book['bids'][0]['price']) + tick, number(book['asks'][0]['price']) - tick)
                legs.append(leg(snapshot, market, token, price))
            volatility = features.latest('polymarket', condition, 'volatility', now)
            vol = number(volatility.value) if volatility else None
            if vol is not None and not 0 <= vol <= 1:
                raise ValueError('Invalid volatility signal')
            remaining = D(int(market['endMs']) - now) / 1000
            threshold = D('.01') + (min(D('.05'), vol / 2) if vol is not None else D('.02')) + D('.01') / (remaining + 1)
            # A conservative virtual settlement cost, not an estimate of actual on-chain fees.
            edge = 1 - sum(number(x['price']) for x in legs) - D('.01') / 5
            probability = None
            if fill_model is not None and vol is not None:
                from .learning import predict
                if fill_model.get('target') != 'fill':
                    raise ValueError('Complete-set research requires a fill-target model')
                probabilities = []
                for item in legs:
                    book = snapshot['books'][item['token']]
                    holding = snapshot['account']['holdings'].get(item['token'], {})
                    values = {'spread': number(book['asks'][0]['price']) - number(book['bids'][0]['price']),
                              'queue_ahead': number(book['bids'][0]['size']),
                              'inventory_imbalance': min(D(1), number(holding.get('shares', 0)) / 100),
                              'source_age_ms': now - int(book['sourceMs']), 'seconds_to_expiry': remaining,
                              'volatility': vol}
                    probabilities.append(predict(fill_model, values)['probability'])
                probability = min(probabilities) if all(p is not None for p in probabilities) else None
            if edge >= threshold:
                result.append({'id': strategy + ':' + condition, 'strategy': strategy, 'edge': edge,
                               'dynamicThreshold': threshold, 'volatilityKnown': vol is not None,
                               'fillProbability': probability, 'fillModelQualified': False, 'secondLegProbability': None, 'legs': legs})
    return result


def allocate(snapshot, proposals, groups=None, per_order=D(25), per_group=D(25), gross_limit=D(100)):
    groups = {} if groups is None else groups
    if not isinstance(groups, dict) or any(not isinstance(k, str) or not isinstance(v, str) or not v for k, v in groups.items()):
        raise ValueError('Invalid portfolio groups')
    per_order, per_group, gross_limit = map(number, (per_order, per_group, gross_limit))
    if min(per_order, per_group, gross_limit) <= 0 or len(proposals) > 1000:
        raise ValueError('Invalid risk limits or too many proposals')
    account, now = snapshot['account'], int(snapshot['generatedMs'])
    markets = {m['condition']: m for m in snapshot['markets']}
    token_groups = {t: groups.get(m['condition'], m['condition']) for m in markets.values() for t in (m['first'], m['second'])}
    exposures, sold, outstanding, cash = {}, {}, set(), number(account['availableCash'])
    def add(mapping, key, value):
        mapping[key] = mapping.get(key, D(0)) + value
    for token, holding in account['holdings'].items():
        add(exposures, token_groups.get(token, 'UNCLASSIFIED'), number(holding['basis']))
    for order in account['orders'].values():
        qty = number(order['remaining'])
        if qty > 0:
            outstanding.add(order['token'])
        if order['buy']:
            add(exposures, token_groups.get(order['token'], 'UNCLASSIFIED'), qty * number(order['price']))
        else:
            add(sold, order['token'], qty)
    admitted, rejected, used_ids, used_tokens = [], [], set(), set()
    # Greedy edge-ranked admission is an explicit heuristic, not a global optimality claim.
    for proposal in sorted(proposals, key=lambda p: (-number(p['edge']), p['id'])):
        reason, local_exposure, local_sold, cost, local_tokens = None, dict(exposures), dict(sold), D(0), set()
        identity = proposal['id']
        if not isinstance(identity, str) or not identity or identity in used_ids or not proposal.get('legs'):
            reason = 'DUPLICATE_OR_EMPTY_PROPOSAL'
        if account['halted'] or int(account['pendingTakers']) > 0:
            reason = 'ACCOUNT_BLOCKED'
        for item in proposal.get('legs', []):
            condition, token = item['condition'], item['token']
            price, size = number(item['price']), number(item['size'])
            market = markets.get(condition)
            if (market is None or token not in (market['first'], market['second']) or not usable(snapshot, market, token)
                    or token in used_tokens or token in local_tokens or token in outstanding):
                reason = 'MARKET_OR_TOKEN_UNAVAILABLE'
                break
            book = snapshot['books'][token]
            expiry = int(item['expiresMs'])
            if (type(item['buy']) is not bool or not 0 < price < 1 or size < number(market['minSize'])
                    or price % number(market['tick']) != 0 or price * size > per_order
                    or not now < expiry <= min(int(market['endMs']), int(book['sourceMs']) + int(snapshot['maxBookAgeMs']))
                    or (item['buy'] and price >= number(book['asks'][0]['price']))
                    or (not item['buy'] and price <= number(book['bids'][0]['price']))):
                reason = 'INVALID_PASSIVE_ORDER'
                break
            local_tokens.add(token)
            if item['buy']:
                cost += price * size
                add(local_exposure, groups.get(condition, condition), price * size)
            else:
                add(local_sold, token, size)
                if local_sold[token] > number(account['holdings'].get(token, {}).get('shares', 0)):
                    reason = 'UNCOVERED_SELL'
        if (cost > cash or sum(local_exposure.values(), D(0)) > gross_limit
                or any(amount > per_group for amount in local_exposure.values())):
            reason = reason or 'PORTFOLIO_LIMIT'
        if reason:
            rejected.append({'id': identity, 'reason': reason})
        else:
            cash -= cost
            exposures, sold = local_exposure, local_sold
            used_tokens.update(local_tokens)
            admitted.append(proposal)
        used_ids.add(identity)
    return {'admitted': admitted, 'rejected': rejected, 'proposalCashRemaining': cash,
            'groupExposure': exposures, 'worstCaseAcquisitionExposure': sum(exposures.values(), D(0)),
            'executionEnabled': False, 'optimization': 'GREEDY_EDGE_RANKED_ATOMIC_GROUPS'}
