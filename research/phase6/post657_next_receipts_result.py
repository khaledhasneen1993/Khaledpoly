"""Verify exact657-next receipts without converting price compatibility into fills."""
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import zipfile

from research.phase6.post657_next_receipts import selection,decode
from research.phase6.post655_next_receipts import digest
from research.phase6.post655_pool_replay_result import ROOT as REPLAY_ROOT

ROOT=Path('research/experiments/post657-next-receipts-20261023')
ZIP_SHA='8558b5feca3d6e7d544ccee9031e2e6d41665e981e043f7d23c0421812635508'


def require(value,why):
    if not value:raise ValueError(why)


def verify(spec,raws,report):
    require(spec==selection(),'Changed exact657 next receipt targets')
    require(report['scope']==spec['scope'] and report['complete'] is True and not report['errors'] and report['rpcCalls']=={'eth_chainId':1,'eth_getTransactionReceipt':2,'eth_getBlockByHash':2},'Changed bounded read provenance')
    for key in ('candidateAccountSimulated','nativePoolExtended','completeAccountComparisonPerformed','marketNetPnlRecomputed','independentPaperQualificationAllowed','liveAllowed'):require(report[key] is False,'Receipt result promoted '+key)
    require(report['modelFillsCreated']==0 and len(report['results'])==2 and set(raws)=={x['transactionHash'] for x in spec['transactions']},'Wrong receipt/fill count')
    results=[]
    with zipfile.ZipFile(REPLAY_ROOT/'ci-artifact.zip') as replay:
        for item,saved in zip(spec['transactions'],report['results']):
            tx=item['transactionHash'];raw=raws[tx]
            require(saved['transactionHash']==tx and saved['profile']==item['profile'] and saved['seq']==item['seq'] and saved['rawSha256']==digest(raw),'Changed raw receipt identity/hash')
            route=decode(spec,item,json.loads(raw));require(route==saved['route'] and route['queueAllocationProven'] is False and route['fillsCreated']==0,'Raw conserved route differs')
            group=route['matchingGroups'][0];failure=json.loads(replay.read('development/'+item['profile']+'/failure.json'));orders=failure['sessionAfterSuspension']['makerExecutionDiagnostics'];comparisons=[];eligible_volume=D(0);eligible_queues=[]
            for part in group['components']:
                eligible=[]
                for order in orders:
                    source_after=int(item['sample']['timestamp'])>order['activatedMs'];side=order['buy']==(part['makerSide']=='BUY');token=order['token']==part['makerToken'];left=D(str(order['price']))*D(part['sharesRaw']);right=D(part['collateralRaw']);price=left>=right if order['buy'] else left<=right
                    if source_after and side and token and price:
                        eligible.append(order['id']);eligible_volume+=D(part['sharesRaw']);eligible_queues.append(D(str(order['remainingQueueAhead']))*D(1_000_000))
                comparisons.append(dict(makerLogIndex=part['makerLogIndex'],route=part['route'],makerSide=part['makerSide'],makerToken=part['makerToken'],makerPrice=part['makerPrice'],sharesRaw=part['sharesRaw'],eligibleRecordedOrdersByNecessaryConditions=eligible))
            queue_cleared=bool(eligible_queues) and eligible_volume>min(eligible_queues)
            require(not queue_cleared,'Price-compatible exact657 evidence unexpectedly clears queue')
            if item['profile']=='candidate':
                require(eligible_volume==D(9_550_000) and min(eligible_queues)==D(1_182_300_000),'Changed candidate price-compatible volume/queue')
            else:require(eligible_volume==0 and not eligible_queues,'Baseline receipt unexpectedly matches an active order')
            results.append(dict(profile=item['profile'],condition=item['sample']['market'],sourceCoordinate=[item['seq'],item['eventIndex']],transactionHash=tx,publicTradeIdSha256=item['publicTradeIdSha256'],rawReceiptSha256=digest(raw),conservedMakerComponents=len(group['components']),venueSharesRaw=group['sharesRaw'],takerCollateralRaw=group['collateralRaw'],routeSharesRaw=group['routeSharesRaw'],componentQuoteComparisons=comparisons,priceCompatibleVenueSharesRaw=int(eligible_volume),minimumQueueAheadSharesRaw=int(min(eligible_queues)) if eligible_queues else None,queueCleared=False,counterfactualQueueAllocationProven=False,modelFillsCreated=0))
    require(sum(x['conservedMakerComponents'] for x in results)==3,'Changed actual component count')
    return dict(scope='VERIFIED_EXACT657_NEXT_TWO_RECEIPT_ROUTES_NOT_BOT_FILLS_OR_ACCOUNT',sourceCommit='2c9e3cae0e4d4060493b040fadd89e99d8c4c21c',runId=39880064108,jobId=120175016072,artifactId=12469689574,artifactSha256=ZIP_SHA,results=results,conservedMakerComponents=3,sourceObservationIdentitiesVerified=True,nativePoolExtended=False,newRuntimeShortcutEnabled=False,modelFillsCreated=0,marketNetPnlRecomputed=False,completeAccountComparisonPerformed=False,independentPaperQualificationAllowed=False,liveAllowed=False,decision='NO_GO',nextStep='Extend a separately frozen659-binding/1562-component pool preserving all657; prove native/source parity before another replay.')


def load(path=None):
    path=Path(path) if path is not None else ROOT/'ci-artifact.zip';raw=path.read_bytes();require(len(raw)==15882 and hashlib.sha256(raw).hexdigest()==ZIP_SHA,'Changed exact657-next receipt archive')
    expected=selection();names={'selection.json','report.json'}|{'raw/'+x['transactionHash']+'.json' for x in expected['transactions']}
    with zipfile.ZipFile(path) as z:
        require(len(z.infolist())==4 and set(z.namelist())==names and all(m.file_size<1024*1024 for m in z.infolist()),'Unexpected bounded receipt archive')
        return json.loads(z.read('selection.json')),{x['transactionHash']:z.read('raw/'+x['transactionHash']+'.json') for x in expected['transactions']},json.loads(z.read('report.json'))


if __name__=='__main__':print(json.dumps(verify(*load()),indent=2))
