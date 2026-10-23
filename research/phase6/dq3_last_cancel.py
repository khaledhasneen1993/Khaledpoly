"""Prepare/verify bounded counterfactual resting-risk cancellation; never account profit."""
import argparse
import base64
from decimal import Decimal as D,ROUND_CEILING
import gzip
import hashlib
import io
import json
from pathlib import Path
import zipfile
from research.phase6.dq3_bottleneck_receipts import ROOT,traffic
from research.phase6.entry_witness_result import load as witness_archive

SHA='9c16e42982477344f1c7e62fa3beda92c0533b4184dc3edb585b2a42a4489808'


def load():
    raw=base64.b64decode((ROOT/'last-activation-result/artifact.zip.b64').read_bytes())
    if hashlib.sha256(raw).hexdigest()!=SHA:raise ValueError('Changed last activation artifact')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if {i.filename:i.file_size for i in z.infolist()}!={'activation.json':1990,'context.json.gz':637785}:
            raise ValueError('Wrong last activation artifact members')
        gz=z.read('context.json.gz')
        with gzip.GzipFile(fileobj=io.BytesIO(gz)) as inp:b=inp.read(64000001)
        if len(b)>64000000:raise ValueError('Oversized original context')
        return json.loads(b),json.loads(z.read('activation.json'),parse_float=D),gz


