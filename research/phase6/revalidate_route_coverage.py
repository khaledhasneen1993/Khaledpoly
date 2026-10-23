"""Reproduce frozen receipt findings offline; never fetch data or allocate fills."""
import base64
from collections import Counter
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import zipfile

from research.phase6.receipt_audit import corroborate
from research.phase6.route_coverage_audit import routes, validate_selection

ARCHIVE = Path('research/experiments/route-coverage-20261018/artifact.zip.b64')
ZIP_SHA256 = '931df689a6775dd4deb5227f24d0b9205b228ede0501226f382357b1410c4cf1'


def revalidate(archive=ARCHIVE):
    encoded = Path(archive).read_bytes()
    if len(encoded) > 300000:
        raise ValueError('Oversized archived evidence')
    raw = base64.b64decode(b''.join(encoded.split()), validate=True)
    if hashlib.sha256(raw).hexdigest() != ZIP_SHA256:
        raise ValueError('Original artifact hash mismatch')
    freeze = json.loads(Path('research/phase6/route-coverage-freeze.json').read_text())
    for name, digest in freeze['filesSha256'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen source changed: ' + name)
    selection = json.loads(Path(freeze['selection']).read_text())
    pair = set(freeze['pair'])
    validate_selection(selection, pair)
    canonical = (json.dumps(selection, sort_keys=True, separators=(',', ':')) + '\n').encode()
    expected = {'report.json', 'selection.json'} | {
        'raw/' + row['transactionHash'] + '.json' for row in selection['transactions']}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names = z.namelist()
        if (len(names) != len(expected) or set(names) != expected
                or sum(x.file_size for x in z.infolist()) > 1000000):
            raise ValueError('Unexpected archive members/size')
        if z.read('selection.json') != canonical:
            raise ValueError('Original selection changed')
        report = json.loads(z.read('report.json'))
        if (report['selectionSha256'] != hashlib.sha256(canonical).hexdigest()
                or report['requested'] != 20 or report['corroborated'] != 20
                or report['uniqueConservedGroups'] != 20 or not report['complete']
                or report['errors'] or len(report['results']) != 20):
            raise ValueError('Incomplete original report')
        summaries = {}
        for item, recorded in zip(selection['transactions'], report['results']):
            receipt = json.loads(z.read('raw/' + item['transactionHash'] + '.json'))
            decoded = corroborate(item['sample'], receipt['receipt'], receipt['block'], report['eventTopics'])
            if any(recorded.get(k) != v for k, v in decoded.items()):
                raise ValueError('Archived receipt decode differs')
            conserved = routes(decoded, pair)
            if recorded['routeConservation'] != conserved or not conserved['uniqueConservedGroup']:
                raise ValueError('Archived route conservation differs')
            if recorded['roles'] != item['roles']:
                raise ValueError('Archived cohort differs')
            for role in item['roles']:
                s = summaries.setdefault(role, dict(transactions=0, sides=Counter(), tokens=Counter(), routeSharesRaw=Counter()))
                s['transactions'] += 1
                s['sides'][item['sample']['side']] += 1
                s['tokens'][item['sample']['asset_id']] += 1
                s['routeSharesRaw'].update(conserved['matchingGroups'][0]['routeSharesRaw'])
        for s in summaries.values():
            s['routeShares'] = {k: str(Decimal(v) / 1000000) for k, v in s['routeSharesRaw'].items()}
    return dict(verifiedTransactions=20, cohorts=summaries, networkRequests=0,
                fillsCreated=0, netPnlRecomputed=False, decision='NO_GO')


if __name__ == '__main__':
    print(json.dumps(revalidate(), indent=2))
