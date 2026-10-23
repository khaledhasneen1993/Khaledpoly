"""Verify exact661-next receipts without promoting necessary quote conditions to fills."""
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import zipfile

from research.phase6.post661_next_receipts import selection,decode
from research.phase6.post655_next_receipts import digest
from research.phase6.post659_pool_replay_result import ROOT as REPLAY_ROOT

ROOT=Path('research/experiments/post661-next-receipts-20261023')
ZIP_SHA='73f345474c5282c24c5d617dc6a151c2d840ee0cf2cf1b7712dcb689ce932330'


def require(value,why):
    if not value:raise ValueError(why)


def verify(spec,raws,report):
    require(spec==selection(),'Changed exact661 next receipt targets')
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
            threshold=bool(eligible_queues) and eligible_volume>min(eligible_queues)
            expected=(D(0),None,False) if item['profile']=='candidate' else (D(35_882_353),D(0),True)
            actual=(eligible_volume,min(eligible_queues) if eligible_queues else None,threshold)
            require(actual==expected,'Changed exact661 necessary price/queue conditions')
            results.append(dict(profile=item['profile'],condition=item['sample']['market'],sourceCoordinate=[item['seq'],item['eventIndex']],transactionHash=tx,publicTradeIdSha256=item['publicTradeIdSha256'],rawReceiptSha256=digest(raw),conservedMakerComponents=len(group['components']),venueSharesRaw=group['sharesRaw'],takerCollateralRaw=group['collateralRaw'],routeSharesRaw=group['routeSharesRaw'],componentQuoteComparisons=comparisons,priceCompatibleVenueSharesRaw=int(eligible_volume),minimumQueueAheadSharesRaw=int(min(eligible_queues)) if eligible_queues else None,necessaryQueueClearanceThresholdExceeded=threshold,necessaryConditionsOnly=True,counterfactualQueueAllocationProven=False,modelFillsCreated=0))
    require(sum(x['conservedMakerComponents'] for x in results)==10,'Changed actual component count')
    return dict(scope='VERIFIED_EXACT661_NEXT_TWO_RECEIPT_ROUTES_NOT_BOT_FILLS_OR_ACCOUNT',sourceCommit='8f344683943fc6eb36e8496929906e54e668c0c7',runId=39947597650,jobId=120393955041,artifactId=12498488616,artifactSha256=ZIP_SHA,results=results,conservedMakerComponents=10,sourceObservationIdentitiesVerified=True,nativePoolExtended=False,newRuntimeShortcutEnabled=False,modelFillsCreated=0,marketNetPnlRecomputed=False,completeAccountComparisonPerformed=False,independentPaperQualificationAllowed=False,liveAllowed=False,decision='NO_GO',nextStep='Extend a separately frozen663-binding/1574-component pool preserving all661; prove native/source parity before another replay.')


def load(path=None):
    path=Path(path) if path is not None else ROOT/'ci-artifact.zip';raw=path.read_bytes();require(len(raw)==16887 and hashlib.sha256(raw).hexdigest()==ZIP_SHA,'Changed exact661-next receipt archive')
    expected=selection();names={'selection.json','report.json'}|{'raw/'+x['transactionHash']+'.json' for x in expected['transactions']}
    with zipfile.ZipFile(path) as z:
        require(len(z.infolist())==4 and set(z.namelist())==names and all(m.file_size<1024*1024 for m in z.infolist()),'Unexpected bounded receipt archive')
        return json.loads(z.read('selection.json')),{x['transactionHash']:z.read('raw/'+x['transactionHash']+'.json') for x in expected['transactions']},json.loads(z.read('report.json'))


if __name__=='__main__':print(json.dumps(verify(*load()),indent=2))
