"""Offline verification of exact653-next receipts; never infer bot fills."""
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import zipfile

from research.phase6.post653_next_receipts import selection,decode,digest
from research.phase6.post651_pool_replay_result import ROOT as REPLAY_ROOT

ROOT=Path('research/experiments/post653-next-receipts-20261022')
ZIP_SHA='3f9febab2dbc952e6ea6d8c072b417d8df6bc80b9b07f608814da940130b1bdd'


def require(value,why):
    if not value:raise ValueError(why)


def verify(spec,raws,report):
    require(spec==selection(),'Changed exact653 next receipt targets')
    require(report['scope']==spec['scope'] and report['complete'] is True and not report['errors'] and report['rpcCalls']=={'eth_chainId':1,'eth_getTransactionReceipt':2,'eth_getBlockByHash':2},'Changed bounded read provenance')
    for key in ('candidateAccountSimulated','nativePoolExtended','completeAccountComparisonPerformed','marketNetPnlRecomputed','independentPaperQualificationAllowed','liveAllowed'):require(report[key] is False,'Receipt result promoted '+key)
    require(report['modelFillsCreated']==0 and len(report['results'])==2 and set(raws)=={x['transactionHash'] for x in spec['transactions']},'Wrong receipt/fill count')
    results=[]
    with zipfile.ZipFile(REPLAY_ROOT/'ci-artifact.zip') as replay:
        for item,saved in zip(spec['transactions'],report['results']):
            tx=item['transactionHash'];raw=raws[tx]
            require(saved['transactionHash']==tx and saved['profile']==item['profile'] and saved['seq']==item['seq'] and saved['rawSha256']==digest(raw),'Changed raw receipt identity/hash')
            route=decode(spec,item,json.loads(raw));require(route==saved['route'] and route['queueAllocationProven'] is False and route['fillsCreated']==0,'Raw conserved route differs')
            group=route['matchingGroups'][0];failure=json.loads(replay.read('development/'+item['profile']+'/failure.json'));orders=failure['sessionAfterSuspension']['makerExecutionDiagnostics'];comparisons=[]
            for part in group['components']:
                eligible=[]
                for order in orders:
                    source_after=int(item['sample']['timestamp'])>order['activatedMs'];side=order['buy']==(part['makerSide']=='BUY');token=order['token']==part['makerToken'];left=D(str(order['price']))*part['sharesRaw'];right=D(part['collateralRaw']);price=left>=right if order['buy'] else left<=right
                    if source_after and side and token and price:eligible.append(order['id'])
                comparisons.append(dict(makerLogIndex=part['makerLogIndex'],route=part['route'],makerSide=part['makerSide'],makerToken=part['makerToken'],makerPrice=part['makerPrice'],sharesRaw=part['sharesRaw'],eligibleRecordedOrdersByNecessaryConditions=eligible))
            require(all(not x['eligibleRecordedOrdersByNecessaryConditions'] for x in comparisons),'These exact receipts no longer exclude recorded quotes')
            results.append(dict(profile=item['profile'],condition=item['sample']['market'],sourceCoordinate=[item['seq'],item['eventIndex']],transactionHash=tx,publicTradeIdSha256=item['publicTradeIdSha256'],rawReceiptSha256=digest(raw),conservedMakerComponents=len(group['components']),venueSharesRaw=group['sharesRaw'],takerCollateralRaw=group['collateralRaw'],routeSharesRaw=group['routeSharesRaw'],componentQuoteComparisons=comparisons,noRecordedOrderPassesNecessaryMatchingConditions=True,counterfactualQueueAllocationProven=False,modelFillsCreated=0))
    require(sum(x['conservedMakerComponents'] for x in results)==4,'Changed actual component count')
    return dict(scope='VERIFIED_EXACT653_NEXT_TWO_RECEIPT_ROUTES_NOT_BOT_FILLS_OR_ACCOUNT',sourceCommit='7bbdb677202906abface96f43b53c37c335ae95b',runId=39823548337,jobId=119980758578,artifactId=12444908879,artifactSha256=ZIP_SHA,results=results,conservedMakerComponents=4,sourceObservationIdentitiesVerified=True,nativePoolExtended=False,newRuntimeShortcutEnabled=False,modelFillsCreated=0,marketNetPnlRecomputed=False,completeAccountComparisonPerformed=False,independentPaperQualificationAllowed=False,liveAllowed=False,decision='NO_GO',nextStep='Extend a separately frozen655-binding/1557-component pool preserving all653; prove native/source parity before another replay.')


def load(path=None):
    path=Path(path) if path is not None else ROOT/'ci-artifact.zip';raw=path.read_bytes();require(len(raw)==15899 and hashlib.sha256(raw).hexdigest()==ZIP_SHA,'Changed exact653-next receipt archive')
    expected=selection();names={'selection.json','report.json'}|{'raw/'+x['transactionHash']+'.json' for x in expected['transactions']}
    with zipfile.ZipFile(path) as z:
        require(len(z.infolist())==4 and set(z.namelist())==names and all(m.file_size<1024*1024 for m in z.infolist()),'Unexpected bounded receipt archive')
        return json.loads(z.read('selection.json')),{x['transactionHash']:z.read('raw/'+x['transactionHash']+'.json') for x in expected['transactions']},json.loads(z.read('report.json'))


if __name__=='__main__':print(json.dumps(verify(*load()),indent=2))
