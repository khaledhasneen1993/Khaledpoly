"""Independent both-order prefix activation/queue allocation reproduction, not PnL."""
from decimal import Decimal as D,localcontext,ROUND_CEILING
import gzip
import hashlib
import json
from research.phase6.queue_aware_causal import QROOT
from research.phase6.queue_aware_pair_prefix import prepare
from research.phase6.settlement_matching_lab import Allocator,Order

ROOT=QROOT/'pair-prefix-result'


def verify(report,artifact):
    context,manifest,evidence=prepare()
    for name,obj in [('context.json.gz',context),('bindings.json',manifest),('evidence.json',evidence)]:
        raw=(json.dumps(obj,default=str,separators=(',',':'))+'\n').encode()
        if name.endswith('.gz'):raw=gzip.compress(raw,mtime=0)
        m=artifact['members'][name]
        if len(raw)!=m['bytes'] or hashlib.sha256(raw).hexdigest()!=m['sha256']:raise ValueError('Original input bytes differ '+name)
    if (report['scope']!='BOTH_ACTUAL_ORDER_PREFIX_MODEL_NOT_FULL_STRATEGY_ACCOUNT'
            or report['counterpartExecutionOmitted'] or not report['hedgeExitAndResolutionOmitted']
            or report['actualBotFillsCreated']!=0 or report['candidateAccountSimulated'] or report['netPnlRecomputed']
            or report['independentPaperQualificationAllowed'] or report['liveAllowed']):raise ValueError('Wrong bounded pair prefix scope')
    state=manifest['state'];horizon=manifest['fixedHorizonMs'];pair=set(manifest['pair'])
    if report['originalSequence']!=243583 or report['fixedHorizonMs']!=horizon or report['completeOriginalBindingsConsumed']!=40:
        raise ValueError('Wrong original prefix/count/horizon')
    expected=[dict(seq=c['originalSequence'],at=c['at'],bothActiveEqualRemaining=True,reason=c['reason']) for c in evidence['checks']]
    if report['prefixRejectionReason'] is not None or report['restingChecks']!=expected:raise ValueError('Changed original resting callback result')
    diagnostics=report['diagnostics']
    if len(diagnostics)!=2:raise ValueError('Both actual order diagnostics required')
    orders=[]
    for i,(q,diag) in enumerate(zip(state['quotes'],diagnostics)):
        if (diag['id']!=f'qw0-pair-{i}' or diag['token']!=q['token'] or diag['price']!=D(q['price']) or not diag['buy']
                or diag['submittedMs']!=state['submitMs'] or diag['activationDueMs']!=state['activationDueMs']):raise ValueError('Changed original order')
        orders.append(Order(diag['id'],q['token'],True,D(q['price']),D(q['quantity']),diag['initialQueueAhead'],
            diag['activatedMs'],state['terminalMs'],state['submitMs']))
    allocator=Allocator(orders,enabled=True);labels={(b['seq'],b['eventIndex']):b for b in manifest['bindings']}
    books={};activated=set();seen=set();audits=[];last=-1
    for rec in context['records']:
        row=rec['input'];at=row['arrivalMs'];seq=row['seq']
        if at>horizon:break
        last=seq;events=row['data']['events'] if row['kind']=='RESEARCH_FRAME' else [dict(kind=row['kind'][9:],data=row['data'])]
        for ix,event in enumerate(events):
            kind=event['kind'];data=event['data']
            if kind not in ('BOOK','TRADE','TICK','GAP','FEED_ERROR'):continue
            for order in orders:
                if order.id in activated or at<order.activation or kind in ('GAP','FEED_ERROR'):continue
                b=books.get(order.token)
                if at!=order.activation or not b or not 0<=at-b['sourceMs']<=2000:raise ValueError('Unproven actual pre-event activation')
                size=next((D(str(l['size'])) for l in b['bids'] if D(str(l['price']))==order.price),D(0))
                if size*2!=order.ahead or order.price>=min(D(str(l['price'])) for l in b['asks']):
                    raise ValueError('Wrong actual activation queue/post-only price')
                activated.add(order.id)
            if kind in ('GAP','FEED_ERROR'):
                affected=set(data.get('tokens',[]))|({data['token']} if 'token' in data else set())
                if not affected or affected&pair:allocator.invalidate(pair,at);books.clear()
                continue
            allocator.advance(at,books)
            if kind=='BOOK' and data['token'] in pair:
                token=data['token'];source=data['sourceMs'];old=books.get(token)
                if source<0 or source>at or at-source>2000 or old and source<old['sourceMs']:
                    books.pop(token,None);allocator.invalidate({token},at)
                else:books[token]=data
            elif kind=='TRADE' and (seq,ix) in labels:
                b=labels[(seq,ix)];seen.add((seq,ix));parts=[]
                for p in b['parts']:
                    with localcontext() as ctx:
                        ctx.prec=80;price=(D(p['collateralRaw'])/D(p['sharesRaw'])).quantize(D('1e-28'),rounding=ROUND_CEILING)
                    parts.append(dict(identity=(p['identity'],),token=p['token'],buy=p['buy'],price=price,
                        quantity=D(p['sharesRaw'])/1000000,route='ACTUAL_CONSERVED_COMPONENT'))
                before=len(allocator.allocations);allocator.accept(parts,at=at,source=data['sourceMs'],books=books,pair=pair)
                audits.append(dict(seq=seq,eventIndex=ix,at=at,sourceMs=data['sourceMs'],allocations=allocator.allocations[before:]))
    def normalized(f):
        return dict(id=f.get('id',f.get('orderId')),token=f['token'],buy=f['buy'],price=D(f['price']),size=D(f.get('size',f.get('quantity'))),at=f['at'])
    if len(activated)!=2 or len(seen)!=40 or last!=report['lastOriginalSequence']:raise ValueError('Incomplete both-order original prefix')
    if [normalized(f) for f in allocator.allocations]!=[normalized(f) for f in report['modelAllocations']]:raise ValueError('Actual paired component allocations differ')
    actual=report['receiptAudit']
    if len(actual)!=40:raise ValueError('Incomplete actual receipt allocation audit')
    for a,b in zip(audits,actual):
        if ({k:v for k,v in a.items() if k!='allocations'}!={k:v for k,v in b.items() if k!='allocations'}
                or [normalized(f) for f in a['allocations']]!=[normalized(f) for f in b['allocations']]):raise ValueError('Per-source allocation audit differs')
    totals={k:sum(D(a[v]) for a in allocator.audit) for k,v in [('venueQuantity','venueQuantity'),('queueAbsorbed','queueAbsorbed'),('allocatedQuantity','allocated'),('unusedQuantity','unused')]}
    engine=report['actualComponentAllocationDiagnostics']
    if len(allocator.audit)!=engine['uniqueMakerComponents'] or any(totals[k]!=D(engine[k]) for k in totals):raise ValueError('Paired component conservation differs')
    for order,diag in zip(allocator.orders,diagnostics):
        if order.remaining!=diag['remainingShares'] or order.ahead!=diag['remainingQueueAhead']:raise ValueError('Remaining actual pair inventory/queue differs')
    return dict(scope='REPRODUCED_BOTH_ORDER_PREFIX_NOT_ACCOUNT',originalSequence=243583,completeOriginalBindings=40,
        actualRestingChecks=len(expected),actualActivationQueues=[str(d['initialQueueAhead']) for d in diagnostics],
        allocatedSharesByToken={o.token:str(D(next(q['quantity'] for q in state['quotes'] if q['token']==o.token))-o.remaining) for o in allocator.orders},
        uniqueActualComponents=len(allocator.audit),hedgeExitResolutionNotSimulated=True,candidateAccountSimulated=False,
        actualBotFillsCreated=0,netPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False,
        decision='REQUIRE_UNHEDGED_HEDGE_CANCEL_EXIT_AND_RESOLUTION_ACCOUNT_EVIDENCE')


def saved():
    artifact=json.loads((ROOT/'artifact-manifest.json').read_text());raw=(ROOT/'report.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=artifact['members']['report.json']['sha256']:raise ValueError('Changed retained actual-engine report')
    return verify(json.loads(raw,parse_float=D),artifact)


if __name__=='__main__':print(json.dumps(saved(),indent=2))
