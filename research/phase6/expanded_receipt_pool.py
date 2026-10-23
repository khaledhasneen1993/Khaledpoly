"""Offline643 pool: preserve ALL642 bindings and add only the proven original97 receipt."""
import argparse
from collections import Counter
from decimal import Decimal as D
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
from research.phase6.first_blocker_result import load,verify
from research.phase6.first_blocker_receipt import digest
from research.phase6.receipt_audit import corroborate
from research.phase6.mixed_replay_labels_proof import portions_sha
from research.phase6.native_pool_inputs import prepare
from research.phase6.full_tape_coverage_result import read_archive,ROOT as COVERAGE
from research.phase6.full_runner_diagnosis import digest as file_sha,STORED_SHA

ROOT=Path('research/experiments/expanded-receipt-pool-20261020')
PARENT=Path('research/experiments/cached-receipt-pool-20261020/bindings.json.gz')
PARENT_SHA='745dadce6749d701ba6048ab1ef76f3f43b354c058e27e9163c2174725aaceea'

def build():
    raw=gzip.decompress(PARENT.read_bytes())
    if digest(raw)!=PARENT_SHA:raise ValueError('Changed complete642 parent')
    parent=json.loads(raw);pool=json.loads(raw);spec,receipt,report=load();proof=verify(spec,receipt,report)
    decoded=corroborate(spec['sample'],json.loads(receipt)['receipt'],json.loads(receipt)['block'],spec['topics'])
    group=report['route']['matchingGroups'][0]
    matches=[m for m in decoded['matches'] if m['exchange']==group['exchange'] and m['ordersMatchedLogIndex']==group['groupLogIndex']]
    binding=dict(seq=spec['seq'],eventIndex=spec['eventIndex'],at=spec['at'],sourceMs=int(spec['sample']['timestamp']),
        transactionHash=spec['transactionHash'],publicTradeIdSha256=spec['publicTradeIdSha256'],token=spec['sample']['asset_id'],
        side=spec['sample']['side'],price=spec['sample']['price'],size=spec['sample']['size'],pair=spec['pair'],condition=spec['condition'],
        matches=matches,sourceCoverage='MISSING_SCOPED_PAIR_LABEL',origin='PROVEN_ORIGINAL_FIRST_BLOCKER97')
    keys={(b['seq'],b['eventIndex']) for b in pool['bindings']};txs={b['transactionHash'] for b in pool['bindings']}
    if (binding['seq'],binding['eventIndex']) in keys or binding['transactionHash'] in txs:raise ValueError('Duplicate expansion')
    pool['bindings'].append(binding);pool['bindings'].sort(key=lambda b:(b['seq'],b['eventIndex']))
    if [b for b in pool['bindings'] if b['origin']!='PROVEN_ORIGINAL_FIRST_BLOCKER97']!=parent['bindings']:raise ValueError('Prior642 changed')
    pool.update(expectedBindingCount=643,expectedComponentCount=1532,remainingUnboundObservations=15674,
        parentPoolLogicalSha256=PARENT_SHA,firstBlockerReceiptBindings=1,
        addedReceiptArtifactSha256='5d8bf1e09bd0a5ed2210a43e256e90b0122c36dc48aeac36427f9ee528c956aa')
    counts=Counter(m['matchType'] for b in pool['bindings'] for m in b['matches'])
    if len(pool['bindings'])!=643 or sum(counts.values())!=1532:raise ValueError('Incomplete expansion')
    pool['routeComponentCounts']=dict(counts);pool['portionsLogicalSha256']=portions_sha(pool)
    return pool

def identities(pool):
    raw,old=prepare()
    if digest(raw)!=PARENT_SHA:raise ValueError('Original642 identity source differs')
    spec,_,_=load();rows=old['observations']+[dict(seq=spec['seq'],eventIndex=spec['eventIndex'],at=spec['at'],data={
        'token':spec['sample']['asset_id'],'side':spec['sample']['side'],'price':spec['sample']['price'],
        'size':spec['sample']['size'],'sourceMs':int(spec['sample']['timestamp']),'tradeId':spec['originalTradeId']})]
    rows.sort(key=lambda r:(r['seq'],r['eventIndex']))
    if [(r['seq'],r['eventIndex']) for r in rows]!=[(b['seq'],b['eventIndex']) for b in pool['bindings']]:raise ValueError('Original643 coordinates differ')
    return dict(scope='EXACT643_ORIGINAL_IDENTITY_INPUTS_NOT_EXECUTION_TAPE',observations=rows)

