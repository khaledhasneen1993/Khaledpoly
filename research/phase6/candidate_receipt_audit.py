"""Fixed, outcome-blind sample selection and OFFLINE settlement labels, not fills."""
from decimal import Decimal
import argparse
import json
from pathlib import Path
import re


def select_samples(report, source):
    if report.get('examplesTruncated') is not False or not report.get('recordingClosedCleanly'):
        raise ValueError('Candidate evidence must be complete and cleanly closed')
    digest = report['logicalTapeSha256']
    if not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('Invalid tape digest')
    rows = [r for r in report['examples'] if r['route'] == 'COMPLEMENT_BUY_CANDIDATE'
            and r['improvementTicks'] == 1]
    if len(rows) != report['complementBuyCandidateCounts']['1'].get('NECESSARY_CONDITIONS_ONLY', 0):
        raise ValueError('Candidate count disagrees with retained rows')
    selected = []
    seen = set()
    # Freeze the first five unique transactions chronologically, BEFORE reading receipts.
    for row in sorted(rows, key=lambda r: (int(r['sourceMs']), int(r['at']), r['transactionHash'])):
        tx = row['transactionHash'].lower()
        if not re.fullmatch('0x[0-9a-f]{64}', tx):
            raise ValueError('Missing candidate transaction hash')
        if tx in seen:
            continue
        pair = {row['firstToken'], row['secondToken']}
        if (len(pair) != 2 or {row['token'], row['reportedToken']} != pair
                or row['reportedSide'] != 'BUY'
                or Decimal(row['printPrice']) + Decimal(row['reportedPrice']) != 1):
            raise ValueError('Inconsistent complementary candidate')
        seen.add(tx)
        selected.append({'transaction_hash': tx, 'asset_id': row['reportedToken'],
            'side': row['reportedSide'], 'price': row['reportedPrice'], 'size': row['printSize'],
            'timestamp': str(row['sourceMs']), 'targetToken': row['token'],
            'targetPrice': row['printPrice'], 'condition': row['condition'],
            'recordedAtMs': row['at'], 'source': source, 'logicalTapeSha256': digest})
        if len(selected) == 5:
            break
    if len(selected) != 5:
        raise ValueError('Require five unique candidate transactions per tape')
    return selected


def label_candidate(sample, matches):
    """Do not allocate aggregate public volume to every maker or to a fake order."""
    groups = {}
    for row in matches:
        groups.setdefault((row['exchange'], row['ordersMatchedLogIndex'], row['taker']['orderHash']), []).append(row)
    plausible = []
    identity_groups = []
    tolerance = Decimal('0.00000001')  # public price rounding only; never a fill-price relaxation
    for rows in groups.values():
        taker = rows[0]['taker']
        if taker['side'] != sample['side'] or taker['token'] != sample['asset_id']:
            continue
        shares = taker['takingRaw'] if taker['side'] == 'BUY' else taker['makingRaw']
        collateral = taker['makingRaw'] if taker['side'] == 'BUY' else taker['takingRaw']
        if Decimal(shares)/1000000 != Decimal(sample['size']):
            continue
        price_difference = abs(Decimal(collateral)/shares - Decimal(sample['price']))
        maker_total = sum(r['maker']['takingRaw'] if r['maker']['side'] == 'BUY'
                          else r['maker']['makingRaw'] for r in rows)
        mint = [r for r in rows if r['matchType'] == 'MINT'
                and r['maker']['token'] == sample['targetToken']]
        at_price = [r for r in mint if abs(Decimal(r['maker']['makingRaw']) /
                    r['maker']['takingRaw'] - Decimal(sample['targetPrice'])) <= tolerance]
        # Settlement amounts are integer micro-collateral. Report this rounding
        # separately, without changing the strict price comparison or fill rules.
        within_unit = [r for r in mint if abs(Decimal(r['maker']['makingRaw']) -
                       Decimal(sample['targetPrice']) * r['maker']['takingRaw']) <= 1]
        group = {'exchange': rows[0]['exchange'],
            'ordersMatchedLogIndex': rows[0]['ordersMatchedLogIndex'],
            'takerShares': str(Decimal(shares)/1000000),
            'makerSharesSum': str(Decimal(maker_total)/1000000),
            'shareConservation': maker_total == shares,
            'targetMintShares': str(Decimal(sum(r['maker']['takingRaw'] for r in mint))/1000000),
            'targetMintSharesAtImpliedPrice': str(Decimal(sum(r['maker']['takingRaw'] for r in at_price))/1000000),
            'targetMintSharesWithinOneCollateralUnit': str(Decimal(sum(r['maker']['takingRaw'] for r in within_unit))/1000000),
            'publicPriceVsWeightedAggregateDifference': str(price_difference),
            'publicPriceMatchesWeightedAggregate': price_difference <= tolerance,
            'directShares': str(Decimal(sum(r['maker']['makingRaw'] for r in rows
                                if r['matchType'] == 'DIRECT'))/1000000),
            'targetMintMakerLogIndices': [r['maker']['logIndex'] for r in mint]}
        identity_groups.append(group)
        if price_difference <= tolerance:
            plausible.append(group)
    return {'matchingPublicAggregateCount': len(plausible), 'matchingGroups': plausible,
            'uniqueConservedGroup': len(plausible) == 1 and plausible[0]['shareConservation'],
            'identityMatchingGroupCount': len(identity_groups), 'identityMatchingGroups': identity_groups,
            'uniqueIdentityConservedGroup': len(identity_groups) == 1 and identity_groups[0]['shareConservation'],
            'queueAllocationProven': False, 'receiptIsFutureInformation': True,
            'usableAsEarlierDecisionFeature': False, 'simulatedFillsCreated': False}


def revalidate_saved(folder, output):
    """Reproduce labels from committed receipts without importing Keccak or using RPC."""
    from research.phase6.receipt_audit import corroborate
    folder = Path(folder)
    initial = json.loads((folder/'initial-strict-report.json').read_text())
    selection = json.loads((folder/'selection.json').read_text())['samples']
    if selection != [r['sample'] for r in initial['results']] or initial['errors'] or not initial['complete']:
        raise ValueError('Require complete original frozen receipt audit')
    results = []
    for index, original in enumerate(initial['results']):
        raw = json.loads((folder/'raw'/('receipt-'+str(index)+'.json')).read_text())
        result = corroborate(original['sample'], raw['receipt'], raw['block'], initial['eventTopics'])
        if result['matches'] != original['matches']:
            raise ValueError('Offline decoding changed original settlement groups')
        results.append(result)
    report = dict(initial, results=results, offlineRevalidation=True,
                  networkCalls=0, originalStrictComparisonsPreserved=True)
    with Path(output).open('x') as target:
        target.write(json.dumps(report, indent=2)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--offline-from', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    revalidate_saved(args.offline_from, args.output)


if __name__ == '__main__':
    main()
