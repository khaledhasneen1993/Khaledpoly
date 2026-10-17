"""Independent PAPER/venue historical strategy accounting (no order submission).

Retrospective replay is research only. A backtest cannot certify latency,
actual venue fills, a forecaster, or strategy profitability in live markets.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
import argparse
import hashlib
from pathlib import Path

from research.phase3.polybot_sdk.model import dumps, decode, integer
from research.phase3.polybot_sdk.runtime import private_write

MAX_ROWS = 100000
PROVENANCE = ('PAPER_MODEL', 'VENUE_EXECUTION')
D = Decimal


def amount(value, label, allow_negative=False):
    try:
        if isinstance(value, bool):
            raise ValueError('Boolean decimal')
        result = D(str(value))
    except (ValueError, InvalidOperation, TypeError) as exc:
        raise ValueError('Invalid monetary field: ' + label) from exc
    if not result.is_finite() or (not allow_negative and result < 0) or abs(result) > D('1e12'):
        raise ValueError('Out-of-domain monetary field: ' + label)
    return result


def normalized_trades(records):
    seen, rows, provenance = set(), [], set()
    for item in records:
        if len(rows) >= MAX_ROWS:
            raise ValueError('Trade dataset exceeded offline bound')
        if not isinstance(item, dict):
            raise ValueError('Trade row is not an object')
        for name in ('tradeId', 'marketId', 'strategyId'):
            if not isinstance(item.get(name), str) or not item[name].strip() or len(item[name]) > 128:
                raise ValueError('Missing/invalid trade, market or strategy ID')
        if item['tradeId'] in seen:
            raise ValueError('Duplicate trade identity')
        seen.add(item['tradeId'])
        start, end = integer(item['openedMs']), integer(item['closedMs'])
        if not 0 < start <= end:
            raise ValueError('Noncausal trade times')
        group = item.get('groupId', item['marketId'])
        if not isinstance(group, str) or not group.strip() or len(group) > 128:
            raise ValueError('Invalid group identity')
        basis = item.get('provenance')
        if basis not in PROVENANCE:
            raise ValueError('Trade provenance is required')
        provenance.add(basis)
        size = amount(item['notionalUsd'], 'notionalUsd')
        gross = amount(item['grossPnlUsd'], 'grossPnlUsd', allow_negative=True)
        fees = amount(item['feeBpsPerSide'], 'feeBpsPerSide')
        slip = amount(item['slippageBpsPerSide'], 'slippageBpsPerSide')
        if fees > D(10000) or slip > D(10000) or size == 0:
            raise ValueError('Unsupported transaction cost or trade notional')
        rows.append({'tradeId':item['tradeId'], 'marketId':item['marketId'],
                     'groupId':group, 'strategyId':item['strategyId'],
                     'openedMs':start, 'closedMs':end, 'provenance':basis,
                     'size':size, 'gross':gross, 'fees':fees, 'slippage':slip})
    if len(provenance) > 1:
        raise ValueError('Cannot pool PAPER and venue execution evidence')
    if not rows:
        raise ValueError('No trade evidence')
    return rows, next(iter(provenance))


def split_by_purged_market_group(rows, holdout_ms):
    """Remove every linked market/group component that straddles the cutoff."""
    parent = {}
    def root(key):
        parent.setdefault(key, key)
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key
    for row in rows:
        a, b = 'market:' + row['marketId'], 'group:' + row['groupId']
        parent[root(a)] = root(b)
    partitions = defaultdict(list)
    for row in rows:
        partitions[root('market:' + row['marketId'])].append(row)
    train, heldout, purged = [], [], []
    for part in partitions.values():
        if max(r['closedMs'] for r in part) < holdout_ms:
            train += part
        elif min(r['openedMs'] for r in part) >= holdout_ms:
            heldout += part
        else:
            purged += part
    return train, heldout, purged


def summarize(rows, stress_multiplier):
    if not rows:
        return {'trades':0, 'grossPnlUsd':None, 'netPnlUsd':None,
                'stressedNetPnlUsd':None, 'maxDrawdownUsd':None,
                'profitableTrades':None, 'transactionCostsUsd':None}
    gross = costs = net = stressed = equity = peak = drawdown = D(0)
    wins = 0
    for row in sorted(rows, key=lambda t:(t['closedMs'], t['tradeId'])):
        fee = row['size'] * D(2) * row['fees'] / D(10000)
        slip = row['size'] * D(2) * row['slippage'] / D(10000)
        outcome = row['gross'] - fee - slip
        costs += fee + slip
        gross += row['gross']
        net += outcome
        stressed += row['gross'] - fee - slip * stress_multiplier
        wins += outcome > 0
        equity += outcome
        peak = max(peak, equity)
        drawdown = max(drawdown, peak-equity)
    return {'trades':len(rows),'grossPnlUsd':str(gross),'netPnlUsd':str(net),
            'stressedNetPnlUsd':str(stressed),'maxDrawdownUsd':str(drawdown),
            'profitableTrades':wins,'transactionCostsUsd':str(costs)}


def evaluate(records, holdout_start_ms, stress_multiplier=2, minimum_heldout_groups=30):
    cut = integer(holdout_start_ms)
    factor = amount(stress_multiplier, 'stressMultiplier')
    if not 0 < cut or not D(1) <= factor <= D(10):
        raise ValueError('Invalid holdout boundary or stress factor')
    if not isinstance(minimum_heldout_groups, int) or not 1 <= minimum_heldout_groups <= 10000:
        raise ValueError('Invalid minimum independent groups')
    rows, basis = normalized_trades(records)
    train, heldout, purged = split_by_purged_market_group(rows, cut)
    strategies = sorted(set(r['strategyId'] for r in rows))
    by_strategy = {}
    group_sets = []
    for strategy in strategies:
        training = [r for r in train if r['strategyId'] == strategy]
        test = [r for r in heldout if r['strategyId'] == strategy]
        distinct_groups = set((r['marketId'], r['groupId']) for r in test)
        group_sets.append(distinct_groups)
        by_strategy[strategy] = {
            'training': summarize(training, factor),
            'heldout': summarize(test, factor),
            'heldoutMarketGroups':len(distinct_groups),
            'minimumHeldoutGroupsMet':len(distinct_groups) >= minimum_heldout_groups,
            'qualified':False}
    return {'schema':1, 'scope':'OFFLINE_PHASE5_PURGED_STRATEGY_ACCOUNTING',
            'holdoutStartMs':cut, 'stressMultiplier':str(factor),
            'sourceProvenance':basis,
            'inputSha256':hashlib.sha256(dumps(records).encode()).hexdigest(),
            'rows':len(rows),'trainRows':len(train),'heldoutRows':len(heldout),
            'purgedRows':len(purged),
            'strategyResults':by_strategy,
            'crossStrategyComparableMarketGroups':len(group_sets) > 1 and all(g == group_sets[0] for g in group_sets),
            'preregisteredHoldoutVerified':False,'venueFillEvidenceVerified':False,
            'strategyQualified':False,'decision':'NO_GO','liveAllowed':False}


def main():
    parser=argparse.ArgumentParser(description='Offline research accounting; no funded orders')
    parser.add_argument('trades',help='Immutable historical JSONL with recorded explicit costs')
    parser.add_argument('--holdout-start-ms',type=int,required=True)
    parser.add_argument('--stress-multiplier',type=str,default='2')
    parser.add_argument('--min-heldout-groups',type=int,default=30)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    rows=[]
    with Path(args.trades).open(encoding='utf-8') as handle:
        for line in handle:
            if line.strip():
                rows.append(decode(line))
            if len(rows) > MAX_ROWS:
                raise ValueError('Dataset too large')
    result=evaluate(rows,args.holdout_start_ms,args.stress_multiplier,args.min_heldout_groups)
    private_write(args.output,result)
    print(dumps(result))


if __name__=='__main__':
    main()
