"""Offline re-derivation from raw public receipts, NEVER reported parts trusted as fills."""
import argparse
from decimal import Decimal as D
import json
from pathlib import Path
import zipfile
from research.phase6.postactivation_receipts import selection,decode,digest
from research.phase6.source_lag_guard_diagnosis import ROOT as SOURCE

ROOT=Path('research/experiments/postactivation-receipts-20261020')
ZIP_SHA='b18b80b960a5de5273197fc04460f4a70224ead77d0307827c494ba5a4337e79'


def require(x,why):
    if not x:raise ValueError(why)


def verify(spec,raws,report):
    require(spec==selection(),'Changed exact original targets')
    require(report['scope']==spec['scope'] and report['complete'] is True and not report['errors'] and report['rpcCalls']=={'eth_chainId':1,'eth_getTransactionReceipt':2,'eth_getBlockByHash':2},'Changed bounded read provenance')
    for k in ('candidateAccountSimulated','nativePoolExtended','completeAccountComparisonPerformed','marketNetPnlRecomputed','independentPaperQualificationAllowed','liveAllowed'):require(report[k] is False,'Receipt result promoted '+k)
    require(report['modelFillsCreated']==0 and len(report['results'])==2 and set(raws)=={x['transactionHash'] for x in spec['transactions']},'Wrong receipt/fill count')
    results=[]
    with zipfile.ZipFile(SOURCE/'ci-artifact.zip') as z:
        for item,saved in zip(spec['transactions'],report['results']):
            tx=item['transactionHash'];raw=raws[tx];require(saved['transactionHash']==tx and saved['profile']==item['profile'] and saved['seq']==item['seq'] and saved['rawSha256']==digest(raw),'Changed raw receipt identity/hash')
            route=decode(spec,item,json.loads(raw));require(route==saved['route'] and route['queueAllocationProven'] is False and route['fillsCreated']==0,'Raw conserved route differs')
            group=route['matchingGroups'][0];old=json.loads(z.read('development/'+item['profile']+'/failure.json'));orders=old['sessionAfterSuspension']['makerExecutionDiagnostics'];comparisons=[]
            for part in group['components']:
                eligible=[]
                for o in orders:
                    # Necessary exact matching conditions only; no inference about queue allocation.
                    source_after=int(item['sample']['timestamp'])>o['activatedMs']
                    side=o['buy']==(part['makerSide']=='BUY');token=o['token']==part['makerToken']
                    left=D(str(o['price']))*part['sharesRaw'];right=D(part['collateralRaw'])
                    price=left>=right if o['buy'] else left<=right
                    if source_after and side and token and price:eligible.append(o['id'])
                comparisons.append(dict(makerLogIndex=part['makerLogIndex'],makerSide=part['makerSide'],makerToken=part['makerToken'],makerPrice=part['makerPrice'],sharesRaw=part['sharesRaw'],eligibleRecordedOrdersByNecessaryConditions=eligible))
            # This is a receipt-specific identity/side/price refusal, NOT a new runtime shortcut.
            require(all(not r['eligibleRecordedOrdersByNecessaryConditions'] for r in comparisons),'These exact receipts no longer exclude recorded quotes')
            results.append(dict(profile=item['profile'],sourceCoordinate=[item['seq'],item['eventIndex']],transactionHash=tx,publicTradeIdSha256=item['publicTradeIdSha256'],rawReceiptSha256=digest(raw),conservedMakerComponents=len(group['components']),venueSharesRaw=group['sharesRaw'],takerCollateralRaw=group['collateralRaw'],routeSharesRaw=group['routeSharesRaw'],componentQuoteComparisons=comparisons,noRecordedOrderPassesNecessaryMatchingConditions=True,counterfactualQueueAllocationProven=False,modelFillsCreated=0))
    require(sum(r['conservedMakerComponents'] for r in results)==2,'Changed actual component count')
    return dict(scope='VERIFIED_TWO_ORIGINAL_RECEIPT_ROUTES_NOT_BOT_FILLS_OR_ACCOUNT',sourceCommit='1f2c7e9d0f1897ace68c0665b943663fd883f381',runId=39468514569,artifactId=12286053123,artifactSha256=ZIP_SHA,results=results,conservedMakerComponents=2,sourceObservationIdentitiesVerified=True,nativePoolExtended=False,newRuntimeShortcutEnabled=False,modelFillsCreated=0,marketNetPnlRecomputed=False,completeAccountComparisonPerformed=False,independentPaperQualificationAllowed=False,liveAllowed=False,decision='NO_GO',nextStep='Build a separately frozen645-binding/1534-component real pool preserving all643 existing bindings, verify native parity and source identities before ONE new baseline/QW0 replay. Do not tune strategy/holdout, infer fills, weaken queue or repeat the unchanged source run.')


def load(path=None):
    path=Path(path) if path is not None else ROOT/'ci-artifact.zip';raw=path.read_bytes()
    require(len(raw)==15018 and digest(raw)==ZIP_SHA,'Changed two-receipt archive')
    expected=selection();names={'selection.json','report.json'}|{'raw/'+x['transactionHash']+'.json' for x in expected['transactions']}
    with zipfile.ZipFile(path) as z:
        require(len(z.infolist())==4 and set(z.namelist())==names and all(m.file_size<1024*1024 for m in z.infolist()),'Unexpected bounded receipt archive')
        return json.loads(z.read('selection.json')),{x['transactionHash']:z.read('raw/'+x['transactionHash']+'.json') for x in expected['transactions']},json.loads(z.read('report.json'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path);a=p.parse_args();print(json.dumps(verify(*load(a.archive)),indent=2))
