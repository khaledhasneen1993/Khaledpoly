"""Verify exact original frontiers, activation-time queues and fail-closed account.

Both runs are incomplete. Cash500 and zero prefix fills/costs are NOT net PnL.
"""
import hashlib
import json
from decimal import Decimal as D
from pathlib import Path
import zipfile
from research.phase6.complete_source_index import reconstruct,digest
from research.phase6.indexed_execution_result import verify as indexed
from research.phase6.atomic_guard_result import verify as atomic
from research.phase6.no_order_result import verify as differential
from research.phase6.source_lag_guard_result import verify
from research.phase6.source_lag_result import verify as math_proof

ROOT=Path('research/experiments/source-lag-guard-20261020')
ZIP_SHA='74765c9e6b019b029b7dc2297b4087a368b02092aec179ff06db92102fe55b7c'
EXPECTED={'baseline':(82964,838,836,10,2,['0','0']), 'candidate':(9035,99,97,12,5,['1182.30','180'])}


def require(value,why):
    if not value:raise ValueError(why)


def frontier(f,audit,rows,config,profile):
    seq,count,unknown,clock,active,queues=EXPECTED[profile];labels=f['labels'];a=labels['lastAttemptedOriginalObservation'];data=a['observation'];identity=rows[count-1]
    require(a['seq']==seq and a['eventIndex']==0 and f['row']=={'seq':seq,'arrivalMs':a['at'],'kind':'RESEARCH_FRAME'},'Wrong original coordinate')
    require(all(a[k]==identity[k] for k in ('seq','eventIndex','at')) and all(data[k]==identity[k] for k in ('token','side','sourceMs')) and all(D(str(data[k]))==D(str(identity[k])) for k in ('price','size')),'Changed original preimage')
    require(digest(data['tradeId'].encode())==identity['publicTradeIdSha256'] and json.loads(data['tradeId'])['transaction_hash']==identity['transactionHash'],'Changed original transaction')
    require(f['candidateFrozenPoliciesEnabled'] is (profile=='candidate') and f['errors']==['IllegalStateException: Eligible/invalid/cancel/sell order cannot use source-lag witness'],'Changed profile/guard')
    idx=labels['sourceIndex'];pool=labels['realReceiptPool'];s=f['sessionAfterSuspension'];ledger=f['ledgerAfterSuspension']
    require(labels['temporalWitnessProfile']=='SOURCE_LAG0' and labels['failed'] is True and idx['failed'] is False and idx['consumedOriginalPreimages']==count and idx['completeOriginalConsumption'] is False and idx['subsetPreimageTestOnly'] is False,'Changed identity scope')
    require(labels['knownAppliedObservations']==1 and labels['knownExpiredObservations']==0 and pool['consumedBindings']==1 and pool['failed'] is False and labels['unknownAtomicClockObservations']==unknown and labels['unknownSourceLagClockObservations']==clock and labels['unknownSourceLagActiveClockObservations']==active and labels['unknownVenueQuantity']=='UNKNOWN_NOT_ZERO','Changed route accounting')
    require(all(D(str(s['configuration'][k]))==D(str(v)) for k,v in config.items()),'Changed execution parameters')
    require(s['halted'] is True and s['openOrderCount']==0 and ledger['halted'] is True and not ledger['holdings'] and not ledger['executions'] and D(str(ledger['cash']))==500 and D(str(ledger['realized']))==0 and D(str(ledger['fees']))==0,'Unsafe prefix account')
    volume=s['settlementVolumeConservation'];require(volume['uniqueMakerComponents']==16 and D(str(volume['venueQuantity']))==200 and D(str(volume['unusedQuantity']))==200 and D(str(volume['allocatedQuantity']))==0 and D(str(volume['queueAbsorbed']))==0,'Known volume changed')
    entries={r['data']['id']:r['data'] for r in audit if r['kind']=='ORDER'};terminal={r['data']['id']:r['data'] for r in audit if r['kind']=='ORDER_TERMINAL'};diagnostics=s['makerExecutionDiagnostics']
    require(len(entries)==2 and set(entries)==set(terminal)==set(ledger['orders']) and len(diagnostics)==2,'Missing original submit/cancel/queue audits')
    orders=[]
    for i,o in enumerate(diagnostics):
        order_id=o['id'];entry=entries[order_id];cancel=terminal[order_id];reservation=ledger['orders'][order_id]
        require(o['submittedMs']==entry['at'] and o['activationDueMs']==entry['at']+250 and o['activatedMs']>=o['activationDueMs'] and o['activatedMs']<a['at'] and data['sourceMs']>o['activatedMs'],'Frontier does not have source after actual activation')
        require(cancel['at']==a['at']==o['terminalMs'] and cancel['status']==reservation['status']=='CANCELED' and o['terminalReason']==cancel['reason']=='DATA_GAP:unknown' and D(str(reservation['remaining']))==0 and D(str(reservation['filled']))==0 and D(str(entry['quantity']))==5,'Changed fail-closed cancel')
        require(D(str(o['initialQueueAhead']))==D(queues[i])==D(str(o['remainingQueueAhead'])) and D(str(o['eligiblePrintVolume']))==0 and D(str(o['remainingShares']))==5 and not o['printObservations'],'Changed actual queue/fill evidence')
        orders.append(dict(id=order_id,price=o['price'],submittedMs=o['submittedMs'],activationDueMs=o['activationDueMs'],activatedMs=o['activatedMs'],activeAtStopMs=a['at']-o['activatedMs'],sourceAfterActivationMs=data['sourceMs']-o['activatedMs'],initialQueueAhead=o['initialQueueAhead'],remainingQueueAhead=o['remainingQueueAhead'],canceledAt=a['at']))
    return dict(sequence=seq,originalIdentitiesConsumed=count,unknownAtomicClockObservations=unknown,unknownSourceLagClockObservations=clock,unknownSourceLagActiveClockObservations=active,transactionHash=identity['transactionHash'],publicTradeIdSha256=identity['publicTradeIdSha256'],arrivalMs=a['at'],sourceMs=data['sourceMs'],orders=orders,frontierOrdersActiveAndTradeSourceAfterTheirActivation=True,temporalShortcutNoLongerApplies=True,executionsBeforeStop=0,fullAccountNetAfterCosts='UNKNOWN_INCOMPLETE_PREFIX_NOT_FINANCIAL_RESULT')


