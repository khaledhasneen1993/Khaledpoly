"""Reproduce frozen14 raw receipts offline. Necessary volume is NOT a model fill."""
import base64
import hashlib
import io
import json
import zipfile
from research.phase6.queue_aware_causal import QROOT
from research.phase6.queue_aware_gap_tail_receipts import selection, summarize

ROOT=QROOT/'gap-tail-result'
SHA='0b6570d1cffb396b4bc2345d0a1db563ddca4d5bd38ae1320167b092ce776e82'


def load():
    raw=base64.b64decode((ROOT/'artifact.zip.b64').read_bytes(),validate=False)
    if hashlib.sha256(raw).hexdigest()!=SHA:raise ValueError('Changed original tail14 archive')
    spec=selection()
    expected={'selection.json','component-summary.json','report.json'}|{f"raw/{t['transactionHash']}.json" for t in spec['transactions']}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if len(z.infolist())!=17 or set(z.namelist())!=expected or any(i.file_size>4000000 for i in z.infolist()):raise ValueError('Wrong bounded14 members')
        if json.loads(z.read('selection.json'))!=spec:raise ValueError('Changed original tail source selection')
        r=json.loads(z.read('report.json'))
        if (r['scope']!=spec['scope'] or not r['complete'] or r['errors'] or r['requested']!=14
                or r['rpcCalls']!={'eth_chainId':1,'eth_getTransactionReceipt':14,'eth_getBlockByHash':2}
                or r['fillsCreated']!=0 or r['netPnlRecomputed'] or r['liveAllowed']):raise ValueError('Incomplete frozen14 receipt scope')
        e={t['transactionHash']:dict(data=json.loads(z.read(f"raw/{t['transactionHash']}.json")),topics=r['eventTopics']) for t in spec['transactions']}
        summary=json.loads(z.read('component-summary.json'))
    return spec,e,summary


def verify(spec,evidence,summary):
    if spec!=selection():raise ValueError('Changed original source tail window')
    if set(evidence)!={t['transactionHash'] for t in spec['transactions']}:raise ValueError('Incomplete receipt cohort: unknown is not zero')
    if summarize(spec,evidence)!=summary:raise ValueError('Actual conserved tail components differ')
    return dict(scope=spec['scope'],completeOriginalObservations=14,
        actualBPriceCompatibleSharesRaw=summary['actualPriceCompatibleSharesRaw'],
        actualASellPriceCompatibleSharesRaw=summary['hedgeSellPriceCompatibleSharesRaw'],
        necessaryVolumeIsNotQueueAllocation=True,hedgeQueueAndLifecycleNotSimulated=True,
        sourceWindowStartExclusiveMs=spec['afterCancelAckExclusiveMs'],sourceWindowEndExclusiveMs=spec['fixedHorizonMs'],
        actualBotFillsCreated=0,netPnlRecomputed=False,candidateAccountSimulated=False,
        independentPaperQualificationAllowed=False,liveAllowed=False,
        decision='FREEZE_SEPARATE_ACTIVE_REDUCTION_GATE_WITH_SIDE_CONSERVATIVE_COMPONENT_PRICES')


if __name__=='__main__':print(json.dumps(verify(*load()),indent=2))
