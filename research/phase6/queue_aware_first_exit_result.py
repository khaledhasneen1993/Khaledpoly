"""Independent conditional recovery decisions, ALL queues, component conservation and FOK."""
from decimal import Decimal as D,ROUND_HALF_UP,ROUND_CEILING,ROUND_FLOOR,localcontext
import gzip
import hashlib
import json
from research.phase6.queue_aware_causal import QROOT
from research.phase6.queue_aware_recovery_exit import prepare
from research.phase6.settlement_matching_lab import Allocator,Order

ROOT=QROOT/'first-exit-result'


def fee(q,p,market,cfg):
    return (q*D(str(market['feeRate']))*D(cfg['feeMultiplier'])*(p*(1-p))**market['feeExponent']).quantize(D('.00001'),rounding=ROUND_HALF_UP)


def verify(report,artifact):
    seed=prepare();raw=(json.dumps(seed,indent=2)+'\n').encode()
    if hashlib.sha256(raw).hexdigest()!=artifact['members']['input.json']['sha256'] or len(raw)!=artifact['members']['input.json']['bytes']:raise ValueError('Changed frozen first exit input')
    if (report['scope']!=seed['scope'] or report['stopReason']!='FIRST_NEW_ATOMIC_TAKER_FOK_STOP_BEFORE_MERGE_OR_STRATEGY'
            or not report['stoppedOnNewAllocation'] or not report['postAllocationInventoryAndMergeNotProcessed']
            or not report['accountRiskAssumedAvailable'] or not report['otherMarketsAndFullAccountOmitted']
            or report['actualBotFillsCreated']!=0 or report['candidateAccountSimulated'] or report['netPnlRecomputed']
            or report['completeInputGroups']!=451 or report['conditionalInitialQuantity']!=5
            or report['independentPaperQualificationAllowed'] or report['liveAllowed']):raise ValueError('Wrong conditional first exit scope')
    cfg=seed['config'];market=seed['market'];lead=market['first'];other=market['second'];pair={lead,other}
    quantity=D(seed['initialQuantity']);basis=D(seed['initialBasisPerShare']);books={};orders=[];decisions=[];pending=None;next_at=seed['nextDecisionMs'];seen=[];outcome=None
    labels={(b['seq'],b['eventIndex']):b for b in seed['bindings']};history=[]
    def fresh(b,at):return b and b['bids'] and b['asks'] and 0<=at-b['sourceMs']<=2000
    def best(b,side,high):return (max if high else min)(D(str(l['price'])) for l in b[side])
    def live():return [o for o in orders if o['terminalMs'] is None]
    def terminate(o,at,reason):o.update(terminalMs=at,terminalReason=reason)
    path=QROOT/'post-gap-result/context.records.jsonl.gz'
    with gzip.open(path,'rt') as source:
        for line in source:
            row=json.loads(line)['input'];at=row['arrivalMs'];seq=row['seq'];kind=row['kind'][9:]
            if at>seed['horizonMs']:break
            events=row['data']['events'] if kind=='FRAME' else [dict(kind=kind,data=row['data'])]
            for ix,event in enumerate(events):
                k=event['kind'];v=event['data'];token=v.get('token');binding=labels.get((seq,ix))
                if k=='META':
                    if v['condition']==market['condition']:
                        if any(v[key]!=market[key] for key in ['first','second','startMs','endMs','negativeRisk']) or v['observedMs']>at:raise ValueError('Changed original market identity')
                        market=v
                        if not market['accepting']:
                            for o in live():terminate(o,at,'MARKET_CLOSED_OR_RESOLVED')
                            books.clear();pending=None
                    continue
                if k in ('GAP','FEED_ERROR'):
                    affected=set(v.get('tokens',[]))|({token} if token else set())
                    if not affected or affected&pair:
                        for o in live():terminate(o,at,'DATA_GAP:'+v.get('reason','unknown'))
                        books.clear();pending=None
                    history.append((at,k,v,binding));continue
                if k not in ('BOOK','TRADE','TICK'):raise ValueError('Unmodelled original source event')
                for o in live():
                    b=books.get(o['token'])
                    if o['activatedMs'] is not None and (not b or at-b['sourceMs']>2000):terminate(o,at,'STALE_BOOK')
                for o in live():
                    b=books.get(o['token'])
                    if o['cancelDue'] is not None and at>=o['cancelDue']:terminate(o,at,o['cancelReason']);continue
                    if o['activatedMs'] is None and at>=o['activationDueMs']:
                        if not fresh(b,at):terminate(o,at,'ACTIVATION_BOOK_UNAVAILABLE');continue
                        if o['price']<=best(b,'bids',True):terminate(o,at,'POST_ONLY_WOULD_CROSS');continue
                        o['activatedMs']=at;o['initialQueueAhead']=sum(D(str(l['size'])) for l in b['asks'] if D(str(l['price']))==o['price'])*2
                if k=='BOOK' and token in pair:
                    old=books.get(token);ms=v['sourceMs']
                    if not 0<=at-ms<=2000 or old and ms<old['sourceMs']:
                        books.pop(token,None)
                        for o in live():
                            if o['token']==token:terminate(o,at,'INVALID_OR_REGRESSED_BOOK')
                    else:books[token]=v
                if binding is not None:seen.append((seq,ix))
                elif k=='TRADE' and at>seed['startMs'] and token in pair:raise ValueError('Unknown original pair receipt')
                history.append((at,k,v,binding))
            if at<seed['startMs'] or kind=='FRAME' and not events:continue
            if pending is not None and at>=pending['due']:
                p=pending;pending=None;b=books.get(p['token'])
                if not fresh(b,at) or at>=market['endMs'] or at-market['observedMs']>cfg['metadataMaxAgeMs']:decisions.append(dict(at=at,seq=seq,reason='TAKER_DATA_REJECT'))
                elif not live() and quantity>=D(str(market['minSize'])):
                    left=quantity;notional=cost=D(0);legs=[]
                    for l in sorted(b['asks' if p['buy'] else 'bids'],key=lambda x:D(str(x['price'])),reverse=not p['buy']):
                        px=D(str(l['price']))
                        if px>p['limit'] if p['buy'] else px<p['limit']:break
                        q=min(left,D(str(l['size'])));f=fee(q,px,market,cfg);notional+=q*px;cost+=f
                        if q>0:legs.append(dict(size=q,price=px,fee=f))
                        left-=q
                        if left==0:break
                    if left>0:decisions.append(dict(at=at,seq=seq,reason='TAKER_FOK_REJECT'))
                    else:
                        pnl=quantity-basis*quantity-notional-cost-D(cfg['mergeCost']) if p['buy'] else notional-cost-basis*quantity
                        if p['purpose']=='POSITIVE_EDGE_COMPLETION' and pnl<D(cfg['minimumEdge'])*quantity:decisions.append(dict(at=at,seq=seq,reason='TAKER_NET_EDGE'))
                        elif max(-pnl,D(0))>D(seed['initialUnspentExitLossBudget']):decisions.append(dict(at=at,seq=seq,reason='EXIT_LOSS_CAP'))
                        else:
                            outcome=dict(at=at,seq=seq,token=p['token'],buy=p['buy'],quantity=quantity,purpose=p['purpose'],result=dict(size=quantity,notional=notional,fee=cost,average=(notional/quantity).quantize(D('1e-18')),legs=legs))
                            break
            if at<next_at:continue
            next_at=at+cfg['decisionMillis'];active=live();overdue=at-seed['firstModelAllocationMs']>=cfg['unhedgedMs'] or quantity>=D(cfg['maxUnhedged'])
            unavailable='OUTSIDE_MARKET' if not market['startMs']<=at<market['endMs'] else 'BOOK_UNAVAILABLE' if not all(fresh(books.get(t),at) for t in pair) else 'METADATA_STALE' if at-market['observedMs']>cfg['metadataMaxAgeMs'] else 'MARKET_UNAVAILABLE' if not market['accepting'] else None
            if unavailable or active:
                if unavailable is None and not overdue:decisions.append(dict(at=at,seq=seq,reason='RESTING_REDUCTION'));continue
                for o in active:
                    if o['cancelDue'] is None:o.update(cancelDue=at+250,cancelReason=unavailable or 'CANCEL_BEFORE_RISK_EXIT')
                decisions.append(dict(at=at,seq=seq,reason=unavailable or 'CANCEL_BEFORE_EXIT'));continue
            if pending is not None:continue
            a=books[lead];b=books[other];bid=best(a,'bids',True);ask=best(a,'asks',False);opposite=best(b,'asks',False);tick=D(str(market['tick']))
            complete=1-basis-opposite-fee(D(1),opposite,market,cfg)-(D(cfg['mergeCost'])/quantity).quantize(D('1e-18'),rounding=ROUND_CEILING)
            sell=bid-basis-fee(D(1),bid,market,cfg);action='COMPLETE' if complete>=D(cfg['minimumEdge']) and complete>=sell else ('RISK_COMPLETE' if complete>=sell else 'RISK_SELL') if overdue else 'WAIT'
            choice=dict(action=action,completeValue=complete,sellValue=sell)
            if not overdue and action!='COMPLETE':
                price=max(ask-tick,bid+tick)
                if price>=1 or quantity<D(str(market['minSize'])) or max(basis-price,D(0))*quantity>D(seed['initialUnspentExitLossBudget']):decisions.append(dict(at=at,seq=seq,reason='REDUCTION_CONSTRAINT'));continue
                oid='qw0-recovery-'+str(len(orders)+1)
                orders.append(dict(id=oid,token=lead,buy=False,price=price,submittedMs=at,activationDueMs=at+250,activatedMs=None,initialQueueAhead=None,terminalMs=None,terminalReason=None,cancelDue=None,cancelReason=None))
                decisions.append(dict(at=at,seq=seq,reason='MAKER_REDUCTION',id=oid,price=price,choice=choice))
            else:
                buy=action.endswith('COMPLETE');limit=min(opposite+tick*3,1-tick) if buy else max(bid-tick*3,tick)
                pending=dict(token=other if buy else lead,buy=buy,due=at+250,limit=limit,purpose='RISK_REDUCTION' if overdue else 'POSITIVE_EDGE_COMPLETION')
                decisions.append(dict(at=at,seq=seq,reason='TAKER_PENDING',pending=pending,choice=choice))
    if outcome is None or report['modelExitAllocations']!=[outcome] or report['stopAt']!=outcome['at'] or report['stopSequence']!=outcome['seq'] or report['stopEventIndex']!=-1:raise ValueError('Independent FOK allocation/stop/fees differ')
    if decisions!=report['decisions'] or len(orders)!=len(report['diagnostics']):raise ValueError('Independent strategy callback/decision trajectory differs')
    for o,native in zip(orders,report['diagnostics']):
        if any(native[k]!=o[k] for k in o if k not in ('cancelDue','cancelReason')):raise ValueError('Independent activation/queue/cancel differs '+o['id'])
    calibrated=[Order(o['id'],o['token'],False,o['price'],quantity,o['initialQueueAhead'],o['activatedMs'],o['terminalMs'],o['submittedMs']) for o in orders if o['activatedMs'] is not None]
    allocator=Allocator(calibrated,enabled=True);books={}
    for at,k,v,binding in history:
        token=v.get('token')
        if k in ('GAP','FEED_ERROR'):
            affected=set(v.get('tokens',[]))|({token} if token else set())
            if not affected or affected&pair:allocator.invalidate(pair,at);books.clear()
            continue
        allocator.advance(at,books)
        if k=='BOOK' and token in pair:
            old=books.get(token);ms=v['sourceMs']
            if not 0<=at-ms<=2000 or old and ms<old['sourceMs']:allocator.invalidate({token},at);books.pop(token,None)
            else:books[token]=v
        elif binding is not None:
            parts=[]
            for p in binding['parts']:
                with localcontext() as ctx:
                    ctx.prec=80;price=(D(p['collateralRaw'])/D(p['sharesRaw'])).quantize(D('1e-28'),rounding=ROUND_CEILING if p['buy'] else ROUND_FLOOR)
                parts.append(dict(identity=(p['identity'],),token=p['token'],buy=p['buy'],price=price,quantity=D(p['sharesRaw'])/1000000,route='ACTUAL_CONSERVED_COMPONENT'))
            allocator.accept(parts,at=at,source=v['sourceMs'],books=books,pair=pair)
    totals={k:sum(D(a[v]) for a in allocator.audit) for k,v in [('venueQuantity','venueQuantity'),('allocatedQuantity','allocated'),('queueAbsorbed','queueAbsorbed'),('unusedQuantity','unused')]}
    if allocator.allocations or len(seen)!=report['consumedOriginalGroups'] or len(allocator.audit)!=report['componentAllocationDiagnostics']['uniqueMakerComponents'] or any(totals[k]!=report['componentAllocationDiagnostics'][k] for k in totals):raise ValueError('Independent maker allocation/conservation differs')
    by_id={o.id:o for o in allocator.orders}
    for n in report['diagnostics']:
        if n['id'] in by_id and (by_id[n['id']].ahead!=n['remainingQueueAhead'] or by_id[n['id']].remaining!=n['remainingShares']):raise ValueError('Remaining queue/inventory differs')
    gross=outcome['result']['notional']-basis*quantity
    return dict(scope='INDEPENDENT_CONDITIONAL_FIRST_EXIT_NOT_FULL_ACCOUNT',makerOrders=len(orders),makerFills=0,
        consumedOriginalGroups=len(seen),uniqueActualComponents=len(allocator.audit),exitAt=outcome['at'],exitOriginalSequence=outcome['seq'],
        conditionalExitShares=str(quantity),conditionalGrossBeforeExitFee=str(gross),conditionalExitFee=str(outcome['result']['fee']),
        conditionalRoundTripNetAfterCosts=str(gross-outcome['result']['fee']),conditionalRemainingShares='0',
        fullAccountOtherMarketsAndFurtherStrategyOmitted=True,candidateAccountSimulated=False,independentPaperQualificationAllowed=False,liveAllowed=False)


def saved():
    a=json.loads((ROOT/'artifact-manifest.json').read_text());raw=(ROOT/'report.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=a['members']['report.json']['sha256']:raise ValueError('Changed native first exit report')
    return verify(json.loads(raw,parse_float=D),a)


if __name__=='__main__':print(json.dumps(saved(),indent=2))
