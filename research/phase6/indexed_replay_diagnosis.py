"""Reconstruct original frozen replay frontier and actual submit/cancel timing.

These incomplete accounts are NOT economic results. No new receipt/capture.
"""
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import zipfile
from research.phase6.indexed_execution_result import ROOT,verify
from research.phase6.complete_source_index import reconstruct,digest
from research.phase6.atomic_guard_result import verify as atomic
from research.phase6.no_order_result import verify as differential

ZIP_SHA='1eee8b222b52ecc49c21d4deebecc98b16a7530f614ce5978421071df26509d9'
EXPECTED={'baseline':(82652,828,826),'candidate':(8018,87,85)}


def verify_frontier(failure,audit,rows,config,profile):
    seq,count,unknown=EXPECTED[profile];labels=failure['labels'];attempt=labels['lastAttemptedOriginalObservation'];data=attempt['observation']
    identity=rows[count-1];index=labels['sourceIndex'];pool=labels['realReceiptPool'];s=failure['sessionAfterSuspension'];ledger=failure['ledgerAfterSuspension']
    if (attempt['seq']!=seq or attempt['eventIndex']!=0 or identity['seq']!=seq
            or failure['row']!={'seq':seq,'arrivalMs':attempt['at'],'kind':'RESEARCH_FRAME'}
            or any(attempt[k]!=identity[k] for k in ('seq','eventIndex','at'))
            or any(data[k]!=identity[k] for k in ('token','side','sourceMs'))
            or any(D(str(data[k]))!=D(str(identity[k])) for k in ('price','size'))
            or digest(data['tradeId'].encode())!=identity['publicTradeIdSha256']
            or json.loads(data['tradeId'])['transaction_hash']!=identity['transactionHash']):raise ValueError('Wrong original frontier identity')
    if (failure['candidateFrozenPoliciesEnabled'] is not (profile=='candidate')
            or failure['errors']!=['IllegalStateException: No-order research witness requires healthy empty exposure']
            or index['consumedOriginalPreimages']!=count or index['failed'] is not False
            or index['completeOriginalConsumption'] is not False or index['subsetPreimageTestOnly'] is not False
            or labels['failed'] is not True or pool['consumedBindings']!=1 or pool['failed'] is not False
            or labels['knownAppliedObservations']!=1 or labels['knownExpiredObservations']!=0
            or labels['unknownAtomicClockObservations']!=unknown or labels['unknownVenueQuantity']!='UNKNOWN_NOT_ZERO'):
        raise ValueError('Wrong frozen profile/guard/consumption accounting')
    if any(D(str(s['configuration'][k]))!=D(str(v)) for k,v in config.items()):raise ValueError('Changed execution/risk/fee config')
    if (s['halted'] is not True or s['openOrderCount']!=0 or ledger['halted'] is not True
            or ledger['holdings'] or ledger['executions'] or D(str(ledger['cash']))!=500
            or D(str(ledger['realized']))!=0 or D(str(ledger['fees']))!=0):raise ValueError('Incomplete prefix account/halt differs')
    volume=s['settlementVolumeConservation']
    if (volume['uniqueMakerComponents']!=16 or D(str(volume['venueQuantity']))!=200
            or D(str(volume['unusedQuantity']))!=200 or D(str(volume['queueAbsorbed']))!=0
            or D(str(volume['allocatedQuantity']))!=0):raise ValueError('Known actual97 volume not conserved')
    entries={r['data']['id']:r['data'] for r in audit if r['kind']=='ORDER'}
    terminal={r['data']['id']:r['data'] for r in audit if r['kind']=='ORDER_TERMINAL'}
    if len(entries)!=2 or set(entries)!=set(ledger['orders']) or set(terminal)!=set(entries):raise ValueError('Missing actual pair submit/cancel audit')
    delays=[];quotes=[]
    for order_id,entry in entries.items():
        order=ledger['orders'][order_id];cancel=terminal[order_id];delay=attempt['at']-entry['at']
        if (not 0<=delay<int(config['activationMs']) or data['sourceMs']>=entry['at']
                or cancel['at']!=attempt['at'] or cancel['status']!='CANCELED'
                or order['status']!='CANCELED' or D(str(order['remaining']))!=0 or D(str(order['filled']))!=0
                or D(str(entry['quantity']))!=5 or D(str(order['price']))!=D(str(entry['price']))):
            raise ValueError('Original frontier was not pre-activation / safe cancel')
        delays.append(delay);quotes.append(str(entry['price']))
    return dict(sequence=seq,sourceIdentitiesConsumed=count,unknownAtomicClockObservations=unknown,
        transactionHash=identity['transactionHash'],publicTradeIdSha256=identity['publicTradeIdSha256'],
        paperOrdersSubmitted=2,paperOrderPrices=sorted(quotes),arrivalAfterSubmissionMs=delays,
        configuredActivationMs=int(config['activationMs']),tradeSourceBeforeSubmissions=True,
        frontierOrdersStillPendingNotActive=True,ordersCanceledAtHalt=2,executionsBeforeStop=0,
        fullAccountNetPnl='UNKNOWN_INCOMPLETE_PREFIX_NOT_FINANCIAL_RESULT')


