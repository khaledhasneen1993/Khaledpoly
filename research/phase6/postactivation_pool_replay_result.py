"""Revalidate retained exact645 same-source failures; never promote prefix cash to PnL."""
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path('research/experiments/postactivation-replay-20261020')
ZIP_SHA='ae76233de5e1ec7f209508aca9499afa2cf98184f173c4d398f8424d837b40a3'
EXPECTED={
    'candidate':dict(seq=9060,at=1792269594591,sourceMs=1792269594522,token='12589566430666404778428222777978747623958961794906352412512658324998006663268',side='BUY',price='0.52',size='38.461539',transactionHash='0x1e466a61b791aaf8b510dcf9ebc8a53c24efd67e866ab994a2044da81a02f651',sourceConsumed=100,poolConsumed=2,known=2,components=17,venue='203.846154',activeMs=88,queues=('1182.3','180')),
    'baseline':dict(seq=82986,at=1792269639697,sourceMs=1792269639627,token='88599287360325233240690982088109814021050513475420535621672707507474151524334',side='BUY',price='0.32',size='40',transactionHash='0xc9b48a2f8ed8998a334469807f4fa141b82e7848e10f86f27f2495e0bcf27621',sourceConsumed=839,poolConsumed=3,known=3,components=18,venue='212.846154',activeMs=112,queues=('0','0')),
}


def require(x,why):
    if not x:raise ValueError(why)


def verify(path=ROOT/'ci-artifact.zip'):
    raw=Path(path).read_bytes();require(hashlib.sha256(raw).hexdigest()==ZIP_SHA,'Changed exact645 replay artifact')
    with zipfile.ZipFile(path) as z:
        names=z.namelist();require(len(names)==15 and len(set(names))==15 and all(m.file_size<1024*1024 for m in z.infolist()),'Unexpected replay archive')
        summary=json.loads(z.read('development/summary.json'));require(summary==json.loads((ROOT/'summary.json').read_bytes()),'Changed retained replay summary')
        require(summary['scope']=='ONE_SAME_ORIGINAL_DEVELOPMENT_EXACT645_BASELINE_QW0_NOT_QUALIFICATION' and summary['poolLogicalSha256']=='16dab5fa70b908ccb5c7aeaaba803f2c5ac4f66b0efa50de6b2d1b82c0d662c7','Wrong replay source/pool scope')
        require(summary['completeAccountComparisonPerformed'] is False and summary['independentPaperQualificationAllowed'] is False and summary['liveAllowed'] is False and summary['decision']=='NO_GO','Failed replay promoted')
        targets={}
        for profile,e in EXPECTED.items():
            result=summary['results'][profile];f=json.loads(z.read(f'development/{profile}/failure.json'));labels=f['labels'];session=f['sessionAfterSuspension'];ledger=f['ledgerAfterSuspension'];attempt=labels['lastAttemptedOriginalObservation'];obs=attempt['observation'];trade=json.loads(obs['tradeId'])
            require(result['status']=='INCOMPLETE_FAIL_CLOSED_NOT_PNL_RESULT' and result['marketNetPnlRecomputed'] is False and result['sourceConsumed']==e['sourceConsumed'] and result['knownReceiptBindingsConsumed']==e['poolConsumed'],'Wrong incomplete result counters')
            require(f['errors']==['IllegalStateException: Eligible/invalid/cancel/sell order cannot use source-lag witness'] and f['row']=={'kind':'RESEARCH_FRAME','seq':e['seq'],'arrivalMs':e['at']} and attempt['seq']==e['seq'] and attempt['eventIndex']==0 and attempt['at']==e['at'],'Wrong next blocker')
            require(obs['sourceMs']==e['sourceMs'] and obs['token']==e['token'] and obs['side']==e['side'] and D(str(obs['price']))==D(e['price']) and D(str(obs['size']))==D(e['size']) and trade['transaction_hash']==e['transactionHash'],'Wrong next original identity')
            pool=labels['realReceiptPool'];source=labels['sourceIndex'];require(pool['bindings']==645 and pool['actualComponents']==1534 and pool['consumedBindings']==e['poolConsumed'] and source['consumedOriginalPreimages']==e['sourceConsumed'] and labels['knownAppliedObservations']==e['known'],'Wrong native consumption')
            volume=session['settlementVolumeConservation'];require(volume['uniqueMakerComponents']==e['components'] and D(str(volume['venueQuantity']))==D(e['venue']) and D(str(volume['allocatedQuantity']))==0 and D(str(volume['queueAbsorbed']))==0 and D(str(volume['unusedQuantity']))==D(e['venue']),'Known volume not conserved')
            orders=session['makerExecutionDiagnostics'];require(len(orders)==2 and all(o['activeMs']==e['activeMs'] and o['terminalReason']=='DATA_GAP:unknown' and D(str(o['eligiblePrintVolume']))==0 and D(str(o['remainingShares']))==5 for o in orders),'Order lifetime differs')
            require(tuple(str(o['remainingQueueAhead']) for o in orders)==e['queues'],'Actual queues differ')
            require(session['halted'] is True and session['openOrderCount']==0 and not session['executions'] and not session['holdings'] and D(str(session['cash']))==500 and D(str(session['feesAndSettlementCosts']))==0,'Unsafe account suspension')
            require(ledger['halted'] is True and not ledger['executions'] and not ledger['holdings'] and D(str(ledger['cash']))==500 and D(str(ledger['realized']))==0 and D(str(ledger['fees']))==0 and all(o['status']=='CANCELED' and D(str(o['filled']))==0 for o in ledger['orders'].values()),'Ledger suspension differs')
            targets[profile]=dict(seq=e['seq'],eventIndex=0,at=e['at'],sourceMs=e['sourceMs'],transactionHash=e['transactionHash'],token=e['token'],side=e['side'],price=e['price'],size=e['size'])
    return dict(scope='VERIFIED_EXACT645_NEXT_TWO_RECEIPT_BLOCKERS_NOT_ACCOUNT_RESULT',runId=39479346181,jobId=118823518285,artifactId=12290241861,artifactSha256=ZIP_SHA,
        results={p:dict(sourceConsumed=e['sourceConsumed'],knownReceiptBindingsConsumed=e['poolConsumed'],knownComponents=e['components'],knownVenueQuantity=e['venue'],activeMs=e['activeMs'],actualQueues=list(e['queues'])) for p,e in EXPECTED.items()},
        nextReceiptTargets=targets,modelFills=0,completeAccountComparisonPerformed=False,marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False,decision='NO_GO')


if __name__=='__main__':print(json.dumps(verify(),indent=2))
