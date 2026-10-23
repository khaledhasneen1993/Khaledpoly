"""One remaining selected leg, preregistered19 receipts, no parameter tuning."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile
from research.phase6.dq3_receipt_coverage import ROOT,cached_receipts,next_selection,coverage,collect


def previous_evidence():
    e=cached_receipts();raw=base64.b64decode((ROOT/'overlap-result/artifact.zip.b64').read_bytes())
    if hashlib.sha256(raw).hexdigest()!='baade0bae80c97677a4a4109da1bbf153e8445631e936e47aa6fc563d6caa621':
        raise ValueError('Changed conserved39-receipt evidence')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        report=json.loads(z.read('report.json'))
        if not report['complete'] or report['errors']:raise ValueError('Incomplete previous cohort')
        for name in z.namelist():
            if name.startswith('raw/'):
                data=json.loads(z.read(name));tx=data['receipt']['transactionHash']
                if tx in e:raise ValueError('Duplicate transaction')
                e[tx]=dict(data=data,topics=report['eventTopics'])
        if coverage(e)!=json.loads(z.read('coverage.json')):raise ValueError('Previous conserved coverage changed')
    return e


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    f=json.loads(Path('research/phase6/dq3-last-selected-leg-freeze.json').read_text())
    for path,sha in f['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Changed frozen input '+path)
    e=previous_evidence();spec=next_selection(e)
    if spec!=json.loads((ROOT/'last-selected-leg.json').read_text()):raise ValueError('Changed frozen selection')
    if spec['state']['originalSequence']!=299650 or spec['maxNewReceiptRequests']!=19:
        raise ValueError('Only the final selected19-receipt leg is authorized')
    collect(spec,a.output)
    out=Path(a.output);report=json.loads((out/'report.json').read_text())
    for t in spec['transactions']:
        tx=t['transactionHash'];data=json.loads((out/'raw'/(tx+'.json')).read_text())
        if tx in e:raise ValueError('Do not double count existing transaction')
        e[tx]=dict(data=data,topics=report['eventTopics'])
    r=coverage(e);(out/'complete-selected-legs-coverage.json').write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps(r),flush=True)


if __name__=='__main__':main()
