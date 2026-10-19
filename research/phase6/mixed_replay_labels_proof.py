"""Cross-language adapter identity/quantity/side/price parity; never account PnL."""
import argparse
from decimal import Decimal as D,localcontext,ROUND_CEILING,ROUND_FLOOR
import hashlib
import json
from pathlib import Path
from research.phase6.mixed_replay_labels import export


def portions_sha(root):
    digest=hashlib.sha256();seen=set()
    for b in root['bindings']:
        for match in b['matches']:
            m=match['maker'];buy=m['side']=='BUY'
            q=m['takingRaw'] if buy else m['makingRaw'];c=m['makingRaw'] if buy else m['takingRaw']
            identity=f"{match['exchange']}:{b['transactionHash']}:{match['ordersMatchedLogIndex']}:{m['logIndex']}"
            if identity in seen or not 0<c<q:raise ValueError('Duplicate/invalid original component')
            seen.add(identity)
            with localcontext() as ctx:
                ctx.prec=100
                price=(D(c)/D(q)).quantize(D('1e-28'),rounding=ROUND_CEILING if buy else ROUND_FLOOR)
                quantity=D(q)/1000000
                line=f"{b['seq']}|{b['eventIndex']}|{identity}|{m['token']}|{m['side']}|{price:.28f}|{quantity:.6f}\n"
            digest.update(line.encode())
    if len(seen)!=root['expectedComponentCount']:raise ValueError('Incomplete component parity')
    return digest.hexdigest()


def verify(report):
    root=export();raw=(json.dumps(root,indent=2)+'\n').encode()
    if (report['experiment']!='CONSERVED-MIXED-LAB0' or report['bindings']!=451 or report['consumedBindings']!=451
            or report['actualComponents']!=1038 or report['originalObservations']!=451 or report['duplicateAggregateSuppressed']!=0
            or report['labelsSha256']!=hashlib.sha256(raw).hexdigest() or report['portionsLogicalSha256']!=portions_sha(root)
            or not report['adapterOnlyNotAccountReplay'] or report['modelFillsCreated']!=0
            or report['candidateAccountSimulated'] or report['netPnlRecomputed'] or report['newPublicReads']!=0
            or report['independentPaperQualificationAllowed'] or report['liveAllowed']):raise ValueError('Mixed adapter parity/scope differs')
    return dict(scope='INDEPENDENT_ALL451_MIXED_ADAPTER_PARITY_NOT_ACCOUNT',bindings=451,actualComponents=1038,
        portionsLogicalSha256=report['portionsLogicalSha256'],routeComponentCounts=root['routeComponentCounts'],
        modelFillsCreated=0,netPnlRecomputed=False,candidateAccountSimulated=False,
        independentPaperQualificationAllowed=False,liveAllowed=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('report');a=p.parse_args()
    print(json.dumps(verify(json.loads(Path(a.report).read_text())),indent=2))
