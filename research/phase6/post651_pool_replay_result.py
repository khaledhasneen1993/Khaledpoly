"""Revalidate retained exact653 same-source failures; never promote prefix cash to PnL."""
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path('research/experiments/post651-pool-replay-20261021')
ZIP_SHA='46eb57490c0b64e2f21ed89d3ee04fcf827100a679972e28ca5a8f91b754e142'
EXPECTED={
    'baseline':dict(seq=83158,at=1792269639786,sourceMs=1792269639717,token='12589566430666404778428222777978747623958961794906352412512658324998006663268',side='BUY',price='0.7',size='28.52857',transactionHash='0xbb752799ecb1eb8c8ca56909384fafb61ed8db5bbfee91e15e775311087d0307',sourceConsumed=843,poolConsumed=11,known=11,components=37,venue='486.071859',activeMs=201,queues=('0','0')),
    'candidate':dict(seq=9379,at=1792269594713,sourceMs=1792269594644,token='12589566430666404778428222777978747623958961794906352412512658324998006663268',side='BUY',price='0.52',size='10.773585',transactionHash='0xc37adc86b7c52b5c6a910c1e3e37b089988c5c262060ce6bfe73efed55827629',sourceConsumed=104,poolConsumed=6,known=6,components=29,venue='353.424617',activeMs=210,queues=('1182.3','180')),
}


def require(x,why):
    if not x:raise ValueError(why)


def verify(path=ROOT/'ci-artifact.zip'):
    raw=Path(path).read_bytes();require(len(raw)==13703 and hashlib.sha256(raw).hexdigest()==ZIP_SHA,'Changed exact653 replay artifact')
    with zipfile.ZipFile(path) as z:
        names=z.namelist();require(len(names)==15 and len(set(names))==15 and all(m.file_size<1024*1024 for m in z.infolist()),'Unexpected replay archive')
        summary=json.loads(z.read('development/summary.json'))
        require(summary['scope']=='ONE_SAME_ORIGINAL_DEVELOPMENT_EXACT653_BASELINE_QW0_NOT_QUALIFICATION' and summary['poolLogicalSha256']=='a6faa2118ba0fdc721a6eb83876886169f0c68980c0c88e04c1cb82ce6835f3c','Wrong replay source/pool scope')
        require(summary['completeAccountComparisonPerformed'] is False and summary['independentPaperQualificationAllowed'] is False and summary['liveAllowed'] is False and summary['decision']=='NO_GO','Failed replay promoted')
        targets={}
        for profile,e in EXPECTED.items():
            result=summary['results'][profile];f=json.loads(z.read(f'development/{profile}/failure.json'));labels=f['labels'];session=f['sessionAfterSuspension'];ledger=f['ledgerAfterSuspension'];attempt=labels['lastAttemptedOriginalObservation'];obs=attempt['observation'];trade=json.loads(obs['tradeId'])
            require(result['status']=='INCOMPLETE_FAIL_CLOSED_NOT_PNL_RESULT' and result['marketNetPnlRecomputed'] is False and result['sourceConsumed']==e['sourceConsumed'] and result['knownReceiptBindingsConsumed']==e['poolConsumed'],'Wrong incomplete result counters')
            require(f['errors']==['IllegalStateException: Eligible/invalid/cancel/sell order cannot use source-lag witness'] and f['row']=={'kind':'RESEARCH_FRAME','seq':e['seq'],'arrivalMs':e['at']} and attempt['seq']==e['seq'] and attempt['eventIndex']==0 and attempt['at']==e['at'],'Wrong next blocker')
            require(obs['sourceMs']==e['sourceMs'] and obs['token']==e['token'] and obs['side']==e['side'] and D(str(obs['price']))==D(e['price']) and D(str(obs['size']))==D(e['size']) and trade['transaction_hash']==e['transactionHash'],'Wrong next original identity')
            pool=labels['realReceiptPool'];source=labels['sourceIndex'];require(pool['bindings']==653 and pool['actualComponents']==1553 and pool['consumedBindings']==e['poolConsumed'] and source['consumedOriginalPreimages']==e['sourceConsumed'] and labels['knownAppliedObservations']==e['known'],'Wrong native consumption')
            volume=session['settlementVolumeConservation'];require(volume['uniqueMakerComponents']==e['components'] and D(str(volume['venueQuantity']))==D(e['venue']) and D(str(volume['allocatedQuantity']))==0 and D(str(volume['queueAbsorbed']))==0 and D(str(volume['unusedQuantity']))==D(e['venue']),'Known volume not conserved')
            orders=session['makerExecutionDiagnostics'];require(len(orders)==2 and all(o['activeMs']==e['activeMs'] and o['terminalReason']=='DATA_GAP:unknown' and D(str(o['eligiblePrintVolume']))==0 and D(str(o['remainingShares']))==5 for o in orders),'Order lifetime differs')
            require(tuple(str(o['remainingQueueAhead']) for o in orders)==e['queues'],'Actual queues differ')
            require(session['halted'] is True and session['openOrderCount']==0 and not session['executions'] and not session['holdings'] and D(str(session['cash']))==500 and D(str(session['feesAndSettlementCosts']))==0,'Unsafe account suspension')
            require(ledger['halted'] is True and not ledger['executions'] and not ledger['holdings'] and D(str(ledger['cash']))==500 and D(str(ledger['realized']))==0 and D(str(ledger['fees']))==0 and all(o['status']=='CANCELED' and D(str(o['filled']))==0 for o in ledger['orders'].values()),'Ledger suspension differs')
            targets[profile]=dict(seq=e['seq'],eventIndex=0,at=e['at'],sourceMs=e['sourceMs'],transactionHash=e['transactionHash'],token=e['token'],side=e['side'],price=e['price'],size=e['size'])
    return dict(scope='VERIFIED_EXACT653_NEXT_TWO_RECEIPT_BLOCKERS_NOT_ACCOUNT_RESULT',runId=39654814359,jobId=119412159026,artifactId=12371311452,artifactSha256=ZIP_SHA,
        results={p:dict(sourceConsumed=e['sourceConsumed'],knownReceiptBindingsConsumed=e['poolConsumed'],knownComponents=e['components'],knownVenueQuantity=e['venue'],activeMs=e['activeMs'],actualQueues=list(e['queues'])) for p,e in EXPECTED.items()},
        nextReceiptTargets=targets,modelFills=0,completeAccountComparisonPerformed=False,marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False,decision='NO_GO')


if __name__=='__main__':print(json.dumps(verify(),indent=2))
