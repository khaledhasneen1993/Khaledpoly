"""Revalidate retained exact661 same-source failures; never promote prefix cash to PnL."""
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path('research/experiments/post659-pool-replay-20261023')
ZIP_SHA='68c9466fab20e14dd518e3f3bfbe1cb4cffbcde6cb79332aaa725000175c0172'
EXPECTED={
    'baseline':dict(seq=83262,at=1792269639825,sourceMs=1792269639756,token='88599287360325233240690982088109814021050513475420535621672707507474151524334',side='BUY',price='0.33',size='50.882353',transactionHash='0xbf0218fe336982520f0fc6c5e001b7ae72ac28d402e719636edf804da64fe8a1',sourceConsumed=847,poolConsumed=19,components=48,venue='603.585148',allocated='0',queueAbsorbed='0',unused='603.585148',activeMs=240,queues=('0','0')),
    'candidate':dict(seq=9982,at=1792269594953,sourceMs=1792269594884,token='12589566430666404778428222777978747623958961794906352412512658324998006663268',side='BUY',price='0.52',size='30',transactionHash='0x5e1ec2c377f1aa8cf5f59166d6e472e93426e0aef32131cca77fdda0a47bd6aa',sourceConsumed=108,poolConsumed=10,components=36,venue='412.785938',allocated='0',queueAbsorbed='9.55',unused='403.235938',activeMs=450,queues=('1172.75','180')),
}


def require(x,why):
    if not x:raise ValueError(why)


def verify(path=ROOT/'ci-artifact.zip'):
    raw=Path(path).read_bytes();require(len(raw)==13754 and hashlib.sha256(raw).hexdigest()==ZIP_SHA,'Changed exact661 replay artifact')
    with zipfile.ZipFile(path) as z:
        names=z.namelist();require(len(names)==15 and len(set(names))==15 and all(m.file_size<1024*1024 for m in z.infolist()),'Unexpected replay archive')
        summary=json.loads(z.read('development/summary.json'))
        require(summary['scope']=='ONE_SAME_ORIGINAL_DEVELOPMENT_EXACT661_BASELINE_QW0_NOT_QUALIFICATION' and summary['poolLogicalSha256']=='f9f2c6646f403f9a3ea0112e1a72dcf5685e90dec70fb4334e4967242be7a121','Wrong replay source/pool scope')
        require(summary['completeAccountComparisonPerformed'] is False and summary['independentPaperQualificationAllowed'] is False and summary['liveAllowed'] is False and summary['decision']=='NO_GO','Failed replay promoted')
        targets={}
        for profile,e in EXPECTED.items():
            result=summary['results'][profile];f=json.loads(z.read(f'development/{profile}/failure.json'));labels=f['labels'];session=f['sessionAfterSuspension'];ledger=f['ledgerAfterSuspension'];attempt=labels['lastAttemptedOriginalObservation'];obs=attempt['observation'];trade=json.loads(obs['tradeId'])
            require(result['status']=='INCOMPLETE_FAIL_CLOSED_NOT_PNL_RESULT' and result['marketNetPnlRecomputed'] is False and result['sourceConsumed']==e['sourceConsumed'] and result['knownReceiptBindingsConsumed']==e['poolConsumed'],'Wrong incomplete result counters')
            require(f['errors']==['IllegalStateException: Eligible/invalid/cancel/sell order cannot use source-lag witness'] and f['row']=={'kind':'RESEARCH_FRAME','seq':e['seq'],'arrivalMs':e['at']} and attempt['seq']==e['seq'] and attempt['eventIndex']==0 and attempt['at']==e['at'],'Wrong next blocker')
            require(obs['sourceMs']==e['sourceMs'] and obs['token']==e['token'] and obs['side']==e['side'] and D(str(obs['price']))==D(e['price']) and D(str(obs['size']))==D(e['size']) and trade['transaction_hash']==e['transactionHash'],'Wrong next original identity')
            pool=labels['realReceiptPool'];source=labels['sourceIndex'];require(pool['bindings']==661 and pool['actualComponents']==1564 and pool['consumedBindings']==e['poolConsumed'] and source['consumedOriginalPreimages']==e['sourceConsumed'] and labels['knownAppliedObservations']==e['poolConsumed'],'Wrong native consumption')
            volume=session['settlementVolumeConservation'];require(volume['uniqueMakerComponents']==e['components'] and D(str(volume['venueQuantity']))==D(e['venue']) and D(str(volume['allocatedQuantity']))==D(e['allocated']) and D(str(volume['queueAbsorbed']))==D(e['queueAbsorbed']) and D(str(volume['unusedQuantity']))==D(e['unused']),'Known volume not conserved')
            orders=session['makerExecutionDiagnostics'];require(len(orders)==2 and all(o['activeMs']==e['activeMs'] and o['terminalReason']=='DATA_GAP:unknown' and D(str(o['eligiblePrintVolume']))==0 and D(str(o['remainingShares']))==5 for o in orders),'Order lifetime differs')
            require(tuple(str(D(str(o['remainingQueueAhead'])).normalize()) for o in orders)==tuple(str(D(q).normalize()) for q in e['queues']),'Actual queues differ')
            if profile=='candidate':require(orders[0]['printObservations']=={'SETTLEMENT_COMPONENT':2},'Candidate queue debit provenance differs')
            require(session['halted'] is True and session['openOrderCount']==0 and not session['executions'] and not session['holdings'] and D(str(session['cash']))==500 and D(str(session['feesAndSettlementCosts']))==0,'Unsafe account suspension')
            require(ledger['halted'] is True and not ledger['executions'] and not ledger['holdings'] and D(str(ledger['cash']))==500 and D(str(ledger['realized']))==0 and D(str(ledger['fees']))==0 and all(o['status']=='CANCELED' and D(str(o['filled']))==0 for o in ledger['orders'].values()),'Ledger suspension differs')
            targets[profile]=dict(seq=e['seq'],eventIndex=0,at=e['at'],sourceMs=e['sourceMs'],transactionHash=e['transactionHash'],token=e['token'],side=e['side'],price=e['price'],size=e['size'])
    return dict(scope='VERIFIED_EXACT661_NEXT_TWO_RECEIPT_BLOCKERS_NOT_ACCOUNT_RESULT',runId=39942073892,jobId=120375686832,artifactId=12496972242,artifactSha256=ZIP_SHA,
        results={p:dict(sourceConsumed=e['sourceConsumed'],knownReceiptBindingsConsumed=e['poolConsumed'],knownComponents=e['components'],knownVenueQuantity=e['venue'],allocatedQuantity=e['allocated'],queueAbsorbed=e['queueAbsorbed'],unusedQuantity=e['unused'],activeMs=e['activeMs'],actualQueues=list(e['queues'])) for p,e in EXPECTED.items()},
        nextReceiptTargets=targets,modelFills=0,completeAccountComparisonPerformed=False,marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False,decision='NO_GO')


if __name__=='__main__':print(json.dumps(verify(),indent=2))
