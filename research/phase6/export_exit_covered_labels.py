"""Add two audited environment labels; preserve all five previous bindings exactly."""
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path
import zipfile
from research.phase6.exit_trigger_audit import selection_and_frames, summarize
from research.phase6.receipt_audit import corroborate
from research.phase6.route_coverage_audit import routes

ARCHIVE = Path('research/experiments/exit-trigger-audit-20261018/artifact.zip.b64')
OLD_LABELS = Path('research/experiments/settlement-lab0-20261018/replay-labels.json')


def export():
    raw = base64.b64decode(b''.join(ARCHIVE.read_bytes().split()), validate=True)
    if hashlib.sha256(raw).hexdigest() != '72c428ee7a3adbd8881bc86ebe1a52560e3462bbf9371163b78874e2482d36da':
        raise ValueError('Original exit artifact hash differs')
    selection, pair = selection_and_frames()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        expected = {'report.json','exit-summary.json','selection.json'} | {
            'raw/'+x['transactionHash']+'.json' for x in selection['transactions']}
        if (set(z.namelist()) != expected or len(z.namelist()) != 5
                or sum(x.file_size for x in z.infolist()) > 100000):
            raise ValueError('Unexpected exit artifact membership/size')
        if json.loads(z.read('selection.json')) != selection:
            raise ValueError('Archived exit selection differs')
        report = json.loads(z.read('report.json'))
        if not report['complete'] or report['errors'] or len(report['results']) != 2:
            raise ValueError('Incomplete exit receipt report')
        labels = json.loads(OLD_LABELS.read_text())
        if labels['logicalTapeSha256'] != selection['logicalTapeSha256']:
            raise ValueError('Labels belong to different tape')
        frames = gzip.decompress(base64.b64decode(
            Path('research/experiments/exit-trigger-selection-20261018/original-frames.json.gz.b64').read_bytes()))
        frames = json.loads(frames)
        for item, original, frame in zip(selection['transactions'], report['results'], frames):
            data = json.loads(z.read('raw/'+item['transactionHash']+'.json'))
            decoded = corroborate(item['sample'],data['receipt'],data['block'],report['eventTopics'])
            if any(original.get(k) != v for k,v in decoded.items()):
                raise ValueError('Receipt re-decode differs')
            conserved = routes(decoded,pair)
            if conserved != original['routeConservation'] or not conserved['uniqueConservedGroup']:
                raise ValueError('Exit route conservation differs')
            group = conserved['matchingGroups'][0]
            matches = [m for m in decoded['matches'] if m['exchange'] == group['exchange']
                       and m['ordersMatchedLogIndex'] == group['groupLogIndex']]
            trade = frame['normalized']['data']['events'][0]['data']; sample = item['sample']
            labels['bindings'].append(dict(transactionHash=item['transactionHash'],seq=item['normalizedSeq'],
                eventIndex=item['originalEventIndex'],at=sample['arrivalMs'],sourceMs=trade['sourceMs'],
                publicTradeIdSha256=hashlib.sha256(trade['tradeId'].encode()).hexdigest(),
                token=sample['asset_id'],side=sample['side'],price=sample['price'],size=sample['size'],
                pair=sorted(pair),matches=matches))
        if summarize(report,selection) != json.loads(z.read('exit-summary.json')):
            raise ValueError('Archived exit summary differs')
    if len(labels['bindings']) != 7 or len({b['transactionHash'] for b in labels['bindings']}) != 7:
        raise ValueError('Duplicate/changed label coverage')
    return labels


if __name__ == '__main__':
    print(json.dumps(export(),indent=2))
