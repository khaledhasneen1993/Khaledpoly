"""Retained first-blocker proof plus ONE bounded public read-only receipt request."""
import argparse
from collections import Counter
from decimal import Decimal as D
import gzip
import hashlib
import io
import json
from pathlib import Path
import zipfile
from research.phase6.full_runner_diagnosis import first_missing,verify_failure
from research.phase6.receipt_audit import rpc,corroborate
from research.phase6.route_coverage_audit import routes

ROOT=Path('research/experiments/full-native-runner-20261020')
ARTIFACT_SHA='5a251717de06ad26c2920180fcc5fa8ec4fad72d725f64f02f85d742833e74a4'
RECOVERY=Path('research/experiments/queue-aware-quote-20261019/recovery-result/artifact.zip')

def digest(raw):return hashlib.sha256(raw).hexdigest()

def retained(path=ROOT/'original-diagnosis.zip'):
    raw=Path(path).read_bytes()
    if digest(raw)!=ARTIFACT_SHA:raise ValueError('Changed original first-blocker artifact')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if len(set(z.namelist()))!=len(z.namelist()) or any(m.file_size>1024*1024 for m in z.infolist()):raise ValueError('Invalid proof archive')
        read=lambda name:json.loads(z.read(name))
        proofs={p:read('original-diagnosis/'+p+'/failure.json') for p in ('baseline','candidate')}
        config=json.loads(Path('research/phase2/research-config.json').read_text());expected=first_missing()
        results={p:verify_failure(proofs[p],expected,p=='candidate',config) for p in proofs}
        saved=read('original-diagnosis/verification.json')
        if (saved['results']!=results or saved['sameOriginalBlocker'] is not True
                or saved['inputStoredSha256']!='9363443ae9287016ab7c63d3cf11d6b1ae33d814d9e3ad340bb99b33e7285074'
                or saved['poolLogicalSha256']!='745dadce6749d701ba6048ab1ef76f3f43b354c058e27e9163c2174725aaceea'
                or saved['freezeSha256']!=digest(Path('research/phase6/full-runner-freeze.json').read_bytes())):
            raise ValueError('Changed source/freeze/first-blocker verification')
        for policy,proof in proofs.items():
            ledger=proof['ledgerAfterSuspension']
            if (z.read('original-diagnosis/'+policy+'/failure-audit.jsonl')!=b''
                    or ledger['orders'] or ledger['holdings'] or ledger['executions']
                    or D(str(ledger['cash']))!=500 or D(str(ledger['realized']))!=0 or D(str(ledger['fees']))!=0):
                raise ValueError('This retained prefix must have no orders/holdings/executions/audit')
        source=proofs['candidate']['labels']['lastAttemptedOriginalObservation']
    return dict(scope='VERIFIED_SAME_SOURCE_FIRST_BLOCKER_NOT_ACCOUNT_PERFORMANCE',
        sourceArtifactSha256=ARTIFACT_SHA,seq=expected['seq'],eventIndex=expected['eventIndex'],
        sameOriginalBlocker=True,noOrdersOrExecutionsBeforeBlocker=True,
        noOrderOptimizationProven=False,completeAccountComparisonPerformed=False,
        marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False),source,expected

def selection():
    proof,source,expected=retained();data=source['observation'];sample=json.loads(data['tradeId'])
    raw=gzip.decompress(Path('research/experiments/cached-receipt-pool-20261020/bindings.json.gz').read_bytes())
    if digest(raw)!='745dadce6749d701ba6048ab1ef76f3f43b354c058e27e9163c2174725aaceea':raise ValueError('Changed reviewed partial pool')
    pool=json.loads(raw);meta=pool['metadataIdentityReference']
    if (expected['condition']!=meta['condition'] or sample['market']!=meta['condition'] or data['token'] not in meta['pair']
            or expected['transactionHash'] in {b['transactionHash'] for b in pool['bindings']}):raise ValueError('Unproven/previously bound blocker pair')
    recovery=RECOVERY.read_bytes()
    if digest(recovery)!='329c0cb43e316a30c61a78d0ae976a05a248d09fb50e7ea5ac103578cde1fcb5':raise ValueError('Changed reviewed event topics')
    with zipfile.ZipFile(io.BytesIO(recovery)) as z:topics=json.loads(z.read('report.json'))['eventTopics']
    return dict(scope='ONE_EXACT_ORIGINAL_FIRST_BLOCKER_RECEIPT_NOT_EXECUTION',
        sourceArtifactSha256=ARTIFACT_SHA,seq=source['seq'],eventIndex=source['eventIndex'],at=source['at'],
        originalTradeId=data['tradeId'],publicTradeIdSha256=expected['publicTradeIdSha256'],
        transactionHash=expected['transactionHash'],sample=sample,pair=meta['pair'],condition=meta['condition'],
        topics=topics,maxNewReceiptRequests=1,maxNewBlockRequests=1,
        noPriceOrOutcomeSelection=True,modelFillsCreated=0,marketNetPnlRecomputed=False,liveAllowed=False)

def decode(spec,data):
    result=corroborate(spec['sample'],data['receipt'],data['block'],spec['topics'])
    route=routes(result,set(spec['pair']))
    if not route['uniqueConservedGroup']:raise ValueError('Unknown/ambiguous first-blocker conserved group; never zero')
    return route

def collect(spec,output,*,read=rpc):
    if spec!=selection():raise ValueError('Only exact frozen one-transaction selection authorized')
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    canonical=json.dumps(spec,sort_keys=True,separators=(',',':'))+'\n';p=out/'selection.json'
    if p.exists() and p.read_text()!=canonical:raise ValueError('Changed selection on resume')
    p.write_text(canonical);raw=out/'raw.json';data=json.loads(raw.read_text()) if raw.exists() else {};calls=Counter()
    def query(method,params):
        limits={'eth_chainId':1,'eth_getTransactionReceipt':1,'eth_getBlockByHash':1}
        if method not in limits or calls[method]>=limits[method]:raise ValueError('One-receipt public read budget exceeded')
        calls[method]+=1;return read(method,params)
    report=dict(scope=spec['scope'],complete=False,modelFillsCreated=0,marketNetPnlRecomputed=False,
        candidateAccountSimulated=False,independentPaperQualificationAllowed=False,liveAllowed=False)
    try:
        if int(query('eth_chainId',[]),16)!=137:raise ValueError('Wrong public chain')
        if 'receipt' not in data:
            data['receipt']=query('eth_getTransactionReceipt',[spec['transactionHash']])
            raw.write_text(json.dumps(data,separators=(',',':'))+'\n')
        if not data['receipt']:raise ValueError('Original receipt absent; unknown is not zero')
        if 'block' not in data:
            data['block']=query('eth_getBlockByHash',[data['receipt']['blockHash'],False])
            raw.write_text(json.dumps(data,separators=(',',':'))+'\n')
        route=decode(spec,data);report.update(complete=True,route=route,rawSha256=digest(raw.read_bytes()))
    except (OSError,ValueError,KeyError,TypeError) as error:
        report['error']=str(error)[:300]
    report['rpcCalls']=dict(calls);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    if not report['complete']:raise ValueError('First blocker unresolved; retain checkpoint and do not invent label')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output');a=p.parse_args()
    print(json.dumps(collect(selection(),a.output) if a.output else retained()[0],indent=2))
