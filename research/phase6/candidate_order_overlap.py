"""Causal lifecycle overlap diagnostic; never changes orders or infers fills."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path


def analyze(census, report):
    diagnostics = report['makerExecutionDiagnostics']
    rows = []
    for candidate in census['examples']:
        if candidate['route'] != 'COMPLEMENT_BUY_CANDIDATE' or candidate['improvementTicks'] != 1:
            continue
        overlaps = []
        for order in diagnostics:
            activation = order.get('activatedMs')
            terminal = order.get('terminalMs')
            if (not order['buy'] or order['token'] != candidate['token'] or activation is None
                    or terminal is None or not activation < candidate['sourceMs'] <= candidate['at'] < terminal):
                continue
            price = Decimal(str(order['price'])); printed = Decimal(candidate['printPrice'])
            relation = 'AT_PRINT' if price == printed else 'MORE_AGGRESSIVE_BUY' if price > printed else 'LESS_AGGRESSIVE_BUY'
            overlaps.append({'orderId': order['id'], 'orderPrice': str(price), 'priceRelation': relation,
                'activatedMs': activation, 'terminalMs': terminal, 'terminalReason': order['terminalReason'],
                'initialQueueAhead': str(order['initialQueueAhead']),
                'remainingQueueAheadAtTerminal': str(order['remainingQueueAhead']),
                'queueAtCandidateTimeKnown': False})
        rows.append(dict(candidate, activeTargetBuyOrders=overlaps))
    return {'scope': 'LEGACY_CANDIDATE_ORDER_LIFECYCLE_OVERLAP_NOT_FILLS',
        'logicalTapeSha256': census['logicalTapeSha256'], 'candidateRows': len(rows),
        'rowsWithActiveTargetBuy': sum(bool(r['activeTargetBuyOrders']) for r in rows),
        'priceRelationOrderObservations': dict(Counter(o['priceRelation'] for r in rows for o in r['activeTargetBuyOrders'])),
        'rows': rows, 'fillsInferred': False, 'pnlInferred': False, 'decision': 'NO_GO',
        'note': 'Candidate quotes omit dynamic risk/edge constraints. Lifecycle overlap and price priority alone do not prove allocation, data validity or queue depletion.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--census', required=True); parser.add_argument('--report', required=True)
    parser.add_argument('--provenance')
    parser.add_argument('--output', required=True); args = parser.parse_args()
    census = json.loads(Path(args.census).read_text()); report = json.loads(Path(args.report).read_text())
    if census['examplesTruncated'] or not census['recordingClosedCleanly']:
        raise ValueError('Incomplete candidate evidence')
    if report.get('inputSha256') and report['inputSha256'] != census['logicalTapeSha256']:
        # Historical replay inputSha256 hashes gzip storage bytes, whereas the
        # census hashes uncompressed logical bytes. Require the retained manifest
        # and lossless-storage provenance; never silently ignore the mismatch.
        if not args.provenance:
            raise ValueError('Baseline report tape mismatch; require verified storage provenance')
        path = Path(args.provenance)
        provenance = json.loads(path.read_text())
        manifest = json.loads((path.parent/'evidence-manifest.json').read_text())
        for item in (path, Path(args.report)):
            if hashlib.sha256(item.read_bytes()).hexdigest() != manifest['filesSha256'][item.name]:
                raise ValueError('Baseline evidence manifest mismatch')
        if (provenance['logicalTapeSha256'] != census['logicalTapeSha256']
                or provenance['transformation'] != 'LOSSLESS_GZIP_STORAGE_ONLY'
                or report['rows'] != census['rows']):
            raise ValueError('Baseline logical tape provenance mismatch')
    with Path(args.output).open('x') as target:
        target.write(json.dumps(analyze(census, report), indent=2)+'\n')


if __name__ == '__main__': main()