def next_missing(pool):
    _,compressed,_=read_archive(COVERAGE/'artifact.zip');keys={(b['seq'],b['eventIndex']) for b in pool['bindings']}
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as f:
        for line in f:
            row=json.loads(line)
            if (row['seq'],row['eventIndex']) not in keys:return row
    raise ValueError('No next missing original observation')

def verify_native(report,summary):
    if (report['scope']!='ALL643_NATIVE_IDENTITY_PARITY_NOT_ACCOUNT_REPLAY' or report['originalIdentities']!=643
            or report['readerRejectionGuards']!=39 or report['conservativeRoundingBoundaryCases']!=2
            or any(report[k]!=summary[k] for k in ('poolLogicalSha256','sourceIdentitiesSha256','portionsLogicalSha256'))):raise ValueError('Native643 source/component parity differs')
    reader=report['pool']
    if (reader['bindings']!=643 or reader['actualComponents']!=1532 or reader['consumedBindings']!=643
            or reader['failed'] is not False or reader['strictPartialPool'] is not True):raise ValueError('Incomplete643 consumption')
    for k in ('aggregateFallbackAllowed','fullOriginalTapeCoverageProven','fullAccountReplayAuthorized','independentPaperQualificationAllowed','liveAllowed'):
        if reader[k] is not False:raise ValueError('Expanded partial pool scope promotion')
    for k in ('marketNetPnlRecomputed','completeAccountComparisonPerformed','independentPaperQualificationAllowed','liveAllowed'):
        if report[k] is not False:raise ValueError('Native parity cannot become account evidence')
    guard=report['separateSyntheticUnknownGuard'];s=guard['session']
    if (guard['inputKind']!='SYNTHETIC_ONLY_NOT_MARKET' or guard['unknownCoveredTransactionAtWrongCoordinateHaltsCancels'] is not True
            or guard['subsequentInputBlocked'] is not True or guard['existingCashAndInventoryPreserved'] is not True
            or s['halted'] is not True or s['openOrderCount']!=0 or D(str(s['cash']))!=498
            or D(str(s['holdings']['a']['shares']))!=5 or D(str(s['feesAndSettlementCosts']))!=0):raise ValueError('Separate synthetic halt/inventory guard differs')
    return dict(scope='VERIFIED_ALL643_NATIVE_PARITY_NOT_ACCOUNT',originalIdentities=643,componentTuples=1532,
        original642Preserved=True,readerRejectionGuards=39,marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False)

def write(output):
    pool=build();raw=(json.dumps(pool,separators=(',',':'))+'\n').encode();source=(json.dumps(identities(pool),separators=(',',':'))+'\n').encode()
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    (out/'pool.json').write_bytes(raw);(out/'source-identities.json').write_bytes(source)
    result=dict(scope='OFFLINE643_PARTIAL_POOL_NOT_ACCOUNT',bindings=643,components=1532,parent642Unchanged=True,
        poolLogicalSha256=digest(raw),sourceIdentitiesSha256=digest(source),portionsLogicalSha256=pool['portionsLogicalSha256'],
        routeComponentCounts=pool['routeComponentCounts'],nextMissing=next_missing(pool),
        marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False)
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');return result

