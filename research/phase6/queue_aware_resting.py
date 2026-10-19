"""Frozen conditional no-counterpart resting lifetime; never an account replay."""
import argparse
from decimal import Decimal as D, ROUND_CEILING, ROUND_HALF_EVEN, ROUND_FLOOR
import gzip
import hashlib
import json
from pathlib import Path
from research.phase6.entry_witness_result import load as witnesses
from research.phase6.queue_aware_causal_result import load, verify


def policy(a,b,vol,at,market,cfg,prices,quantity,submitted):
    depth=min(a['bids'][0]['size'],b['bids'][0]['size'])
    required=(D(cfg['minimumEdge'])+vol*D('.5')
        +(D('.02') if (market['endMs']-at)//1000<60 else D('.01') if (market['endMs']-at)//1000<180 else D(0))
        +min((1/max(depth,D(1))).quantize(D('.00000001'),rounding=ROUND_CEILING),D('.02')))
    valid=all(p%market['tick']==0 and p<book['asks'][0]['price'] for p,book in zip(prices,[a,b]))
    net=(1-sum(prices))*quantity-D(cfg['mergeCost'])
    reason='RESTING'
    if not valid:reason='RESTING_PRICE_INVALID'
    elif net<required*quantity:reason='RESTING_NET_EDGE'
    else:
        # Existing runtime default makerImprovementTicks=1, NOT a new QW0 reprice rule.
        bids=[(min(book['bids'][0]['price']+market['tick'],book['asks'][0]['price']-market['tick'])
            /market['tick']).to_integral_value(rounding=ROUND_FLOOR)*market['tick'] for book in [a,b]]
        size=min(D(cfg['orderShares']),depth*D('.1')).quantize(D('.01'),rounding=ROUND_FLOOR)
        improve=any(p<book['bids'][0]['price'] for p,book in zip(prices,[a,b]))
        lawful=all(p>0 and p<book['asks'][0]['price'] for p,book in zip(bids,[a,b]))
        if improve and lawful and size>=market['minSize'] and (1-sum(bids))*size-D(cfg['mergeCost'])>=required*size and at-submitted>=2000:
            reason='REPRICE_VALIDATED_PAIR'
    return dict(at=at,reason=reason,depth=str(depth),volatility=str(vol),secondsToExpiry=(market['endMs']-at)//1000,
        requiredEdge=str(required),reservedNetEdgeTotal=str(net),validPrices=valid)


def timeline(context,manifest,causal):
    verify(context,manifest,causal)
    cfg=json.loads(Path('research/phase2/research-config.json').read_text())
    report=json.loads(witnesses()['report.json'],parse_float=D)
    anchor=next(w for w in report['entryDecisionWitnesses'] if w['originalSequence']==243583)
    if anchor['openOrderIds'] or anchor['imbalance']!=0 or anchor['entryStopped'] or anchor['ledgerHalted']:
        raise ValueError('No unchanged independent flat-state seed')
    state=manifest['state'];pair=[anchor['market']['first'],anchor['market']['second']]
    books={};mids={};vols={};checks=[];seeded=False;next_at=anchor['nextDecisionMs'];observed=anchor['market']['observedMs']
    original={w['originalSequence']:w for w in report['entryDecisionWitnesses']};validated=[]
    horizon=causal['conditionalModelFills'][0]['at']
    market=anchor['market'];prices=[D(q['price']) for q in state['quotes']];quantity=D(state['targetQuote']['quantity'])
    for rec in context['records']:
        row=rec['input'];seq=row['seq'];at=row['arrivalMs'];kind=row['kind'][9:];data=row['data']
        if at>horizon:break
        events=data['events'] if kind=='FRAME' else [dict(kind=kind,data=data)]
        for event in events:
            k=event['kind'];v=event['data'];token=v.get('token')
            if k=='BOOK' and token in pair:
                source=v['sourceMs'];old=books.get(token)
                if source<0 or source>at or at-source>cfg['maxBookAgeMs'] or old and source<old['sourceMs']:
                    books.pop(token,None);continue
                b={**v,**{side:sorted([dict(price=D(str(l['price'])),size=D(str(l['size']))) for l in v[side]],
                    key=lambda l:l['price'],reverse=side=='bids') for side in ['bids','asks']}}
                books[token]=b
                if seeded and b['bids'] and b['asks']:
                    mid=(b['bids'][0]['price']+b['asks'][0]['price'])/2
                    if token in mids:
                        delta=abs(mid-mids[token]);vols[token]=(vols[token]*D('.9')+delta*D('.1')).quantize(D('1e-18'),rounding=ROUND_HALF_EVEN)
                    mids[token]=mid
            elif seeded and k in ('GAP','FEED_ERROR'):
                affected=set(v.get('tokens',[]))|({token} if token else set())
                if not affected or affected&set(pair):raise ValueError('Scoped GAP before fixed conditional-fill horizon')
            elif seeded and k in ('TICK_SIZE','RESOLUTION'):
                if token in pair or v.get('condition_id')==market['condition']:raise ValueError('Unmodelled terminal/tick change')
            elif seeded and k not in ('BOOK','TRADE','TICK','GAP','FEED_ERROR'):
                raise ValueError('Unmodelled metadata/input needs explicit parsing')
        if seq==243583:
            if at!=anchor['at']:raise ValueError('Changed source anchor time')
            for token,key,volkey in [(pair[0],'firstBook','firstObservedVolatility'),(pair[1],'secondBook','secondObservedVolatility')]:
                b=books[token];w=anchor[key]
                if b['sourceMs']!=w['sourceMs'] or any(b[side][:3]!=w[side] for side in ['bids','asks']):raise ValueError('Anchor source books differ')
                mids[token]=(b['bids'][0]['price']+b['asks'][0]['price'])/2;vols[token]=anchor[volkey]
            seeded=True;continue
        if not seeded or at<next_at or kind=='FRAME' and not events:continue
        next_at=at+cfg['decisionMillis']
        if any(t not in books or not books[t]['bids'] or not books[t]['asks'] or at-books[t]['sourceMs']>2000 for t in pair):
            raise ValueError('Unmodelled missing/stale/empty decision book')
        if at-observed>cfg['metadataMaxAgeMs']:raise ValueError('Metadata stale before fixed horizon')
        a,b=[books[t] for t in pair];vol=max(vols.values())
        check=policy(a,b,vol,at,market,cfg,prices,quantity,anchor['at'])
        check.update(originalSequence=seq,firstBook=a,secondBook=b)
        if seq in original:
            w=original[seq]
            if (at!=w['at'] or next_at!=w['nextDecisionMs'] or vols[pair[0]]!=w['firstObservedVolatility']
                    or vols[pair[1]]!=w['secondObservedVolatility'] or D(check['requiredEdge'])!=w['requiredEdge']):
                raise ValueError('Reconstructed callback/volatility differs from original witness')
            validated.append(seq)
        checks.append(check)
        if check['reason']!='RESTING':break
    if not seeded or not checks or not validated:raise ValueError('No source-bound original scheduled checks')
    return dict(scope='CONDITIONAL_UNFILLED_PAIR_RESTING_CHECKS_NOT_ACCOUNT',state=state,seedWitness=anchor,
        checks=checks,matchedOriginalWitnessSequences=validated,config=cfg,fixedHorizonMs=horizon,
        counterpartExecutionOmitted=True,candidateAccountSimulated=False,actualBotFillsCreated=0,
        netPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    frozen=json.loads(Path('research/phase6/queue-aware-resting-freeze.json').read_text())
    for path,sha in frozen['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Frozen input changed '+path)
    c,m,r=load();e=timeline(c,m,r);out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    for name,v in [('context.json.gz',c),('bindings.json',m),('evidence.json',e)]:
        raw=(json.dumps(v,default=str,separators=(',',':'))+'\n').encode()
        (out/name).write_bytes(gzip.compress(raw,mtime=0) if name.endswith('.gz') else raw)
    print(json.dumps({k:v for k,v in e.items() if k not in ('checks','seedWitness','state')},default=str))


if __name__=='__main__':main()
