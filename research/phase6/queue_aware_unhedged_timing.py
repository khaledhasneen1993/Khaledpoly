"""Conditional no-further-fill wait/cancel timing, NOT a strategy/account replay."""
import argparse
from decimal import Decimal as D,ROUND_DOWN,ROUND_HALF_EVEN
import gzip
import hashlib
import json
from pathlib import Path
from research.phase6.entry_witness_result import load as witness_archive
from research.phase6.queue_aware_pair_prefix import prepare
from research.phase6.queue_aware_pair_prefix_result import saved as verified_prefix
from research.phase6.dq3_bottleneck_receipts import traffic


def wait_ms(remaining_ms,unhedged_ms,volatility):
    if unhedged_ms<=0 or volatility<0:raise ValueError('Invalid original wait inputs')
    budget=max(0,min(5000,unhedged_ms//2,remaining_ms//4))
    return int((D(budget)/(1+volatility*100)).to_integral_value(rounding=ROUND_DOWN))


def timeline(context,manifest,seed):
    state=manifest['state'];market=seed['seedWitness']['market'];anchor=seed['seedWitness'];cfg=seed['config']
    fill=manifest['fixedHorizonMs'];pair=[market['first'],market['second']];books={};mids={};vols={}
    seeded=False;next_at=anchor['nextDecisionMs'];checks=[];matched=[];requested=None;ack=None
    witnesses={w['originalSequence']:w for w in json.loads(witness_archive()['report.json'],parse_float=D)['entryDecisionWitnesses']}
    for rec in context['records']:
        row=rec['input'];seq=row['seq'];at=row['arrivalMs'];kind=row['kind'][9:];data=row['data']
        events=data['events'] if kind=='FRAME' else [dict(kind=kind,data=data)]
        for ix,event in enumerate(events):
            k=event['kind'];v=event['data'];token=v.get('token')
            # GAP returns before normal engine advance; it must never be counted as a due cancel ACK.
            if requested and ack is None and at>=requested['at']+cfg['cancelMs'] and k in ('BOOK','TRADE','TICK'):
                ack=dict(originalSequence=seq,eventIndex=ix,at=at,kind=k)
                break
            if k=='BOOK' and token in pair:
                source=v['sourceMs'];old=books.get(token)
                if source<0 or source>at or at-source>cfg['maxBookAgeMs'] or old and source<old['sourceMs']:
                    books.pop(token,None);continue
                b={**v,**{side:sorted([dict(price=D(str(l['price'])),size=D(str(l['size']))) for l in v[side]],
                    key=lambda l:l['price'],reverse=side=='bids') for side in ['bids','asks']}}
                books[token]=b
                if seeded and b['bids'] and b['asks']:
                    mid=(b['bids'][0]['price']+b['asks'][0]['price'])/2
                    vols[token]=(vols[token]*D('.9')+abs(mid-mids[token])*D('.1')).quantize(D('1e-18'),rounding=ROUND_HALF_EVEN)
                    mids[token]=mid
            elif seeded and k in ('GAP','FEED_ERROR'):
                affected=set(v.get('tokens',[]))|({token} if token else set())
                if not affected or affected&set(pair):raise ValueError('Scoped GAP before conditional original wait/cancel acknowledgement')
            elif seeded and k not in ('BOOK','TRADE','TICK','GAP','FEED_ERROR'):
                raise ValueError('Unmodelled metadata/tick/resolution event')
        if ack:break
        if seq==243583:
            if at!=anchor['at']:raise ValueError('Changed original seed arrival')
            for token,key,vkey in [(pair[0],'firstBook','firstObservedVolatility'),(pair[1],'secondBook','secondObservedVolatility')]:
                b=books[token];w=anchor[key]
                if b['sourceMs']!=w['sourceMs'] or any(b[s][:3]!=w[s] for s in ['bids','asks']):raise ValueError('Changed original seed books')
                mids[token]=(b['bids'][0]['price']+b['asks'][0]['price'])/2;vols[token]=anchor[vkey]
            seeded=True;continue
        if not seeded or at<next_at or kind=='FRAME' and not events:continue
        next_at=at+cfg['decisionMillis']
        if any(t not in books or not books[t]['bids'] or not books[t]['asks'] or not 0<=at-books[t]['sourceMs']<=cfg['maxBookAgeMs'] for t in pair):
            raise ValueError('Conditional callback has missing/stale/empty original book')
        if at-market['observedMs']>cfg['metadataMaxAgeMs']:raise ValueError('Metadata stale in conditional callback')
        if seq in witnesses:
            w=witnesses[seq]
            if at!=w['at'] or next_at!=w['nextDecisionMs'] or vols[pair[0]]!=w['firstObservedVolatility'] or vols[pair[1]]!=w['secondObservedVolatility']:
                raise ValueError('Original witness callback/EWMA mismatch')
            matched.append(seq)
        if at<=fill or requested:continue
        vol=max(vols.values());age=at-fill;remaining=market['endMs']-at;wait=wait_ms(remaining,cfg['unhedgedMs'],vol)
        overdue=age>=cfg['unhedgedMs'] or D(state['targetQuote']['quantity'])>=D(cfg['maxUnhedged'])
        check=dict(originalSequence=seq,at=at,ageMs=age,remainingMs=remaining,volatility=str(vol),waitMs=wait,
            overdue=overdue,reason='WAIT_SECOND_LEG' if age<wait and not overdue else 'CANCEL_BEFORE_EXIT')
        checks.append(check)
        if check['reason']=='CANCEL_BEFORE_EXIT':requested=check
    if requested is None or ack is None:raise ValueError('No conditional cancellation within complete retained source window')
    if not fill<requested['at']<ack['at']<state['terminalMs']:raise ValueError('Wrong conditional cancellation chronology')
    # Quote-independent original census, bounded only by frozen causal cancellation acknowledgement.
    source=next(s for s in traffic()['states'] if s['selection']['originalSequence']==243583)
    observations=[o for o in source['observations'] if o['targetToken']==state['quotes'][1]['token'] and fill<o['arrivalMs']<=ack['at']]
    return dict(scope='CONDITIONAL_NO_FURTHER_ALLOCATIONS_WAIT_CANCEL_NOT_ACCOUNT',state=state,config=cfg,
        firstModelAllocationMs=fill,checks=checks,matchedOriginalWitnessSequences=matched,
        conditionalCancelRequest=requested,conditionalCancelDueMs=requested['at']+cfg['cancelMs'],
        expectedFirstDueEngineEvent=ack,postFillCounterpartSourceObservations=observations,
        furtherCounterpartAllocationsSuppressed=True,accountRiskAndOtherMarketsOmitted=True,
        hedgeExitResolutionOmitted=True,actualBotFillsCreated=0,candidateAccountSimulated=False,netPnlRecomputed=False,
        independentPaperQualificationAllowed=False,liveAllowed=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    f=json.loads(Path('research/phase6/queue-aware-unhedged-timing-freeze.json').read_text())
    for path,sha in f['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Frozen input changed '+path)
    verified_prefix();context,manifest,seed=prepare();e=timeline(context,manifest,seed);out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    for name,obj in [('context.json.gz',context),('evidence.json',e)]:
        raw=(json.dumps(obj,default=str,separators=(',',':'))+'\n').encode()
        (out/name).write_bytes(gzip.compress(raw,mtime=0) if name.endswith('.gz') else raw)
    print(json.dumps(dict(scope=e['scope'],checks=len(e['checks']),request=e['conditionalCancelRequest'],
        due=e['conditionalCancelDueMs'],ack=e['expectedFirstDueEngineEvent'],boundedUnknownObservations=len(e['postFillCounterpartSourceObservations']))))


if __name__=='__main__':main()
