"""Audit only two preregistered exit-trigger receipts; no matching/account mutation."""
import argparse
import base64
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path

from research.phase6.route_coverage_audit import collect, validate_selection

ROOT = Path('research/experiments/exit-trigger-selection-20261018')


def selection_and_frames():
    raw = (ROOT / 'selection.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != 'fb4f4b7970c9e850fdf898f6a232ed2e29fb24fc18ff881d5043559654c141b7':
        raise ValueError('Frozen exit selection changed')
    selection = json.loads(raw)
    original = Path('research/experiments/settlement-replay-20261018/candidate-report.original.json').read_bytes()
    if hashlib.sha256(original).hexdigest() != selection['originalCandidateReportSha256']:
        raise ValueError('Original account report changed')
    account = json.loads(original)
    frames = json.loads(gzip.decompress(base64.b64decode((ROOT / 'original-frames.json.gz.b64').read_bytes())))
    validate_bindings(selection, frames, account)
    pair = set(json.loads(Path('research/phase6/route-coverage-freeze.json').read_text())['pair'])
    validate_selection(selection, pair)
    return selection, pair


def validate_bindings(selection, frames, account):
    if len(frames) != 2 or len(selection['transactions']) != 2:
        raise ValueError('Require exactly two original exit triggers')
    order = selection['cohorts'][0]['orderDiagnostic']
    for item, frame, expected in zip(selection['transactions'], frames, selection['expectedExecutions']):
        raw = frame['raw']; normalized = frame['normalized']
        canonical = (json.dumps(raw, sort_keys=True, separators=(',', ':')) + '\n').encode()
        # The extractor hashes canonical RAW JSON without its newline.
        if hashlib.sha256(canonical.rstrip(b'\n')).hexdigest() != frame['canonicalRawRowSha256']:
            raise ValueError('Original RAW binding hash changed')
        message = json.loads(raw['data']['text'])
        sample = dict(message, arrivalMs=normalized['arrivalMs'])
        event = next(e for e in normalized['data']['events'] if e['originalEventIndex'] == item['originalEventIndex'])
        trade = event['data']
        if (sample != item['sample'] or normalized['seq'] != item['normalizedSeq']
                or raw['arrivalMs'] != normalized['arrivalMs']
                or raw['data']['frameId'] != normalized['data']['frameId']
                or event['kind'] != 'TRADE' or json.loads(trade['tradeId']) != message
                or trade['token'] != message['asset_id'] or trade['size'] != message['size']
                or trade['price'] != message['price'] or trade['side'] != message['side']
                or trade['sourceMs'] != int(message['timestamp'])):
            raise ValueError('RAW/normalized/sample binding differs')
        fills = [x for x in account['executions'] if x['orderId'] == order['id'] and x['at'] == expected['at']]
        if (len(fills) != 1 or fills[0]['size'] != expected['quantity'] or fills[0]['buy']
                or fills[0]['token'] != sample['asset_id'] or sample['side'] != 'BUY'
                or Decimal(str(fills[0]['price'])) != Decimal(sample['price'])
                or expected['at'] != sample['arrivalMs']):
            raise ValueError('Original exit execution binding differs')


def summarize(report, selection):
    order = selection['cohorts'][0]['orderDiagnostic']; rows = []
    for result in report['results']:
        conservation = result['routeConservation']
        if not conservation['uniqueConservedGroup']:
            raise ValueError('Ambiguous exit settlement identity')
        group = conservation['matchingGroups'][0]
        exact = [p for p in group['components'] if p['route'] == 'DIRECT'
                 and p['makerToken'] == order['token'] and p['makerSide'] == 'SELL'
                 and Decimal(p['makerPrice']) == Decimal(str(order['price']))]
        rows.append(dict(transactionHash=result['transactionHash'], routeSharesRaw=group['routeSharesRaw'],
                         ownSideSamePriceDirectSharesRaw=sum(p['sharesRaw'] for p in exact),
                         makerFeesRaw=sum(m['maker']['feeRaw'] for m in result['matches']
                             if m['exchange'] == group['exchange'] and m['ordersMatchedLogIndex'] == group['groupLogIndex']),
                         takerFeeRaw=next(m['taker']['feeRaw'] for m in result['matches']
                             if m['exchange'] == group['exchange'] and m['ordersMatchedLogIndex'] == group['groupLogIndex']),
                         queueAllocationProven=False))
    return dict(scope=selection['scope'], observations=rows, originalInitialQueueAhead=order['initialQueueAhead'],
                queueAllocationProven=False, fillsCreated=0, netPnlRecomputed=False,
                liveAllowed=False, independentPaperQualificationAllowed=False, decision='NO_GO')


def main():
    p = argparse.ArgumentParser(); p.add_argument('--output', required=True); args = p.parse_args()
    freeze = json.loads(Path('research/phase6/exit-trigger-freeze.json').read_text())
    for path, digest in freeze['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen exit audit changed: ' + path)
    selection, pair = selection_and_frames()
    report = collect(selection, args.output, pair)
    if not report['complete']:
        raise SystemExit('Incomplete; retain successes and retry only missing receipts')
    summary = summarize(report, selection)
    (Path(args.output) / 'exit-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
