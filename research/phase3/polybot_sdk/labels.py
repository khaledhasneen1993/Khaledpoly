"""Derive PAPER labels only from own-order telemetry, real print-driven model fills and clean tapes."""
from collections import defaultdict
import hashlib
from pathlib import Path
from .model import decode, dumps, integer, number
from .learning import example
from .runtime import private_write


def build_labels(tape, directory):
    tape, directory = Path(tape), Path(directory)
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    orders, fills, cancellations, markouts, groups = {}, defaultdict(list), {}, {}, {}
    markout_identities = set()
    previous, sequence, run, ended, last, gaps, unavailable = -1, 0, None, False, -1, [], 0
    checksum = hashlib.sha256()
    with tape.open('rb') as stream:
        for raw in iter(lambda: stream.readline(8 * 1024 * 1024 + 1), b''):
            if len(raw) > 8 * 1024 * 1024 or not raw.endswith(b'\n'):
                raise ValueError('Incomplete/oversized label tape row')
            checksum.update(raw)
            row = decode(raw)
            at = integer(row['arrivalMs'])
            if (ended or at < previous or integer(row['seq']) != sequence + 1
                    or row['schema'] != 1 or (run is not None and row['runId'] != run)):
                raise ValueError('Noncausal or mixed label tape')
            previous, last, sequence, run = at, at, sequence + 1, row['runId']
            kind, data = row['kind'], row['data']
            if kind == 'RUN_END':
                ended = data.get('complete') is True
                if not ended:
                    raise ValueError('Incomplete recording cannot supply negative labels')
            elif kind == 'SESSION_ORDER_FEATURES':
                identity = data['orderId']
                if identity in orders or data['provenance'] != 'PAPER_MODEL':
                    raise ValueError('Duplicate order features or mixed provenance')
                if integer(data['featureObservedMs']) > integer(data['submittedMs']) or integer(data['submittedMs']) > at:
                    raise ValueError('Future own-order features')
                if len(orders) >= 100000:
                    raise ValueError('Own-order label bound exceeded')
                orders[identity] = data
            elif kind == 'SESSION_FEATURES_UNAVAILABLE':
                unavailable += 1
            elif kind == 'SESSION_FILL':
                if integer(data['at']) > at or number(data['size']) <= 0:
                    raise ValueError('Invalid own-order fill')
                fills[data['id']].append((integer(data['at']), number(data['size'])))
            elif kind == 'SESSION_ORDER_TERMINAL' and data['status'] != 'FILLED':
                terminal = integer(data['at'])
                if terminal > at:
                    raise ValueError('Future terminal status')
                cancellations.setdefault(data['id'], terminal)
            elif kind == 'SESSION_MARKOUT':
                if (integer(data['observedMs']) > at or integer(data['sourceMs']) > integer(data['observedMs'])
                        or integer(data['sourceMs']) < integer(data['fillAt']) + integer(data['horizonMs'])):
                    raise ValueError('Noncausal markout')
                key = data['id'], integer(data['fillAt']), integer(data['horizonMs'])
                identity = key + (integer(data.get('fillSequence', 0)),)
                if identity in markout_identities or number(data['quantity']) <= 0:
                    raise ValueError('Duplicate/invalid markout sample')
                markout_identities.add(identity)
                markouts.setdefault(key, []).append(data)
            elif kind == 'SESSION_PROPOSAL_GROUP':
                identity = data['groupId']
                if identity in groups:
                    raise ValueError('Duplicate proposal group')
                members = {x['id']: number(x['quantity']) for x in data['orders']}
                if len(members) != len(data['orders']) or any(x <= 0 for x in members.values()):
                    raise ValueError('Invalid proposal membership')
                groups[identity] = members
            if (kind in ('RESEARCH_GAP', 'RESEARCH_FEED_ERROR')
                    or (kind == 'RESEARCH_FRAME' and any(e['kind'] == 'GAP' for e in data['events']))):
                gaps.append(at)
    if not ended:
        raise ValueError('Clean RUN_END required; missing data is never a negative fill')
    paired, membership = {}, {}
    for group, members in groups.items():
        completions = []
        for identity, requested in members.items():
            if identity in membership:
                raise ValueError('Order belongs to multiple intent groups')
            membership[identity] = group
            cumulative = number(0)
            complete_at = None
            for at, quantity in fills[identity]:
                cumulative += quantity
                if cumulative > requested:
                    raise ValueError('Fill quantity exceeds own order')
                if cumulative == requested and complete_at is None:
                    complete_at = at
            completions.append(complete_at)
        if len(members) >= 2 and all(x is not None for x in completions):
            paired[group] = max(completions)
    rows = []
    for identity, feature in sorted(orders.items()):
        submitted = integer(feature['submittedMs'])
        end = min([last] + [at for at in gaps if at >= submitted])
        own_fills = [at for at, _ in fills[identity] if submitted <= at <= end]
        first = min(own_fills) if own_fills else None
        group = membership.get(identity)
        completion = paired.get(group)
        row = {k: feature[k] for k in ('orderId', 'marketId', 'submittedMs', 'featureObservedMs', 'provenance', 'features')}
        if 'featuresV2' in feature:
            row['featuresV2']=feature['featuresV2']
            example(dict(row,labelEndMs=end),feature_schema='v2')
        row.update(labelEndMs=end, fillMs=first, cancelMs=cancellations.get(identity),
                   secondLegMs=completion if completion is not None and completion <= end else None)
        if group is not None:
            row['groupId'] = group
        if row['cancelMs'] is not None and row['cancelMs'] > end:
            row['cancelMs'] = None
        samples = markouts.get((identity, first, 5000), [])
        if samples and all(integer(sample['observedMs']) <= end for sample in samples):
            # One frame can partially fill the same order several times at the same timestamp.
            # Keep each actual fill sample distinct and weight the first-fill instant by quantity.
            quantity = sum((number(sample['quantity']) for sample in samples), number(0))
            filled_quantity = sum((quantity for at, quantity in fills[identity] if at == first), number(0))
            if quantity > filled_quantity:
                raise ValueError('Markout quantity exceeds its actual fill instant')
            if quantity == filled_quantity:
                markout = sum((number(sample['perShare']) * number(sample['quantity']) for sample in samples), number(0)) / quantity
                row.update(markout=markout, markoutObservedMs=max(integer(sample['observedMs']) for sample in samples))
        # Validate even censored rows so invalid evidence cannot hide among rejected examples.
        example(row)
        rows.append(row)
    import os
    with (directory / 'labels.jsonl').open('x') as output:
        os.chmod(directory / 'labels.jsonl', 0o600)
        for row in rows:
            output.write(dumps(row) + '\n')
        output.flush()
        os.fsync(output.fileno())
    report = {'provenance': 'PAPER_MODEL', 'ordersWithFeatures': len(rows), 'ordersWithoutFeatures': unavailable,
              'sourceTapeSha256': checksum.hexdigest(), 'recordingComplete': ended, 'dataGaps': len(gaps),
              'fillLabels': sum(example(row) is not None for row in rows),
              'secondLegLabels': sum(example(row, 'second_leg') is not None for row in rows),
              'markoutLabels': sum(example(row, 'adverse_selection') is not None for row in rows),
              'venueExecutionEvidence': False, 'decision': 'NO_GO', 'liveAllowed': False}
    private_write(directory / 'report.json', report)
    return report