def evidence(context,activation):
    frozen=json.loads(Path('research/phase6/dq3-last-activation-freeze.json').read_text())
    if context['spec']!=frozen['spec'] or context['logicalTapeSha256']!=frozen['spec']['logicalTapeSha256']:
        raise ValueError('Wrong immutable original context')
    if (not activation['allTradeVolumeSuppressed'] or activation['fillsCreated']!=0 or activation['netPnlRecomputed']
            or activation['actualRestingCancellationSimulated'] or len(activation['results'])!=1):
        raise ValueError('Wrong activation-only scope')
    r=activation['results'][0];s=frozen['spec']['states'][0];d=r['diagnostic']
    if (r['state']!=s or not r['sameFirstDueInput'] or r['tickChangeSinceSubmission']
            or r['activationOutcomeSequence']!=299997 or d['activatedMs']!=s['activationDueMs']
            or d['initialQueueAhead']!=200 or d['terminalMs'] is not None):
        raise ValueError('Wrong/ambiguous actual-engine activation seed')
    report=json.loads(witness_archive()['report.json'],parse_float=D)
    entry=next(w for w in report['entryDecisionWitnesses'] if w['originalSequence']==299650)
    check=next(w for w in report['entryDecisionWitnesses'] if w['originalSequence']==299997)
    if entry['nextDecisionMs']!=check['at'] or check['at']!=d['activatedMs'] or check['condition']!=s['condition']:
        raise ValueError('Wrong original first scheduled risk-check witness')
    if (entry['openOrderIds'] or entry['imbalance']!=0 or entry['ledgerHalted'] or entry['entryStopped']
            or check['imbalance']!=0 or not check['firstFresh'] or not check['secondFresh']):
        raise ValueError('Unsupported independent flat-start state')
    # Actual decisions occur AFTER the entire original frame. Prove both full
    # source books match the immutable observed risk witness at that callback.
    books={};pre=None;seen_anchor=False;seen_check=False
    for record in context['records']:
        row=record['input'];events=row['data']['events'] if row['kind']=='RESEARCH_FRAME' else [dict(kind=row['kind'][9:],data=row['data'])]
        if row['seq']==299997:pre=books.get(s['targetQuote']['token'])
        for event in events:
            ed=event['data']
            if event['kind']=='BOOK':books[ed['token']]=ed
            elif event['kind'] in ('GAP','FEED_ERROR'):
                affected=set(ed.get('tokens',[]))|({ed['token']} if 'token' in ed else set())
                pair={q['token'] for q in s['quotes']}
                if not affected or affected&pair:books={}
        if row['seq']==299650:seen_anchor=row['arrivalMs']==s['submitMs']
        if row['seq']==299997:
            if row['arrivalMs']!=check['at']:raise ValueError('Changed risk-check source time')
            seen_check=True;break
    if not seen_anchor or not seen_check or not pre:raise ValueError('Missing original source anchors')
    own=next(D(str(l['size'])) for l in pre['bids'] if D(str(l['price']))==D(s['targetQuote']['price']))
    if own*2!=d['initialQueueAhead']:raise ValueError('Pre-event queue seed changed')
    for token,key in [(check['market']['first'],'firstBook'),(check['market']['second'],'secondBook')]:
        b=books[token];w=check[key]
        if b['sourceMs']!=w['sourceMs']:raise ValueError('Wrong risk-check book source')
        for side,rev in [('bids',True),('asks',False)]:
            levels=sorted(((D(str(l['price'])),D(str(l['size']))) for l in b[side]),reverse=rev)[:3]
            if levels!=[(l['price'],l['size']) for l in w[side]]:raise ValueError('Post-frame full book differs from witness')
    cfg=json.loads(Path('research/phase2/research-config.json').read_text())
    q=D(s['targetQuote']['quantity']);priceA=D(s['quotes'][0]['price']);priceB=D(s['quotes'][1]['price'])
    depth=min(check['firstBook']['bids'][0]['size'],check['secondBook']['bids'][0]['size'])
    vol=max(check['firstObservedVolatility'],check['secondObservedVolatility'])
    thin=min((D(1)/max(D(1),depth)).quantize(D('.00000001'),rounding=ROUND_CEILING),D('.02'))
    expiry=D('.02') if check['secondsToExpiry']<60 else D('.01') if check['secondsToExpiry']<180 else D(0)
    required=D(cfg['minimumEdge'])+vol*D('.5')+expiry+thin
    net=(1-priceA-priceB)*q-D(cfg['mergeCost'])
    if required!=check['requiredEdge'] or cfg['activationMs']!=250 or cfg['cancelMs']!=250 or not net<required*q:
        raise ValueError('Unchanged resting-risk check does not require cancellation')
    if not(priceA<check['firstBook']['asks'][0]['price'] and priceB<check['secondBook']['asks'][0]['price']):
        raise ValueError('Risk reason would instead be price invalid')
    observations=next(x for x in traffic()['states'] if x['selection']['originalSequence']==299650)['observations']
    own_obs=[o for o in observations if o['targetToken']==s['targetQuote']['token']]
    earliest=min(o['arrivalMs'] for o in own_obs);due=check['at']+cfg['cancelMs']
    if earliest<=due:raise ValueError('Cannot reject prints inside cancellation race')
    return dict(scope='CONDITIONAL_FIRST_SCHEDULED_RESTING_RISK_CANCEL_NOT_ACTUAL_ACCOUNT',
        state=s,entryWitness=entry,riskWitness=check,config=cfg,expectedCancelRequestMs=check['at'],
        expectedCancelDueMs=due,firstPossibleTargetPrintArrivalMs=earliest,
        restingQuantity=str(q),netEdgeTotal=str(net),requiredEdge=str(required),requiredEdgeTotal=str(required*q),
        initialQueueAhead=str(d['initialQueueAhead']),allTargetObservationsAfterCancelDue=True,
        candidateAccountSimulated=False,fillsCreated=0,netPnlRecomputed=False,liveAllowed=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    f=json.loads(Path('research/phase6/dq3-last-cancel-freeze.json').read_text())
    for path,sha in f['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Changed frozen input '+path)
    context,activation,gz=load();e=evidence(context,activation);out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    (out/'context.json.gz').write_bytes(gz)
    # Keep numeric witness literals exact for the actual Java PairPolicy.
    from research.phase6.entry_witness_result import load as original
    (out/'witness-report.json').write_bytes(original()['report.json'])
    (out/'evidence.json').write_text(json.dumps(e,default=str,indent=2)+'\n')


if __name__=='__main__':main()