def load():
    raw=(ROOT/'ci-artifact.zip').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=ZIP_SHA:raise ValueError('Changed indexed original result artifact')
    with zipfile.ZipFile(ROOT/'ci-artifact.zip') as z:
        if len(z.infolist())!=22 or len(set(z.namelist()))!=22 or any(m.file_size>16*1024*1024 for m in z.infolist()):raise ValueError('Wrong bounded diagnostic archive')
        proof=json.loads(z.read('proof/indexed-execution-proof.json'));verify(proof)
        if proof!=json.loads((ROOT/'indexed-execution-proof.json').read_bytes()):raise ValueError('Native Java21 integration differs')
        if atomic(json.loads(z.read('proof/atomic-guard-proof.json')))!=json.loads(z.read('proof/atomic-verification.json')):raise ValueError('Atomic proof differs')
        if differential(json.loads(z.read('proof/no-order-proof.json')))!=json.loads(z.read('proof/differential-verification.json')):raise ValueError('No-order counterexamples differ')
        if json.loads(z.read('proof/default-parity.json'))!=json.loads(Path('research/experiments/session-bridge-20261019/default-before.json').read_bytes()):raise ValueError('Default oracle changed')
        rows,_,_=reconstruct();config=json.loads(Path('research/phase2/research-config.json').read_bytes());results={}
        for profile in EXPECTED:
            failure=json.loads(z.read('development/'+profile+'/failure.json'))
            audit=[json.loads(line) for line in z.read('development/'+profile+'/failure-audit.jsonl').splitlines()]
            results[profile]=verify_frontier(failure,audit,rows,config,profile)
        summary=json.loads(z.read('development/summary.json'))
        if summary['completeAccountComparisonPerformed'] is not False or summary['decision']!='NO_GO':raise ValueError('Incomplete runs promoted')
        for profile,result in results.items():
            if summary['results'][profile]['sourceConsumed']!=result['sourceIdentitiesConsumed']:raise ValueError('Summary count differs')
    return dict(scope='VERIFIED_ORIGINAL_INDEXED_REPLAY_PENDING_ORDER_FRONTIERS_NOT_PNL',
        sourceCommit='3d5310ae613ec6995fbbafee2fca8ebd44d96c74',runId=39433713918,results=results,
        original628PassedInBothReplays=True,completeAccountComparisonPerformed=False,marketNetPnlRecomputed=False,
        newPublicReads=0,independentPaperQualificationAllowed=False,liveAllowed=False,decision='NO_GO',
        nextStep='Prove pending/pre-activation print irrelevance with unchanged activation/cancel ordering before broadening frozen guard; otherwise request only bounded exact frontier receipts. Do not tune strategy or rerun unchanged data.')


if __name__=='__main__':print(json.dumps(load(),indent=2))
