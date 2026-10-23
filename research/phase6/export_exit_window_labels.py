"""Validate all nine frozen window receipts offline and extend the five entry bindings."""
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path
import zipfile
from research.phase6.exit_window_audit import ROOT,validate
from research.phase6.receipt_audit import corroborate
from research.phase6.route_coverage_audit import routes

ARCHIVE=Path('research/experiments/exit-window-audit-20261018/artifact.zip.b64')


def export():
    selection=json.loads((ROOT/'selection.json').read_text())
    if hashlib.sha256((ROOT/'selection.json').read_bytes()).hexdigest()!='52ff778f09e50e73871b0905d69858da668a15864620d7937887009a390468ef':
        raise ValueError('Frozen complete window selection changed')
    frames=json.loads(gzip.decompress(base64.b64decode((ROOT/'original-frames.json.gz.b64').read_bytes())))
    validate(selection,frames)
    raw=base64.b64decode(b''.join(ARCHIVE.read_bytes().split()),validate=True)
    if hashlib.sha256(raw).hexdigest()!='0e856ae5da7aa679a06db38a877962125f62a3c1dc61a5492b52dc2eb8338b29':
        raise ValueError('Original nine-receipt artifact hash differs')
    labels=json.loads(Path('research/experiments/settlement-lab0-20261018/replay-labels.json').read_text())
    if labels['logicalTapeSha256']!=selection['logicalTapeSha256']:raise ValueError('Wrong original tape')
    pair=set(json.loads(Path('research/phase6/route-coverage-freeze.json').read_text())['pair'])
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        expected={'report.json','selection.json'}|{'raw/'+x['transactionHash']+'.json' for x in selection['transactions']}
        if set(z.namelist())!=expected or len(z.namelist())!=11 or sum(x.file_size for x in z.infolist())>500000:
            raise ValueError('Unexpected nine-receipt archive membership/size')
        if json.loads(z.read('selection.json'))!=selection:raise ValueError('Original selection differs')
        report=json.loads(z.read('report.json'))
        if not report['complete'] or report['errors'] or len(report['results'])!=9:
            raise ValueError('Incomplete original receipt audit')
        for item,frame,original in zip(selection['transactions'],frames,report['results']):
            data=json.loads(z.read('raw/'+item['transactionHash']+'.json'))
            decoded=corroborate(item['sample'],data['receipt'],data['block'],report['eventTopics'])
            if any(original.get(k)!=v for k,v in decoded.items()):raise ValueError('Receipt decode differs')
            conserved=routes(decoded,pair)
            if conserved!=original['routeConservation'] or not conserved['uniqueConservedGroup']:
                raise ValueError('Conserved route differs')
            group=conserved['matchingGroups'][0];trade=frame['normalized']['data']['events'][0]['data'];sample=item['sample']
            matches=[m for m in decoded['matches'] if m['exchange']==group['exchange'] and m['ordersMatchedLogIndex']==group['groupLogIndex']]
            labels['bindings'].append(dict(transactionHash=item['transactionHash'],seq=item['normalizedSeq'],
                eventIndex=item['originalEventIndex'],at=sample['arrivalMs'],sourceMs=trade['sourceMs'],
                publicTradeIdSha256=hashlib.sha256(trade['tradeId'].encode()).hexdigest(),
                token=sample['asset_id'],side=sample['side'],price=sample['price'],size=sample['size'],pair=sorted(pair),matches=matches))
    if len(labels['bindings'])!=14 or len({x['transactionHash'] for x in labels['bindings']})!=14:
        raise ValueError('Duplicate/changed full-window bindings')
    return labels


if __name__=='__main__':print(json.dumps(export(),indent=2))
