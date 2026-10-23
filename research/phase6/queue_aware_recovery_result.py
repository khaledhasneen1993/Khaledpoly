"""Reproduce ALL451 source-bound integer route labels offline, never execution."""
import hashlib
import json
import zipfile
from research.phase6.queue_aware_causal import QROOT
from research.phase6.queue_aware_recovery_receipts import selection,decode

ROOT=QROOT/'recovery-result'
SHA='329c0cb43e316a30c61a78d0ae976a05a248d09fb50e7ea5ac103578cde1fcb5'


def load():
    path=ROOT/'artifact.zip'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=SHA:raise ValueError('Changed original451 archive')
    spec=selection();expected={'selection.json','report.json','component-summary.json'}|{f"raw/{t['transactionHash']}.json" for t in spec['transactions']}
    with zipfile.ZipFile(path) as z:
        if len(z.infolist())!=454 or set(z.namelist())!=expected or any(i.file_size>4000000 for i in z.infolist()):raise ValueError('Wrong bounded451 archive members')
        if json.loads(z.read('selection.json'))!=spec:raise ValueError('Changed original451 selection')
        r=json.loads(z.read('report.json'))
        if (not r['complete'] or r['errors'] or r['requested']!=451 or r['reusedReceipts']!=0
                or r['rpcCalls']!={'eth_chainId':1,'eth_getTransactionReceipt':451,'eth_getBlockByHash':17}
                or r['fillsCreated']!=0 or r['netPnlRecomputed'] or r['liveAllowed']):raise ValueError('Incomplete original451 proof')
        e={t['transactionHash']:dict(data=json.loads(z.read(f"raw/{t['transactionHash']}.json")),topics=r['eventTopics']) for t in spec['transactions']}
        summary=json.loads(z.read('component-summary.json'))
    return spec,e,summary


def verify(spec,evidence,summary):
    if spec!=selection() or set(evidence)!={t['transactionHash'] for t in spec['transactions']}:raise ValueError('Incomplete/changed original451, unknown is not zero')
    rows=[decode(t,evidence[t['transactionHash']]['data'],evidence[t['transactionHash']]['topics'],spec['pair']) for t in spec['transactions']]
    ids=[p['identity'] for r in rows for p in r['parts']]
    expected=dict(scope=spec['scope'],complete=True,observations=451,results=rows,uniqueMakerComponents=len(ids),
        genericBothMakerSidesAndBothTokens=True,queueAndStrategyLifecycleNotSimulated=True,
        fillsCreated=0,netPnlRecomputed=False,candidateAccountSimulated=False,independentPaperQualificationAllowed=False,liveAllowed=False)
    if len(ids)!=len(set(ids)) or expected!=summary:raise ValueError('Actual451 conserved components/scope differ')
    return dict(scope=spec['scope'],completeOriginalGroups=451,uniqueActualMakerComponents=len(ids),
        bothSidesAndTokensDecoded=True,queueAndLifecycleNotSimulated=True,
        fillsCreated=0,netPnlRecomputed=False,candidateAccountSimulated=False,
        independentPaperQualificationAllowed=False,liveAllowed=False)


if __name__=='__main__':print(json.dumps(verify(*load()),indent=2))
