"""Independent source-time three-order queue/conservation reproduction, NOT PnL."""
from decimal import Decimal as D,localcontext,ROUND_CEILING,ROUND_FLOOR
import gzip
import hashlib
import json
from research.phase6.queue_aware_causal import QROOT
from research.phase6.queue_aware_reduction_context import prepare
from research.phase6.queue_aware_gap_tail_receipts import selection
from research.phase6.settlement_matching_lab import Allocator,Order

ROOT=QROOT/'active-reduction-result'


def verify(report,artifact):
    context,m,e=prepare();s=m['state'];pair=set(m['pair']);gap=m['horizonMs']
    for name,obj in [('context.json.gz',context),('bindings.json',m),('evidence.json',e)]:
        raw=(json.dumps(obj,default=str,separators=(',',':'))+'\n').encode()
        if name.endswith('.gz'):raw=gzip.compress(raw,mtime=0)
        a=artifact['members'][name]
        if len(raw)!=a['bytes'] or hashlib.sha256(raw).hexdigest()!=a['sha256']:raise ValueError('Original bounded input bytes differ '+name)
    if (report['scope']!='BOUNDED_ACTIVE_REDUCTION_UNTIL_FIRST_NEW_FILL_OR_GAP_NOT_ACCOUNT'
            or report['originalSequence']!=243583 or report['completeInputGroups']!=162
            or report['consumedOriginalGroups']!=162 or report['firstScopedGapMs']!=gap
            or not report['firstGapActuallyProcessed'] or report['stoppedOnFirstReductionAllocation']
            or report['postReductionFillStrategyNotProcessed'] or report['stopOriginalSequence']!=-1
            or report['stopEventIndex']!=-1 or report['pendingTakerCanceledByGap']
            or report['componentPriceRounding']!='BUY_UP_SELL_DOWN_28'
            or not report['accountRiskAndOtherMarketsOmitted'] or not report['postGapAndResolutionOmitted']
            or report['actualBotFillsCreated']!=0 or report['candidateAccountSimulated'] or report['netPnlRecomputed']
            or report['independentPaperQualificationAllowed'] or report['liveAllowed']):raise ValueError('Wrong incomplete account scope or bounded outcome')
    timing=e['timing'];ack=timing['expectedFirstDueEngineEvent']['at'];request=timing['conditionalCancelRequest']['at']
    if ack!=1792269759566 or request+250>ack:raise ValueError('Changed original cancellation evidence')
    spec=selection();hedge=report['hedgeDecision'];q=spec['hypotheticalUnchangedHedgeQuote'];hs=spec['hedgeQuoteSource']
    if (hedge['at']!=ack or hedge['originalSequence']!=hs['originalSequence'] or hedge['plannedAction']!='MAKER_REDUCTION'
            or hedge['plannedDueMs']!=ack+250 or D(hedge['price'])!=D(q['price'])
            or hedge['choice']['action']!='WAIT' or D(hedge['choice']['completeValue'])!=D(hs['completeValue'])
            or D(hedge['choice']['sellValue'])!=D(hs['sellValue']) or not hedge['accountRiskAssumedAvailable']):raise ValueError('Changed source/fee-derived original hedge')
    quotes=[dict(**a,buy=True,submitted=s['submitMs'],due=s['activationDueMs'],terminal=gap) for a in s['quotes']]
    quotes[1]['terminal']=ack
    quotes.append(dict(token=q['token'],price=q['price'],quantity=q['quantity'],buy=False,submitted=ack,due=ack+250,terminal=gap))
    ids=['qw0-gap-0','qw0-gap-1','qw0-gap-reduction'];orders=[];books={};activation=[];cancel_ack=None
    # Derive first actual activation and queue from the PRE-event original book,
    # not the report's measured queue or the decision-time book.
    for rec in context['records']:
        row=rec['input'];at=row['arrivalMs']
        events=row['data']['events'] if row['kind']=='RESEARCH_FRAME' else [dict(kind=row['kind'][9:],data=row['data'])]
        for ix,event in enumerate(events):
            k=event['kind'];v=event['data']
            if k not in ('BOOK','TRADE','TICK','GAP','FEED_ERROR'):continue
            if k in ('GAP','FEED_ERROR'):
                affected=set(v.get('tokens',[]))|({v['token']} if 'token' in v else set())
                if not affected or affected&pair:books.clear()
                continue
            if at>=request+250 and cancel_ack is None:cancel_ack=(row['seq'],ix,at)
            for i,z in enumerate(quotes):
                if any(o.id==ids[i] for o in orders) or at<z['due']:continue
                b=books.get(z['token']);price=D(z['price']);side='bids' if z['buy'] else 'asks'
                if not b or not 0<=at-b['sourceMs']<=2000:raise ValueError('Missing pre-event activation depth')
                if price>=min(D(str(l['price'])) for l in b['asks']) if z['buy'] else price<=max(D(str(l['price'])) for l in b['bids']):raise ValueError('Original post-only activation crossed')
                queue=sum(D(str(l['size'])) for l in b[side] if D(str(l['price']))==price)*2
                orders.append(Order(ids[i],z['token'],z['buy'],price,D(z['quantity']),queue,at,z['terminal'],z['submitted']))
                activation.append(dict(id=ids[i],originalSequence=row['seq'],eventIndex=ix,at=at,preEventBookSourceMs=b['sourceMs'],initialQueue=str(queue)))
            if k=='BOOK' and v['token'] in pair:
                old=books.get(v['token']);source=v['sourceMs']
                if not 0<=at-source<=2000 or old and source<old['sourceMs']:books.pop(v['token'],None)
                else:books[v['token']]=v
    expected_ack=timing['expectedFirstDueEngineEvent']
    if cancel_ack!=(expected_ack['originalSequence'],expected_ack['eventIndex'],ack) or len(orders)!=3:raise ValueError('Original activation/cancel clocks differ')
    diagnostics=report['diagnostics']
    if len(diagnostics)!=3:raise ValueError('Require three actual order diagnostics')
    for o,z,d in zip(orders,quotes,diagnostics):
        if (d['id']!=o.id or d['token']!=o.token or d['buy']!=o.buy or D(d['price'])!=o.price
                or d['submittedMs']!=o.submitted or d['activationDueMs']!=z['due'] or d['activatedMs']!=o.activation
                or D(d['initialQueueAhead'])!=o.ahead):raise ValueError('Measured pre-event queue/activation differs')
    allocator=Allocator(orders,enabled=True);labels={(b['seq'],b['eventIndex']):b for b in m['bindings']};seen=set();books={};priced=[]
    for rec in context['records']:
        row=rec['input'];at=row['arrivalMs'];events=row['data']['events'] if row['kind']=='RESEARCH_FRAME' else [dict(kind=row['kind'][9:],data=row['data'])]
        for ix,event in enumerate(events):
            k=event['kind'];v=event['data'];key=(row['seq'],ix)
            if k in ('GAP','FEED_ERROR'):
                affected=set(v.get('tokens',[]))|({v['token']} if 'token' in v else set())
                if not affected or affected&pair:allocator.invalidate(pair,at);books.clear()
                continue
            if k not in ('BOOK','TRADE','TICK'):continue
            allocator.advance(at,books)
            if k=='BOOK' and v['token'] in pair:
                old=books.get(v['token']);source=v['sourceMs']
                if not 0<=at-source<=2000 or old and source<old['sourceMs']:
                    books.pop(v['token'],None);allocator.invalidate({v['token']},at)
                else:books[v['token']]=v
            elif k=='TRADE' and key in labels:
                b=labels[key];seen.add(key);parts=[]
                for p in b['parts']:
                    with localcontext() as ctx:
                        ctx.prec=80;price=(D(p['collateralRaw'])/D(p['sharesRaw'])).quantize(D('1e-28'),rounding=ROUND_CEILING if p['buy'] else ROUND_FLOOR)
                    parts.append(dict(identity=(p['identity'],),token=p['token'],buy=p['buy'],price=price,quantity=D(p['sharesRaw'])/1000000,route='ACTUAL_CONSERVED_COMPONENT'))
                before=len(allocator.audit);allocator.accept(parts,at=at,source=v['sourceMs'],books=books,pair=pair)
                for p,audit in zip(parts,allocator.audit[before:]):
                    if p['token']==q['token'] and not p['buy'] and p['price']>=D(q['price']) and at>ack:
                        priced.append(dict(seq=row['seq'],eventIndex=ix,at=at,sourceMs=v['sourceMs'],quantity=str(p['quantity']),queueAbsorbed=audit['queueAbsorbed'],reason=audit['reason']))
    def normalized(f):return (f.get('id',f.get('orderId')),f['token'],f['buy'],D(f['price']),D(f.get('size',f.get('quantity'))),f['at'])
    if len(seen)!=162 or [normalized(f) for f in allocator.allocations]!=[normalized(f) for f in report['modelAllocations']]:raise ValueError('Independent actual component allocations differ')
    totals={k:sum(D(a[v]) for a in allocator.audit) for k,v in [('venueQuantity','venueQuantity'),('queueAbsorbed','queueAbsorbed'),('allocatedQuantity','allocated'),('unusedQuantity','unused')]}
    native=report['actualComponentAllocationDiagnostics']
    if len(allocator.audit)!=native['uniqueMakerComponents'] or any(totals[k]!=D(native[k]) for k in totals):raise ValueError('Independent component conservation differs')
    for o,d in zip(allocator.orders,diagnostics):
        if o.remaining!=D(d['remainingShares']) or o.ahead!=D(d['remainingQueueAhead']):raise ValueError('Remaining original inventory/queue differs')
    if (diagnostics[1]['terminalMs']!=ack or diagnostics[1]['terminalReason']!='CANCEL_BEFORE_RISK_EXIT'
            or diagnostics[2]['terminalMs']!=gap or diagnostics[2]['terminalReason']!='DATA_GAP:invalid_depth'
            or D(report['remainingUnhedgedShares'])!=allocator.orders[2].remaining):raise ValueError('Wrong cancel/GAP or uncovered inventory')
    return dict(scope='INDEPENDENTLY_REPRODUCED_ACTIVE_REDUCTION_TO_FIRST_GAP_NOT_ACCOUNT',completeOriginalGroups=162,
        activationEvidence=activation,actualPriceCompatibleSellComponents=priced,uniqueActualComponents=len(allocator.audit),
        reductionQueueAbsorbed=str(orders[2].ahead-allocator.orders[2].ahead),remainingReductionQueue=str(allocator.orders[2].ahead),
        remainingUnhedgedShares=str(allocator.orders[2].remaining),conservedTotals={k:str(v) for k,v in totals.items()},
        modelReductionFilledShares=str(D(q['quantity'])-allocator.orders[2].remaining),firstGapMs=gap,
        actualBotFillsCreated=0,candidateAccountSimulated=False,netPnlRecomputed=False,
        independentPaperQualificationAllowed=False,liveAllowed=False,decision='REQUIRE_ORIGINAL_POST_GAP_RECOVERY_AND_FULL_ACCOUNT')


def saved():
    artifact=json.loads((ROOT/'artifact-manifest.json').read_text());raw=(ROOT/'report.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=artifact['members']['report.json']['sha256']:raise ValueError('Changed actual engine reduction report')
    return verify(json.loads(raw,parse_float=D),artifact)


if __name__=='__main__':print(json.dumps(saved(),indent=2))
