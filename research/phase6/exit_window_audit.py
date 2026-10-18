"""Bounded public-read window, not an invented virtual-order lifetime."""
import argparse
import base64
import gzip
import hashlib
import io
import json
from collections import Counter
from pathlib import Path
import time
import zipfile
from research.phase6.receipt_audit import corroborate, event_topics, rpc
from research.phase6.route_coverage_audit import routes

ROOT = Path('research/experiments/exit-window-selection-20261018')


def validate(selection, frames):
    rows = selection['transactions']; window = selection['window']
    if len(rows) != 9 or len(frames) != 9 or len({x['transactionHash'] for x in rows}) != 9:
        raise ValueError('Require all nine original distinct window observations')
    for item, frame in zip(rows,frames):
        raw = frame['raw']; normal = frame['normalized']; sample = item['sample']
        if hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(',',':')).encode()).hexdigest() != frame['canonicalRawRowSha256']:
            raise ValueError('Original RAW hash differs')
        message = json.loads(raw['data']['text'])
        event = next(e for e in normal['data']['events'] if e['originalEventIndex'] == item['originalEventIndex'])
        data = event['data']
        if (dict(message,arrivalMs=normal['arrivalMs']) != sample or event['kind'] != 'TRADE'
                or normal['seq'] != item['normalizedSeq'] or normal['data']['frameId'] != raw['data']['frameId']
                or raw['arrivalMs'] != normal['arrivalMs'] or json.loads(data['tradeId']) != message
                or item['transactionHash'] != message['transaction_hash'] or data['side'] != sample['side']
                or data['token'] != sample['asset_id'] or data['sourceMs'] != int(sample['timestamp'])
                or data['size'] != sample['size'] or data['price'] != sample['price']
                or sample['side'] != 'BUY' or sample['asset_id'] != selection['originalObservedOrderDiagnostic']['token']
                or not window['startInclusiveMs'] <= int(sample['timestamp']) <= sample['arrivalMs'] < window['endExclusiveMs']):
            raise ValueError('Window observation identity/time differs')


def seed_cache(output, selection):
    encoded = Path('research/experiments/exit-trigger-audit-20261018/artifact.zip.b64').read_bytes()
    raw = base64.b64decode(b''.join(encoded.split()),validate=True)
    if hashlib.sha256(raw).hexdigest() != selection['existingReceiptArtifactZipSha256']:
        raise ValueError('Existing receipt archive changed')
    folder = Path(output)/'raw';folder.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if len(z.namelist()) != 5 or sum(x.file_size for x in z.infolist()) > 100000:
            raise ValueError('Unexpected cached archive size')
        for tx in selection['existingReceiptTransactions']:
            target=folder/(tx+'.json');original=z.read('raw/'+tx+'.json')
            if target.exists() and target.read_bytes() != original:
                raise ValueError('Existing receipt output conflicts with original cache')
            if not target.exists():target.write_bytes(original)


def collect_window(selection, frames, output, *, topics=None, read=rpc):
    validate(selection,frames)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    canonical=(json.dumps(selection,sort_keys=True,separators=(',',':'))+'\n').encode()
    checkpoint=output/'selection.json'
    if checkpoint.exists() and checkpoint.read_bytes() != canonical:
        raise ValueError('Resume window selection differs')
    if not checkpoint.exists():checkpoint.write_bytes(canonical)
    seed_cache(output,selection)
    topics=topics or event_topics();calls=Counter();blocks={};results=[];errors=[]
    def query(method,params):calls[method]+=1;return read(method,params)
    if int(query('eth_chainId',[]),16) != 137:raise ValueError('Wrong public chain')
    pair=set(json.loads(Path('research/phase6/route-coverage-freeze.json').read_text())['pair'])
    for item in selection['transactions']:
        tx=item['transactionHash'];target=output/'raw'/(tx+'.json')
        try:
            if target.exists():data=json.loads(target.read_text());origin='CACHE'
            else:
                if calls['eth_getTransactionReceipt'] >= selection['maxNewReceiptRequests']:
                    raise ValueError('Seven-receipt budget exhausted')
                time.sleep(.5);receipt=query('eth_getTransactionReceipt',[tx])
                if not receipt:raise ValueError('Missing public receipt')
                h=receipt['blockHash'].lower()
                if h not in blocks:blocks[h]=query('eth_getBlockByHash',[receipt['blockHash'],False])
                data=dict(receipt=receipt,block=blocks[h]);origin='PUBLIC_READ'
                target.write_text(json.dumps(data,separators=(',',':'))+'\n')
            blocks[data['block']['hash'].lower()]=data['block']
            result=corroborate(item['sample'],data['receipt'],data['block'],topics)
            result.update(routeConservation=routes(result,pair),receiptOrigin=origin)
            if not result['routeConservation']['uniqueConservedGroup']:
                raise ValueError('Ambiguous window settlement identity')
            results.append(result)
        except (OSError,ValueError,KeyError,TypeError) as error:
            errors.append(dict(transactionHash=tx,error=str(error)[:200]))
    report=dict(scope=selection['scope'],collectionWindow=selection['window'],notObservedOrderLifetime=True,
                requested=9,corroborated=len(results),complete=len(results)==9 and not errors,
                results=results,errors=errors,eventTopics=topics,rpcCalls=dict(calls),
                queueAllocationProven=False,fillsCreated=0,netPnlRecomputed=False,
                independentPaperQualificationAllowed=False,liveAllowed=False,decision='NO_GO')
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
    freeze=json.loads(Path('research/phase6/exit-window-freeze.json').read_text())
    for path,digest in freeze['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:
            raise ValueError('Frozen window audit changed: '+path)
    selection=json.loads((ROOT/'selection.json').read_text())
    frames=json.loads(gzip.decompress(base64.b64decode((ROOT/'original-frames.json.gz.b64').read_bytes())))
    report=collect_window(selection,frames,args.output)
    print(json.dumps({k:v for k,v in report.items() if k not in ('results','eventTopics')}),flush=True)
    if not report['complete']:raise SystemExit('Incomplete; retain successes and retry missing receipts only')


if __name__ == '__main__':main()
