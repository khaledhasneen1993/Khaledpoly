"""Re-derive the one actual first-blocker route from retained raw receipt+block."""
import argparse
import io
import json
from pathlib import Path
import zipfile
from research.phase6.first_blocker_receipt import selection,decode,digest

ROOT=Path('research/experiments/first-blocker-receipt-20261020')
SHA='5d8bf1e09bd0a5ed2210a43e256e90b0122c36dc48aeac36427f9ee528c956aa'

def verify(spec,raw,report):
    if spec!=selection():raise ValueError('Changed exact original source selection')
    if (report['scope']!=spec['scope'] or report['complete'] is not True
            or report['rpcCalls']!={'eth_chainId':1,'eth_getTransactionReceipt':1,'eth_getBlockByHash':1}
            or report['rawSha256']!=digest(raw)):
        raise ValueError('Changed raw receipt/public request provenance')
    for key in ('marketNetPnlRecomputed','candidateAccountSimulated','independentPaperQualificationAllowed','liveAllowed'):
        if report[key] is not False:raise ValueError('Receipt cannot become account/qualification evidence')
    if report['modelFillsCreated']!=0:raise ValueError('No model fills permitted')
    actual=decode(spec,json.loads(raw))
    if actual!=report['route'] or actual['queueAllocationProven'] is not False or actual['fillsCreated']!=0:
        raise ValueError('Raw conserved components differ from reported route')
    group=actual['matchingGroups'][0]
    return dict(scope='VERIFIED_ONE_ORIGINAL_RECEIPT_ROUTE_NOT_BOT_FILLS',
        sourceCoordinate=[spec['seq'],spec['eventIndex']],transactionHash=spec['transactionHash'],
        conservedMakerComponents=len(group['components']),venueSharesRaw=group['sharesRaw'],
        takerCollateralRaw=group['collateralRaw'],routeSharesRaw=group['routeSharesRaw'],
        rawReceiptSha256=digest(raw),sourceObservationIdentityVerified=True,
        nativePoolExtended=False,counterfactualQueueAllocationProven=False,
        modelFillsCreated=0,marketNetPnlRecomputed=False,
        completeAccountComparisonPerformed=False,independentPaperQualificationAllowed=False,liveAllowed=False)

def load(path=ROOT/'artifact.zip'):
    raw=Path(path).read_bytes()
    if digest(raw)!=SHA:raise ValueError('Changed one-receipt artifact')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if len(z.infolist())!=3 or set(z.namelist())!={'selection.json','raw.json','report.json'} or any(m.file_size>1024*1024 for m in z.infolist()):
            raise ValueError('Unexpected bounded one-receipt archive')
        args=(json.loads(z.read('selection.json')),z.read('raw.json'),json.loads(z.read('report.json')))
    return args

if __name__=='__main__':
    print(json.dumps(verify(*load()),indent=2))
