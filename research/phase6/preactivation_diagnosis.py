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
from research.phase6.preactivation_result import verify

ROOT=Path('research/experiments/preactivation-20261020')
ZIP_SHA='f8dd0c2754b5ee15d6f78240d63dfdaf1aed7617537e5836139f0d029d0a0902'
EXPECTED={'baseline':(82880,836,834,8,['0','0']), 'candidate':(8739,94,92,7,['1182.30','180'])}


def require(value,why):
    if not value:raise ValueError(why)


def frontier(f,audit,rows,config,profile):
    seq,count,unknown,pending,queues=EXPECTED[profile];labels=f['labels'];a=labels['lastAttemptedOriginalObservation'];data=a['observation'];identity=rows[count-1]
    require(a['seq']==seq and a['eventIndex']==0 and f['row']=={'seq':seq,'arrivalMs':a['at'],'kind':'RESEARCH_FRAME'},'Wrong original coordinate')
    require(all(a[k]==identity[k] for k in ('seq','eventIndex','at')) and all(data[k]==identity[k] for k in ('token','side','sourceMs')) and all(D(str(data[k]))==D(str(identity[k])) for k in ('price','size')),'Changed original preimage')
    require(digest(data['tradeId'].encode())==identity['publicTradeIdSha256'] and json.loads(data['tradeId'])['transaction_hash']==identity['transactionHash'],'Changed original transaction')
    require(f['candidateFrozenPoliciesEnabled'] is (profile=='candidate') and f['errors']==['IllegalStateException: Active/due/cancel/sell order cannot use pending-buy witness'],'Changed profile/guard')
    idx=labels['sourceIndex'];pool=labels['realReceiptPool'];s=f['sessionAfterSuspension'];ledger=f['ledgerAfterSuspension']
    require(labels['temporalWitnessProfile']=='PRE_ACTIVATION0' and labels['failed'] is True and idx['failed'] is False and idx['consumedOriginalPreimages']==count and idx['completeOriginalConsumption'] is False and idx['subsetPreimageTestOnly'] is False,'Changed identity scope')
    require(labels['knownAppliedObservations']==1 and labels['knownExpiredObservations']==0 and pool['consumedBindings']==1 and pool['failed'] is False and labels['unknownAtomicClockObservations']==unknown and labels['unknownPreActivationClockObservations']==pending and labels['unknownVenueQuantity']=='UNKNOWN_NOT_ZERO','Changed route accounting')
    require(all(D(str(s['configuration'][k]))==D(str(v)) for k,v in config.items()),'Changed execution parameters')
    require(s['halted'] is True and s['openOrderCount']==0 and ledger['halted'] is True and not ledger['holdings'] and not ledger['executions'] and D(str(ledger['cash']))==500 and D(str(ledger['realized']))==0 and D(str(ledger['fees']))==0,'Unsafe prefix account')
    volume=s['settlementVolumeConservation'];require(volume['uniqueMakerComponents']==16 and D(str(volume['venueQuantity']))==200 and D(str(volume['unusedQuantity']))==200 and D(str(volume['allocatedQuantity']))==0 and D(str(volume['queueAbsorbed']))==0,'Known volume changed')
    entries={r['data']['id']:r['data'] for r in audit if r['kind']=='ORDER'};terminal={r['data']['id']:r['data'] for r in audit if r['kind']=='ORDER_TERMINAL'};diagnostics=s['makerExecutionDiagnostics']
    require(len(entries)==2 and set(entries)==set(terminal)==set(ledger['orders']) and len(diagnostics)==2,'Missing original submit/cancel/queue audits')
    orders=[]
    for i,o in enumerate(diagnostics):
        order_id=o['id'];entry=entries[order_id];cancel=terminal[order_id];reservation=ledger['orders'][order_id]
        require(o['submittedMs']==entry['at'] and o['activationDueMs']==entry['at']+250 and o['activatedMs']>=o['activationDueMs'] and o['activatedMs']<a['at'] and data['sourceMs']<o['activatedMs'],'Not active arrival with pre-activation source')
        require(cancel['at']==a['at']==o['terminalMs'] and cancel['status']==reservation['status']=='CANCELED' and o['terminalReason']==cancel['reason']=='DATA_GAP:unknown' and D(str(reservation['remaining']))==0 and D(str(reservation['filled']))==0 and D(str(entry['quantity']))==5,'Changed fail-closed cancel')
        require(D(str(o['initialQueueAhead']))==D(queues[i])==D(str(o['remainingQueueAhead'])) and D(str(o['eligiblePrintVolume']))==0 and D(str(o['remainingShares']))==5 and not o['printObservations'],'Changed actual queue/fill evidence')
        orders.append(dict(id=order_id,price=o['price'],submittedMs=o['submittedMs'],activationDueMs=o['activationDueMs'],activatedMs=o['activatedMs'],activeAtStopMs=a['at']-o['activatedMs'],sourceBeforeActivationMs=o['activatedMs']-data['sourceMs'],initialQueueAhead=o['initialQueueAhead'],remainingQueueAhead=o['remainingQueueAhead'],canceledAt=a['at']))
    return dict(sequence=seq,originalIdentitiesConsumed=count,unknownAtomicClockObservations=unknown,unknownPreActivationClockObservations=pending,transactionHash=identity['transactionHash'],publicTradeIdSha256=identity['publicTradeIdSha256'],arrivalMs=a['at'],sourceMs=data['sourceMs'],orders=orders,frontierOrdersActiveButTradeSourceBeforeTheirActivation=True,executionsBeforeStop=0,fullAccountNetAfterCosts='UNKNOWN_INCOMPLETE_PREFIX_NOT_FINANCIAL_RESULT')


