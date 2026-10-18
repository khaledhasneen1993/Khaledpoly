"""Original only-pair context and two frozen public receipts; never creates fills."""
import argparse
import base64
from decimal import Decimal
import gzip
import hashlib
import io
import json
from pathlib import Path
import zipfile
from research.phase6.route_coverage_audit import collect, validate_selection

ROOT = Path('research/experiments/risk-pair-context-20261018')
DIAGNOSTIC = Path('research/experiments/residual-entry-risk-20261018/result/only-pair-diagnostic.json')
ZIP_SHA = 'fddaeffc29f635b643d9e5ac715c33f85935155968bd6951b29b69c8ddfdbb36'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def load_context():
    raw = base64.b64decode((ROOT/'artifact.zip.b64').read_bytes(), validate=False)
    if hashlib.sha256(raw).hexdigest() != ZIP_SHA:
        raise ValueError('Original context artifact hash mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        if len(infos) != 1 or infos[0].filename != 'risk-opportunity-context.json.gz' or infos[0].file_size != 339605:
            raise ValueError('Unexpected original context artifact members')
        with gzip.GzipFile(fileobj=io.BytesIO(archive.read(infos[0]))) as stream:
            decoded = stream.read(12000001)
        if len(decoded) > 12000000:
            raise ValueError('Context decompression cap exceeded')
    return json.loads(decoded)


def analyze(context, diagnostics):
    orders = diagnostics['makerExecutionDiagnostics']
    if len(orders) != 2 or any(not x['buy'] for x in orders):
        raise ValueError('Require actual BUY pair')
    pair = {x['token'] for x in orders}
    submit, active, terminal = orders[0]['submittedMs'], orders[0]['activatedMs'], orders[0]['terminalMs']
    if any((o['submittedMs'], o['activatedMs'], o['terminalMs'], o['terminalReason']) !=
           (submit, active, terminal, 'DATA_GAP:invalid_depth') for o in orders):
        raise ValueError('Actual pair lifecycle mismatch')
    if set(context['spec']['tokens']) != pair or context['sourceRows'] != 6163831 or len(context['frames']) != 2259:
        raise ValueError('Wrong complete context source')
    expected = json.loads(Path('research/phase6/risk-opportunity-context-freeze.json').read_text())
    if context['spec'] != expected['spec'] or context['logicalTapeSha256'] != expected['spec']['logicalTapeSha256']:
        raise ValueError('Wrong frozen tape/window')
    latest = {}; trades = []; gaps = []; recoveries = []; last_seq = -1
    for frame in context['frames']:
        raw, norm = frame['raw'], frame['normalized']
        if (hashlib.sha256(canonical(raw)).hexdigest() != frame['canonicalRawRowSha256']
                or raw['data']['frameId'] != norm['data']['frameId'] or raw['seq'] >= norm['seq']
                or raw['seq'] <= last_seq or raw['runId'] != norm['runId']
                or norm['runId'] != context['runId'] or raw['arrivalMs'] > norm['arrivalMs']):
            raise ValueError('Original frame hash/binding mismatch')
        last_seq = norm['seq']; at = norm['arrivalMs']; original = json.loads(raw['data']['text'])
        for event in norm['data']['events']:
            data = event['data']; token = data.get('token'); kind = event['kind']
            if kind == 'BOOK' and token in pair:
                if original.get('event_type') == 'book':
                    if original['asset_id'] != token or int(original['timestamp']) != data['sourceMs']:
                        raise ValueError('Original snapshot identity mismatch')
                    for side, reverse in [('bids', True), ('asks', False)]:
                        levels = sorted((x for x in original[side] if Decimal(x['size']) > 0),
                                        key=lambda x: Decimal(x['price']), reverse=reverse)[:3]
                        if levels != data[side]:
                            raise ValueError('Original full-book/projection mismatch')
                if at <= submit:
                    latest[token] = dict(seq=norm['seq'], arrivalMs=at, sourceMs=data['sourceMs'],
                        bids=data['bids'], asks=data['asks'], originalEventType=original.get('event_type'))
                if terminal < at and original.get('event_type') == 'book' and not any(x['token'] == token for x in recoveries):
                    recoveries.append(dict(token=token, seq=norm['seq'], arrivalMs=at, sourceMs=data['sourceMs']))
            if kind == 'GAP' and at == terminal:
                if data.get('reason') != 'invalid_depth':
                    raise ValueError('Wrong actual terminal GAP')
                gaps.append(dict(seq=norm['seq'], eventIndex=event['originalEventIndex'], data=data))
            if kind == 'TRADE' and active <= at <= terminal:
                sample = json.loads(data['tradeId'])
                if (sample != original or sample['event_type'] != 'last_trade_price'
                        or sample['asset_id'] != token or sample['side'] != data['side']
                        or int(sample['timestamp']) != data['sourceMs']
                        or any(Decimal(sample[k]) != Decimal(data[k]) for k in ('price', 'size'))):
                    raise ValueError('Original public trade/normalized mismatch')
                sample = dict(sample, arrivalMs=at)
                trades.append(dict(seq=norm['seq'], eventIndex=event['originalEventIndex'], sample=sample,
                    classification='SOURCE_BEFORE_OBSERVED_ACTIVATION' if data['sourceMs'] < active else 'RECEIPT_REQUIRED'))
    if set(latest) != pair or not gaps or len(trades) != 4 or len(recoveries) != 2:
        raise ValueError('Incomplete actual context evidence')
    txs = []; cohorts = []
    for trade in trades:
        if trade['classification'] != 'RECEIPT_REQUIRED':
            continue
        sample = trade['sample']
        if sample['side'] != 'BUY':
            raise ValueError('Unexpected new route; do not broaden selection')
        target = next(o for o in orders if o['token'] != sample['asset_id'])
        role = target['id']; tx = sample['transaction_hash']
        txs.append(dict(transactionHash=tx, roles=[role], sample=sample,
            normalizedSeq=trade['seq'], eventIndex=trade['eventIndex'], targetOrder=target))
        cohorts.append(dict(role=role, orderDiagnostic=target, transactions=[tx]))
    selection = dict(scope='ACTUAL_ONLY_RISK_PAIR_POST_ACTIVATION_NOT_COUNTERFACTUAL_WINDOW',
        maxNewReceiptRequests=2, cohorts=cohorts, transactions=txs)
    if len(txs) != 2:
        raise ValueError('Frozen two-receipt budget changed')
    validate_selection(selection, pair)
    clocks = [x['sourceMs'] for x in latest.values()]
    proof = dict(scope='ONLY_PAIR_ORIGINAL_CONTEXT_NOT_FILL_PROOF', sourceRows=context['sourceRows'],
        logicalTapeSha256=context['logicalTapeSha256'], artifactZipSha256=ZIP_SHA,
        submitMs=submit, observedActivationMs=active, terminalMs=terminal, activeMs=terminal-active,
        booksAtSubmit=latest, sourceClockSkewMs=max(clocks)-min(clocks),
        sourceAgeAtSubmitMs={k:submit-v['sourceMs'] for k,v in latest.items()},
        publicTradesDuringArrivalActiveInterval=trades, terminalGaps=gaps, firstFullSnapshotAfterCancel=recoveries,
        queueReconstructed=False, fillsInferred=False, pnlInferred=False, liveAllowed=False,
        decision='NO_GO_ZERO_FILLS_PENDING_TWO_RECEIPTS')
    return proof, selection


def summarize_routes(report, selection):
    if not report['complete'] or report['requested'] != 2 or len(report['results']) != 2:
        raise ValueError('Incomplete two-receipt evidence')
    targets = {x['transactionHash']:x for x in selection['transactions']}
    seen = set(); results = []
    for row in report['results']:
        tx = row['sample']['transaction_hash']; item = targets[tx]; order = item['targetOrder']
        if tx in seen or row['sample'] != item['sample'] or not row['routeConservation']['uniqueConservedGroup']:
            raise ValueError('Duplicate or ambiguous settlement group')
        seen.add(tx)
        group = row['routeConservation']['matchingGroups'][0]
        portions = [p for p in group['components'] if p['makerToken'] == order['token'] and p['makerSide'] == 'BUY']
        price_eligible = [p for p in portions if Decimal(p['collateralRaw']) <= Decimal(str(order['price']))*p['sharesRaw']]
        results.append(dict(transactionHash=tx, targetOrderId=order['id'], targetBid=order['price'],
            actualRouteSharesRaw=group['routeSharesRaw'], targetBuyComponents=portions,
            targetBuyAtOrBelowOwnBidSharesRaw=sum(p['sharesRaw'] for p in price_eligible)))
    return dict(scope='ACTUAL_MAKER_COMPONENT_PRICES_NOT_QUEUE_ALLOCATION', results=results,
        fillsCreated=0, netPnlRecomputed=False, independentPaperQualificationAllowed=False,
        liveAllowed=False, decision='NO_GO',
        note='Even price-compatible maker volume is not evidence of queue allocation or redirect priority.')


def main():
    p = argparse.ArgumentParser(); p.add_argument('--output', required=True); p.add_argument('--offline-only', action='store_true'); a = p.parse_args()
    proof, selection = analyze(load_context(), json.loads(DIAGNOSTIC.read_text()))
    output = Path(a.output); output.mkdir(parents=True, exist_ok=True)
    if not a.offline_only:
        freeze = json.loads(Path('research/phase6/risk-pair-receipts-freeze.json').read_text())
        for name, digest in freeze['filesSha256'].items():
            if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest:
                raise ValueError('Frozen two-receipt audit changed: '+name)
        if selection != json.loads((ROOT/'selection.json').read_text()):
            raise ValueError('Frozen public selection changed')
    (output/'context-proof.json').write_text(json.dumps(proof, indent=2)+'\n')
    (output/'selection.json').write_text(json.dumps(selection, sort_keys=True, separators=(',', ':'))+'\n')
    if a.offline_only:
        return
    report = collect(selection, output, set(proof['booksAtSubmit']))
    # The reusable old collector carries a legacy -.85 diagnostic constant, NOT
    # an economic calculation. Explicitly remove it for this unrelated audit.
    report.pop('originalAccountNetPnl', None)
    report['scope'] = 'FROZEN_TWO_ACTUAL_RISK_PAIR_RECEIPTS_NOT_ACCOUNT_REPLAY'
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    summary = summarize_routes(report, selection)
    (output/'route-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
