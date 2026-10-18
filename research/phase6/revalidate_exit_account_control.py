"""Reproduce the archived account comparison without rerunning or altering a ledger."""
import base64
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import zipfile
from research.phase6.historical_source_proof import verify_historical_sources

ROOT = Path('research/experiments/exit-covered-replay-20261018/result')
ZIP_SHA = 'c3f46b928b6cb150356c44317737975bf8d798c9418af9b1015550889750dbb6'


def revalidate(archive=ROOT / 'artifact.zip.b64'):
    encoded = Path(archive).read_bytes()
    if len(encoded) > 400000:
        raise ValueError('Oversized account evidence')
    raw = base64.b64decode(b''.join(encoded.split()),validate=True)
    if hashlib.sha256(raw).hexdigest() != ZIP_SHA:
        raise ValueError('Original account artifact hash changed')
    frozen = json.loads(Path('research/phase6/exit-covered-replay-freeze.json').read_text())
    verify_historical_sources(frozen)
    expected = {'comparison.json','baseline/report.json','baseline/audit.jsonl',
                'candidate/report.json','candidate/audit.jsonl'}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if (set(z.namelist()) != expected or len(z.namelist()) != 5
                or sum(x.file_size for x in z.infolist()) > 8000000):
            raise ValueError('Unexpected account archive membership/size')
        comparison = json.loads(z.read('comparison.json'))
        if z.read('comparison.json') != (ROOT / 'comparison.original.json').read_bytes():
            raise ValueError('Original comparison changed')
        summaries = {}
        for mode, variant in frozen['variants'].items():
            report = json.loads(z.read(mode+'/report.json'))
            if any(report.get(k) != v for k,v in comparison['variants'][mode].items()):
                raise ValueError('Original report/comparison differ')
            labels = report['settlementExperiment']
            if (labels['consumedBindings'] != variant['bindings'] or labels['labelBindings'] != variant['bindings']
                    or report['inputSha256'] != frozen['inputSha256']
                    or report['configSha256'] != frozen['configSha256']
                    or labels['logicalTapeSha256'] != frozen['logicalTapeSha256']
                    or report['independentPaperQualificationAllowed']):
                raise ValueError('Coverage or provenance differs')
            audit_fills = [json.loads(line)['data'] for line in z.read(mode+'/audit.jsonl').splitlines()
                           if json.loads(line)['kind'] == 'FILL']
            for execution in report['executions']:
                matched = [f for f in audit_fills if f['id'] == execution['orderId'] and f['at'] == execution['at']]
                if len(matched) != 1 or any(matched[0][k] != execution[k] for k in ('token','buy','price','size')):
                    raise ValueError('Audit execution does not match report')
            volume = report['settlementVolumeConservation']
            if (Decimal(str(volume['venueQuantity'])) != sum(Decimal(str(volume[k])) for k in
                    ('allocatedQuantity','queueAbsorbed','unusedQuantity'))):
                raise ValueError('Account component volume does not conserve')
            summaries[mode] = dict(netRealizedPnl=report['netRealizedPnl'],cash=report['cash'],
                fills=report['fills'],feesAndSettlementCosts=report['feesAndSettlementCosts'],
                maxDrawdown=report['maxDrawdown'],quantityPairCompletion=report['quantityPairCompletion'],
                residualExpiryWorstCaseNotional=report['residualExpiryWorstCaseNotional'],
                finalFillMs=report['executions'][-1]['at'],
                missingMarkoutsByReason=report['missingMarkoutsByReason'],settlementVolumeConservation=volume)
    return dict(variants=summaries,finalFillDelayMs=summaries['candidate']['finalFillMs']-summaries['baseline']['finalFillMs'],
                networkRequests=0,accountReruns=0,independentPaperQualificationAllowed=False,decision='NO_GO')


if __name__ == '__main__':
    print(json.dumps(revalidate(),indent=2))
