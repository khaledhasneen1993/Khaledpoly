"""Fixed, outcome-blind sample selection and OFFLINE settlement labels, not fills."""
from decimal import Decimal
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
    tolerance = Decimal('0.00000001')  # public price rounding only; never a fill-price relaxation
    for rows in groups.values():
        taker = rows[0]['taker']
        if taker['side'] != sample['side'] or taker['token'] != sample['asset_id']:
            continue
        shares = taker['takingRaw'] if taker['side'] == 'BUY' else taker['makingRaw']
        collateral = taker['makingRaw'] if taker['side'] == 'BUY' else taker['takingRaw']
        if (abs(Decimal(collateral)/shares - Decimal(sample['price'])) > tolerance
                or Decimal(shares)/1000000 != Decimal(sample['size'])):
            continue
        maker_total = sum(r['maker']['takingRaw'] if r['maker']['side'] == 'BUY'
                          else r['maker']['makingRaw'] for r in rows)
        mint = [r for r in rows if r['matchType'] == 'MINT'
                and r['maker']['token'] == sample['targetToken']]
        at_price = [r for r in mint if abs(Decimal(r['maker']['makingRaw']) /
                    r['maker']['takingRaw'] - Decimal(sample['targetPrice'])) <= tolerance]
        plausible.append({'exchange': rows[0]['exchange'],
            'ordersMatchedLogIndex': rows[0]['ordersMatchedLogIndex'],
            'takerShares': str(Decimal(shares)/1000000),
            'makerSharesSum': str(Decimal(maker_total)/1000000),
            'shareConservation': maker_total == shares,
            'targetMintShares': str(Decimal(sum(r['maker']['takingRaw'] for r in mint))/1000000),
            'targetMintSharesAtImpliedPrice': str(Decimal(sum(r['maker']['takingRaw'] for r in at_price))/1000000),
            'directShares': str(Decimal(sum(r['maker']['makingRaw'] for r in rows
                                if r['matchType'] == 'DIRECT'))/1000000),
            'targetMintMakerLogIndices': [r['maker']['logIndex'] for r in mint]})
    return {'matchingPublicAggregateCount': len(plausible), 'matchingGroups': plausible,
            'uniqueConservedGroup': len(plausible) == 1 and plausible[0]['shareConservation'],
            'queueAllocationProven': False, 'receiptIsFutureInformation': True,
            'usableAsEarlierDecisionFeature': False, 'simulatedFillsCreated': False}
