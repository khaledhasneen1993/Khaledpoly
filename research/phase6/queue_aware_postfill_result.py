"""Offline reproduction of all79 actual post-fill receipts, never account PnL."""
import base64
import hashlib
import io
import json
import zipfile
from research.phase6.queue_aware_causal import QROOT
from research.phase6.queue_aware_postfill_receipts import selection,summarize

ROOT=QROOT/'postfill-result'
SHA='81a680473c83a641fcb3a5df36a334853cf6a0e78bc817a01c29770b36e8bfae'


def load():
    raw=base64.b64decode((ROOT/'artifact.zip.b64').read_bytes())
    if hashlib.sha256(raw).hexdigest()!=SHA:raise ValueError('Changed original post-fill79 archive')
    spec=selection();expected={'selection.json','component-summary.json','report.json'}|{f"raw/{t['transactionHash']}.json" for t in spec['transactions']}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if len(z.infolist())!=82 or set(z.namelist())!=expected or any(i.file_size>4000000 for i in z.infolist()):raise ValueError('Wrong bounded79 members')
        if json.loads(z.read('selection.json'))!=spec:raise ValueError('Changed source prefix selection')
        r=json.loads(z.read('report.json'))
        if (not r['complete'] or r['errors'] or r['requested']!=79 or r['rpcCalls']!={'eth_chainId':1,'eth_getTransactionReceipt':79,'eth_getBlockByHash':5}
                or r['fillsCreated']!=0 or r['netPnlRecomputed'] or r['liveAllowed']):raise ValueError('Incomplete/no-fill receipt scope')
        e={t['transactionHash']:dict(data=json.loads(z.read(f"raw/{t['transactionHash']}.json")),topics=r['eventTopics']) for t in spec['transactions']}
        summary=json.loads(z.read('component-summary.json'))
    return spec,e,summary


def verify(spec,evidence,summary):
    if spec!=selection():raise ValueError('Changed original conditional post-fill source window')
    if summarize(spec,evidence)!=summary:raise ValueError('Actual conserved post-fill components differ')
    return dict(scope=spec['scope'],completeOriginalObservations=79,actualPriceCompatibleSharesRaw=summary['actualPriceCompatibleSharesRaw'],
        sourceWindowStartExclusiveMs=spec['firstModelAllocationMs'],sourceWindowEndInclusiveMs=spec['fixedHorizonMs'],
        causalAllocationAndAccountNotSimulated=True,fillsCreated=0,netPnlRecomputed=False,
        independentPaperQualificationAllowed=False,liveAllowed=False,
        decision='REPLAY_ACTUAL_BOTH_ORDER_WAIT_CANCEL_WITH_ALL_RECORDED_GROUPS_THEN_HEDGE_EXIT')


if __name__=='__main__':print(json.dumps(verify(*load()),indent=2))