def load():
    archive=ROOT/'ci-artifact.zip';require(hashlib.sha256(archive.read_bytes()).hexdigest()==ZIP_SHA,'Changed artifact')
    verify(ROOT)
    with zipfile.ZipFile(archive) as z:
        require(len(z.infolist())==25 and len(set(z.namelist()))==25 and all(m.file_size<16*1024*1024 for m in z.infolist()),'Changed bounded archive')
        for name in ('preactivation-proof.json','preactivation-session-proof.json','indexed-execution-proof.json'):
            require(json.loads(z.read('proof/'+name))==json.loads((ROOT/name).read_bytes()),'Native Java21 proof differs '+name)
        indexed(json.loads(z.read('proof/indexed-execution-proof.json')))
        require(atomic(json.loads(z.read('proof/atomic-guard-proof.json')))==json.loads(z.read('proof/atomic-verification.json')),'Atomic verification differs')
        require(differential(json.loads(z.read('proof/no-order-proof.json')))==json.loads(z.read('proof/differential-verification.json')),'Differential verification differs')
        require(json.loads(z.read('proof/default-parity.json'))==json.loads(Path('research/experiments/session-bridge-20261019/default-before.json').read_bytes()),'DEFAULT changed')
        rows,_,_=reconstruct();config=json.loads(Path('research/phase2/research-config.json').read_bytes());results={}
        summary=json.loads(z.read('development/summary.json'))
        require(summary['completeAccountComparisonPerformed'] is False and summary['decision']=='NO_GO' and summary['temporalWitnessProfile']=='PRE_ACTIVATION0','Incomplete runs promoted')
        for profile in EXPECTED:
            f=json.loads(z.read('development/'+profile+'/failure.json'));audit=[json.loads(line) for line in z.read('development/'+profile+'/failure-audit.jsonl').splitlines()]
            results[profile]=frontier(f,audit,rows,config,profile)
            require(summary['results'][profile]['sourceConsumed']==results[profile]['originalIdentitiesConsumed'],'Summary mismatch')
    return dict(scope='VERIFIED_ORIGINAL_PRE_ACTIVATION0_ACTIVE_ARRIVAL_SOURCE_LAG_FRONTIERS_NOT_PNL',sourceCommit='886ee0ce0f3416ff394c85baca7b41f351f6986a',runId=39443362971,artifactId=12275333120,artifactSha256=ZIP_SHA,results=results,completeAccountComparisonPerformed=False,marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False,decision='NO_GO',nextStep='No unchanged rerun. Prove narrowly source-time-at-or-before-activation irrelevance, including exact activation/cancel/queue ordering and counterexamples, before any separately frozen guard; otherwise collect bounded exact frontier receipts. Do not tune holdout or strategy.')


if __name__=='__main__':print(json.dumps(load(),indent=2))