def load():
    archive=ROOT/'ci-artifact.zip';require(hashlib.sha256(archive.read_bytes()).hexdigest()==ZIP_SHA,'Changed artifact')
    verify(json.loads((ROOT/'source-lag-guard-proof.json').read_bytes()))
    with zipfile.ZipFile(archive) as z:
        require(len(z.infolist())==27 and len(set(z.namelist()))==27 and all(m.file_size<16*1024*1024 for m in z.infolist()),'Changed bounded archive')
        for name in ('source-lag-guard-proof.json','indexed-execution-proof.json'):
            require(json.loads(z.read('proof/'+name))==json.loads((ROOT/name).read_bytes()),'Native Java21 proof differs '+name)
        indexed(json.loads(z.read('proof/indexed-execution-proof.json')))
        require(verify(json.loads(z.read('proof/source-lag-guard-proof.json')))==json.loads(z.read('proof/source-lag-guard-verification.json')),'Guard verification differs')
        mathematical=json.loads(z.read('proof/source-lag-proof.json'))
        require(mathematical==json.loads(Path('research/experiments/source-lag-20261020/source-lag-proof.json').read_bytes()) and math_proof(mathematical)==json.loads(z.read('proof/source-lag-math-verification.json')),'Frozen source-lag math differs')
        require(json.loads(z.read('proof/preactivation-proof.json'))==json.loads(Path('research/experiments/preactivation-20261020/preactivation-proof.json').read_bytes()),'Prior preactivation guard differs')
        require(atomic(json.loads(z.read('proof/atomic-guard-proof.json')))==json.loads(z.read('proof/atomic-verification.json')),'Atomic verification differs')
        require(differential(json.loads(z.read('proof/no-order-proof.json')))==json.loads(z.read('proof/differential-verification.json')),'Differential verification differs')
        require(json.loads(z.read('proof/default-parity.json'))==json.loads(Path('research/experiments/session-bridge-20261019/default-before.json').read_bytes()),'DEFAULT changed')
        rows,_,_=reconstruct();config=json.loads(Path('research/phase2/research-config.json').read_bytes());results={}
        summary=json.loads(z.read('development/summary.json'))
        require(summary['completeAccountComparisonPerformed'] is False and summary['decision']=='NO_GO' and summary['temporalWitnessProfile']=='SOURCE_LAG0','Incomplete runs promoted')
        for profile in EXPECTED:
            f=json.loads(z.read('development/'+profile+'/failure.json'));audit=[json.loads(line) for line in z.read('development/'+profile+'/failure-audit.jsonl').splitlines()]
            results[profile]=frontier(f,audit,rows,config,profile)
            require(summary['results'][profile]['sourceConsumed']==results[profile]['originalIdentitiesConsumed'],'Summary mismatch')
    return dict(scope='VERIFIED_ORIGINAL_SOURCE_LAG0_SOURCE_AFTER_ACTIVATION_FRONTIERS_NOT_PNL',sourceCommit='da1211f2eccca29e865994f4090f8df55edb0000',runId=39459692699,artifactId=12281674124,artifactSha256=ZIP_SHA,results=results,completeAccountComparisonPerformed=False,marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False,decision='NO_GO',nextStep='No unchanged rerun or weaker temporal guard. Obtain and independently verify ONLY the exact original baseline82964 and candidate9035 transaction receipts, parse conserved settlement components, preserve raw preimages, then separately freeze an expanded real pool before one new same-source comparison. Public price/size is NOT venue quantity or a bot fill. No holdout or strategy tuning.')


if __name__=='__main__':print(json.dumps(load(),indent=2))
