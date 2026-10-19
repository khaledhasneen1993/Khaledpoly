"""Replay exact thirty raw counterpart receipts offline; never manufacture fills."""
import base64
import hashlib
import io
import json
import zipfile
from research.phase6.queue_aware_causal import QROOT
from research.phase6.queue_aware_counterpart import selection,summarize

ROOT=QROOT/'counterpart-result'
SHA='c7fa33ad5faad12940cdeb11405253cd6c98b5a41118f2813758072befc1626a'


def load():
    raw=base64.b64decode((ROOT/'artifact.zip.b64').read_bytes())
    if hashlib.sha256(raw).hexdigest()!=SHA:raise ValueError('Changed original counterpart30 ZIP')
    spec=selection();expected={f"raw/{t['transactionHash']}.json" for t in spec['transactions']}|{'selection.json','report.json','component-summary.json'}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if len(z.infolist())!=33 or set(z.namelist())!=expected or any(i.file_size>4000000 for i in z.infolist()):
            raise ValueError('Wrong counterpart30 artifact members/bounds')
        if json.loads(z.read('selection.json'))!=spec:raise ValueError('Changed frozen source cohort')
        report=json.loads(z.read('report.json'))
        if (not report['complete'] or report['errors'] or report['requested']!=30
                or report['rpcCalls']!={'eth_chainId':1,'eth_getTransactionReceipt':30,'eth_getBlockByHash':3}
                or report['fillsCreated']!=0 or report['netPnlRecomputed'] or report['liveAllowed']):
            raise ValueError('Incomplete/wrong no-fill source receipt report')
        evidence={t['transactionHash']:dict(data=json.loads(z.read(f"raw/{t['transactionHash']}.json")),topics=report['eventTopics'])
            for t in spec['transactions']}
        summary=json.loads(z.read('component-summary.json'))
    return spec,evidence,summary


def verify(spec,evidence,summary):
    if spec!=selection():raise ValueError('Original counterpart prefix selection differs')
    result=summarize(spec,evidence)
    if result!=summary:raise ValueError('Original actual component reconstruction differs')
    return dict(scope='REPRODUCED_COMPLETE30_COUNTERPART_PRICED_COMPONENTS_NOT_ACCOUNT',
        originalSequence=243583,fixedHorizonMs=spec['fixedHorizonMs'],completeOriginalObservations=30,
        actualPriceCompatibleSharesRaw=result['actualPriceCompatibleSharesRaw'],
        counterpartAfterHorizonAudited=False,actualBotFillsCreated=0,candidateAccountSimulated=False,
        netPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False,
        decision='REQUIRE_BOTH_ACTUAL_ORDER_ACTIVATIONS_AND_COMPLETE_HEDGE_EXIT_ACCOUNT_PATH')


if __name__=='__main__':print(json.dumps(verify(*load()),indent=2))
