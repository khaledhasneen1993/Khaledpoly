"""Immutable observational replay proof; retain actual reasons, never infer executions."""
import base64
from collections import Counter
from decimal import Decimal as D, ROUND_CEILING, ROUND_DOWN
import io
import json
from pathlib import Path
import zipfile
import hashlib
from research.phase6.entry_decision_witness import golden, verify_report

ROOT=Path('research/experiments/entry-decision-witness-20261018')
SHA='934abe8054ebbc30c3c9625d65176843f63a0bfbe39676f9b50ce2c3e6ffc6e6'


def load():
    raw=base64.b64decode((ROOT/'result/artifact.zip.b64').read_bytes())
    if hashlib.sha256(raw).hexdigest()!=SHA:raise ValueError('Witness artifact changed')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if {i.filename:i.file_size for i in z.infolist()}!={'report.json':104007,'audit.jsonl':3619874,'witness-verification.json':336}:
            raise ValueError('Unexpected witness artifact members')
        return {n:z.read(n) for n in z.namelist()}


def verify_rows(rows,config,windows):
    counts=Counter();last=-1
    for r in rows:
        if r['at']<=last or r['originalSequence']<=0 or r['nextDecisionMs']!=r['at']+config['decisionMillis']:
            raise ValueError('Actual decision chronology/source mismatch')
        last=r['at'];m=r['market'];a=r['firstBook'];b=r['secondBook']
        if m['condition']!=r['condition'] or m['observedMs']>r['at']:raise ValueError('Future/wrong metadata')
        for book in (a,b):
            if book['sourceMs']>r['at'] or book['receivedMs']>r['at']:raise ValueError('Future book')
        depth=min(a['bids'][0]['size'],b['bids'][0]['size'])
        q=min(D(config['orderShares']),D(depth)*D('.1')).quantize(D('.01'),rounding=ROUND_DOWN)
        if q!=r['quantity'] or depth!=r['depth']:raise ValueError('Causal size formula differs')
        vol=max(r['firstObservedVolatility'],r['secondObservedVolatility'])
        expiry=D('.02') if r['secondsToExpiry']<60 else D('.01') if r['secondsToExpiry']<180 else D(0)
        thin=min((D(1)/max(D(depth),D(1))).quantize(D('.00000001'),rounding=ROUND_CEILING),D('.02'))
        required=D(config['minimumEdge'])+D(vol)*D('.5')+expiry+thin
        if required!=r['requiredEdge'] or vol!=r['effectivePolicyVolatility']:raise ValueError('Actual risk premium differs')
        net=(1-r['firstBid']-r['secondBid'])*q-D(config['mergeCost'])
        if net!=r['netEdgeTotal']:raise ValueError('Actual net edge differs')
        reason=r['actualDecisionReasonDelta']
        if len(reason)!=1 or list(reason.values())!=[1]:raise ValueError('Ambiguous actual branch')
        k=next(iter(reason));counts[k]+=1
        small=q<m['minSize'];edge_bad=net<required*q
        if (k=='MIN_SIZE' and (not small or edge_bad) or k=='NET_EDGE' and (small or not edge_bad)
                or k=='MIN_SIZE_AND_NET_EDGE' and not(small and edge_bad)):
            raise ValueError('Actual rejection does not match inputs')
    if any(not any(w['condition']==r['condition'] and w['startMs']<=r['at']<=w['endMs'] for r in rows) for w in windows):
        raise ValueError('A frozen window has no decision witness')
    return dict(counts)


def analyze():
    data=load();report=json.loads(data['report.json']);windows=json.loads((ROOT/'windows.json').read_text())
    verified=verify_report(report,golden(),windows)
    if verified!=json.loads(data['witness-verification.json']):raise ValueError('Original verification differs')
    exact=json.loads(data['report.json'],parse_float=D)
    config=json.loads(Path('research/phase2/research-config.json').read_text())
    counts=verify_rows(exact['entryDecisionWitnesses'],config,windows)
    old=base64.b64decode(Path('research/experiments/residual-entry-risk-20261018/result/artifact.zip.b64').read_bytes())
    with zipfile.ZipFile(io.BytesIO(old)) as z:original=z.read('candidate/audit.jsonl')
    if [json.loads(l) for l in original.splitlines()]!=[json.loads(l) for l in data['audit.jsonl'].splitlines()]:
        raise ValueError('Observational replay changed original audit actions')
    return dict(scope='ACTUAL_ENTRY_WITNESS_RESULT_NOT_STRATEGY_PERFORMANCE',artifactZipSha256=SHA,
        sourceRun=39168798844,artifactId=12152096415,originalFieldsReproduced=verified['originalAccountFieldCount'],
        originalAuditActionsReproduced=True,windowsCovered=len(windows),witnessCount=len(exact['entryDecisionWitnesses']),
        actualBranchCounts=counts,minSizeRejections=counts.get('MIN_SIZE',0)+counts.get('MIN_SIZE_AND_NET_EDGE',0),
        insufficientEdgeRejections=counts.get('NET_EDGE',0)+counts.get('MIN_SIZE_AND_NET_EDGE',0),
        accountNetPnl=report['netRealizedPnl'],fills=report['fills'],fillsInferred=False,
        decision='NO_GO',independentPaperQualificationAllowed=False,liveAllowed=False)


if __name__=='__main__':
    print(json.dumps(analyze(),indent=2))
