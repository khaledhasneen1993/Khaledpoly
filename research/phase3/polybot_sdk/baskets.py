"""Multi-outcome and collateral scenarios; never a settlement/broadcast implementation."""
import re
from decimal import Decimal as D
from .model import number, integer


def universe(data):
    outcomes = data['outcomes']
    if (not isinstance(outcomes, list) or not 2 <= len(outcomes) <= 256
            or any(not isinstance(x, str) or not x.strip() for x in outcomes)
            or len(set(outcomes)) != len(outcomes)
            or not re.fullmatch('[0-9a-f]{64}', data['metadataSha256'])
            or any(type(data[k]) is not bool for k in ('negativeRisk', 'augmented', 'complete'))):
        raise ValueError('Invalid outcome universe')
    return outcomes


def analyze_basket(data, prices, size, costs=0):
    outcomes, size, costs = universe(data), number(size), number(costs)
    if set(prices) != set(outcomes) or size <= 0 or costs < 0 or any(not 0 < number(x) < 1 for x in prices.values()):
        raise ValueError('Incomplete/invalid basket scenario')
    acquisition = sum((number(x) * size for x in prices.values()), D(0)) + costs
    complete = data['complete'] and not data['augmented']
    return {'status': 'SCENARIO_ONLY', 'cost': acquisition, 'hypotheticalPayout': size if complete else None,
            'hypotheticalNet': size - acquisition if complete else None, 'metadataSha256': data['metadataSha256'],
            'venueSettlementVerified': False, 'executionEnabled': False}


def convert_no(data, outcome):
    outcomes = universe(data)
    if not data['negativeRisk'] or data['augmented'] or not data['complete'] or outcome not in outcomes:
        raise ValueError('Unknown/incomplete negative-risk conversion')
    return {'hypotheticalYesShares': {x: D(1) for x in outcomes if x != outcome},
            'venueSettlementVerified': False, 'executionEnabled': False}


def collateral_check(data, now_ms):
    # Evidence is an operator-supplied assertion until independently checked against a chain.
    required = ('chainId', 'tokenAddress', 'symbol', 'decimals', 'observedMs', 'evidenceSha256')
    if any(k not in data for k in required):
        raise ValueError('Missing collateral identity evidence')
    age = integer(now_ms) - integer(data['observedMs'])
    if (integer(data['chainId']) != 137 or not re.fullmatch('0x[0-9a-fA-F]{40}', data['tokenAddress'])
            or integer(data['decimals']) != 6 or data['symbol'] != 'pUSD' or not 0 <= age <= 86400000
            or not re.fullmatch('[0-9a-f]{64}', data['evidenceSha256'])):
        raise ValueError('Unknown, outdated or legacy collateral identity')
    return {'status': 'EVIDENCE_RECORDED_NOT_CHAIN_VERIFIED', 'symbol': 'pUSD', 'chainId': 137,
            'chainVerified': False, 'executionEnabled': False, 'broadcast': False}


def gas_scenario(gas_units, gas_price_wei, native_usd, batch_size=1):
    units, wei, batch, price = integer(gas_units), integer(gas_price_wei), integer(batch_size), number(native_usd)
    if min(units, wei) < 0 or batch < 1 or price <= 0:
        raise ValueError('Invalid gas scenario')
    total = D(units) * wei * price / D(10 ** 18)
    return {'estimatedTotalUsd': total, 'estimatedPerItemUsd': total / batch, 'batchSize': batch,
            'broadcast': False, 'estimateOnly': True}