def verify_stop(proof,expected,candidate,config):
    if (proof['scope']!='INCOMPLETE_ORIGINAL_TAPE_FAIL_CLOSED_DIAGNOSTIC_NOT_FINANCIAL_RESULT'
            or proof['candidateFrozenPoliciesEnabled'] is not candidate or proof['decision']!='NO_GO'):
        raise ValueError('Invalid expanded-prefix scope/profile')
    for k in ('fullOriginalTapeCoverageProven','completeAccountComparisonPerformed','marketNetPnlRecomputed','independentPaperQualificationAllowed','liveAllowed'):
        if proof[k] is not False:raise ValueError('Partial prefix cannot become qualification/PnL')
    labels=proof['labels'];attempt=labels['lastAttemptedOriginalObservation'];data=attempt['observation']
    if (labels['bindings']!=643 or labels['actualComponents']!=1532 or labels['consumedBindings']!=1
            or labels['failed'] is not True or labels['aggregateFallbackAllowed'] is not False
            or proof['row']!={'seq':expected['seq'],'arrivalMs':expected['at'],'kind':'RESEARCH_FRAME'}
            or any(attempt[k]!=expected[k] for k in ('seq','eventIndex','at'))
            or any(data[k]!=expected[k] for k in ('token','side','sourceMs'))
            or any(D(str(data[k]))!=D(str(expected[k])) for k in ('price','size'))
            or digest(data['tradeId'].encode())!=expected['publicTradeIdSha256']
            or json.loads(data['tradeId'])['transaction_hash']!=expected['transactionHash']):raise ValueError('Wrong next ORIGINAL identity/count')
    if proof['errors']!=['IllegalArgumentException: Fail-closed pool resolution','IllegalArgumentException: Unknown original observation; incomplete pool is not zero']:
        raise ValueError('Unexpected failure, not next coverage stop')
    session=proof['sessionAfterSuspension'];ledger=proof['ledgerAfterSuspension']
    if (session['halted'] is not True or session['openOrderCount']!=0 or ledger['halted'] is not True
            or session['frozenQw0AndFeePositivePoliciesIntegrated'] is not candidate or session['settlementExperiment']!=labels):raise ValueError('Unsafe halt/profile')
    if any(D(str(session['configuration'][k]))!=D(str(v)) for k,v in config.items()):raise ValueError('Original risk/queue/fee config changed')
    volume=session['settlementVolumeConservation']
    if (volume['uniqueMakerComponents']!=16 or D(str(volume['venueQuantity']))!=200
            or sum(D(str(volume[k])) for k in ('queueAbsorbed','allocatedQuantity','unusedQuantity'))!=200):raise ValueError('Original16 component volume not conserved')
    return dict(seq=expected['seq'],eventIndex=expected['eventIndex'],transactionHash=expected['transactionHash'],
        consumedBindings=1,uniqueMakerComponents=16,venueQuantity='200',halted=True,openOrders=0,
        completeAccountComparisonPerformed=False,marketNetPnlRecomputed=False)

def replay(input_root,output,classpath,inputs):
    frozen=json.loads(Path('research/phase6/expanded-pool-freeze.json').read_text())
    for p,s in frozen['filesSha256'].items():
        if file_sha(p)!=s:raise ValueError('Frozen643 replay dependency changed '+p)
    tapes=list(Path(input_root).rglob('events.jsonl.gz'))
    if len(tapes)!=1 or file_sha(tapes[0])!=STORED_SHA:raise ValueError('Exactly one unchanged original source required')
    inputs=Path(inputs);pool=build();raw=(json.dumps(pool,separators=(',',':'))+'\n').encode()
    if (inputs/'pool.json').read_bytes()!=raw or digest(raw)!=frozen['poolLogicalSha256']:raise ValueError('Changed643 pool')
    expected=next_missing(pool);config=json.loads(Path('research/phase2/research-config.json').read_text())
    out=Path(output);out.mkdir(parents=True,exist_ok=False);results={}
    for p in ('baseline','candidate'):
        target=out/p
        with (out/(p+'.log')).open('w') as log:
            process=subprocess.run(['java','-Xmx1g','-cp',classpath,'com.polybot.hft.paper.NativeReplaySupport',
                str(tapes[0]),str(target),'research/phase2/research-config.json',str(inputs/'pool.json'),p],stdout=log,stderr=subprocess.STDOUT,timeout=180)
        if process.returncode==0 or not (target/'failure.json').exists() or (target/'report.json').exists():raise ValueError('Missing strict next-blocker diagnostic')
        results[p]=verify_stop(json.loads((target/'failure.json').read_text()),expected,p=='candidate',config)
    if results['baseline']!=results['candidate']:raise ValueError('Policies stopped at different original unknowns')
    result=dict(scope='SAME_ORIGINAL_SOURCE_EXPANDED643_NEXT_BLOCKER_NOT_ACCOUNT_COMPARISON',poolLogicalSha256=digest(raw),
        inputStoredSha256=STORED_SHA,results=results,fullOriginalTapeCoverageProven=False,
        completeAccountComparisonPerformed=False,marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False)
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--input-root');p.add_argument('--classpath');p.add_argument('--inputs');a=p.parse_args()
    print(json.dumps(replay(a.input_root,a.output,a.classpath,a.inputs) if a.input_root else write(a.output),indent=2))
