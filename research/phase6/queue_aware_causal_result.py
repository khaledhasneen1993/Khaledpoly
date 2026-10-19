"""Independently reproduce conditional source/queue allocation, never account profit."""
import base64
from decimal import Decimal as D,localcontext,ROUND_CEILING
import gzip
import hashlib
import io
import json
from pathlib import Path
import zipfile
from research.phase6.queue_aware_causal import QROOT,selection_and_bindings,validate_terminal
from research.phase6.settlement_matching_lab import Allocator,Order

SHA='49ad5c66c74761d1a4be29645b77cccde784cc5d55ab08ab478ba5bf20351eea'


def load():
    raw=base64.b64decode((QROOT/'causal-result/artifact.zip.b64').read_bytes())
    if hashlib.sha256(raw).hexdigest()!=SHA:raise ValueError('Changed actual-matcher QW0 artifact')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if {i.filename:i.file_size for i in z.infolist()}!={'bindings.json':72782,'context.json.gz':2207309,'report.json':21103}:
            raise ValueError('Wrong actual-matcher artifact members')
        with gzip.GzipFile(fileobj=io.BytesIO(z.read('context.json.gz'))) as inp:body=inp.read(128000001)
        if len(body)>128000000:raise ValueError('Oversized bounded original context')
        return json.loads(body),json.loads(z.read('bindings.json')),json.loads(z.read('report.json'),parse_float=D)


def verify(context,manifest,report):
    spec,original=selection_and_bindings()
    if manifest!=original or context['spec']!=spec or context['logicalTapeSha256']!=spec['logicalTapeSha256']:
        raise ValueError('Changed source/actual receipts/frozen QW0 quote')
    validate_terminal(context,spec)
    if (report['scope']!='OPTIMISTIC_ISOLATED_QW0_TARGET_ONLY_NOT_STRATEGY_OR_ACCOUNT'
            or report['state']!=manifest['state'] or not report['restingRiskCancellationOmitted']
            or not report['counterpartExecutionOmitted'] or report['actualBotFillsCreated']!=0
            or report['netPnlRecomputed'] or report['candidateAccountSimulated']
            or report['independentPaperQualificationAllowed'] or report['liveAllowed']):
        raise ValueError('Wrong conditional upper-bound scope')
    if report['consumedOriginalBindings']!=39 or len(report['diagnostics'])!=1:raise ValueError('Incomplete label/order diagnostics')
    d=report['diagnostics'][0];s=manifest['state'];q=s['targetQuote'];pair=set(manifest['pair'])
    if d['token']!=q['token'] or d['price']!=D(q['price']) or d['submittedMs']!=s['submitMs']:
        raise ValueError('Changed hypothetical isolated order')
    order=Order('qw0-target-only',q['token'],True,D(q['price']),D(q['quantity']),d['initialQueueAhead'],
        d['activatedMs'],s['terminalMs'],s['submitMs']);allocator=Allocator([order],enabled=True)
    labels={(b['seq'],b['eventIndex']):b for b in manifest['bindings']}
    audit={(b['seq'],b['eventIndex']):b for b in report['bindingAudit']}
    books={};consumed=set();activation_proven=False;last_seq=-1;last_at=-1
    for rec in context['records']:
        row=rec['input'];at=row['arrivalMs'];seq=row['seq'];kind=row['kind'][9:]
        if seq<=last_seq or at<last_at:raise ValueError('Changed original input chronology')
        last_seq=seq;last_at=at
        if kind=='FRAME':
            if rec['raw']['data']['frameId']!=row['data']['frameId']:raise ValueError('Unbound original RAW frame')
            events=row['data']['events']
        else:events=[dict(kind=kind,data=row['data'])]
        for ix,event in enumerate(events):
            k=event['kind'];data=event['data']
            if k not in ('BOOK','TRADE','TICK','GAP','FEED_ERROR'):continue
            if not activation_proven and at>=d['activatedMs'] and k not in ('GAP','FEED_ERROR'):
                pre=books.get(q['token'])
                if at!=d['activatedMs'] or not pre or not 0<=at-pre['sourceMs']<=2000:
                    raise ValueError('No exact pre-event activation book')
                size=next((D(str(l['size'])) for l in pre['bids'] if D(str(l['price']))==D(q['price'])),D(0))
                if size*2!=d['initialQueueAhead'] or D(q['price'])>=min(D(str(l['price'])) for l in pre['asks']):
                    raise ValueError('Wrong pre-event initial queue/post-only price')
                activation_proven=True
            if k in ('GAP','FEED_ERROR'):
                affected=set(data.get('tokens',[]))|({data['token']} if 'token' in data else set())
                if not affected or affected&pair:allocator.invalidate(pair,at);books.clear()
                continue
            allocator.advance(at,books)
            if k=='BOOK' and data['token'] in pair:
                token=data['token'];source=data['sourceMs'];prior=books.get(token)
                if source<0 or source>at or at-source>2000 or prior and source<prior['sourceMs']:
                    books.pop(token,None);allocator.invalidate({token},at)
                else:books[token]=data
            elif k=='TRADE' and (seq,ix) in labels:
                key=(seq,ix);b=labels[key];a=audit[key]
                if key in consumed or json.loads(data['tradeId'])!=b['sample'] or at!=b['at'] or data['sourceMs']!=b['sourceMs']:
                    raise ValueError('Actual receipt does not bind to original trade')
                consumed.add(key);sources={t:books[t]['sourceMs'] if t in books else -1 for t in pair}
                causal=0<=at-data['sourceMs']<=2000 and all(t in books and books[t]['bids'] and books[t]['asks']
                    and at-books[t]['sourceMs']<=2000 and data['sourceMs']>=books[t]['sourceMs'] for t in pair)
                if sources!=a['pairBookSourcesBeforePrint'] or bool(causal)!=a['sourceNotOlderThanBothFreshBooks']:
                    raise ValueError('Changed current pair-book source eligibility')
                portions=[]
                for p in b['parts']:
                    with localcontext() as ctx:
                        ctx.prec=80;price=(D(p['collateralRaw'])/D(p['sharesRaw'])).quantize(D('1e-28'),rounding=ROUND_CEILING)
                    portions.append(dict(identity=(p['identity'],),token=p['token'],buy=p['buy'],price=price,
                        quantity=D(p['sharesRaw'])/1000000,route='ACTUAL_CONSERVED_COMPONENT'))
                allocator.accept(portions,at=at,source=data['sourceMs'],books=books,pair=pair)
    if len(consumed)!=39 or not activation_proven:raise ValueError('Incomplete labels/activation proof')
    expected=[(a['orderId'],a['token'],a['buy'],D(a['price']),D(a['quantity']),a['at']) for a in allocator.allocations]
    actual=[(a['id'],a['token'],a['buy'],D(a['price']),D(a['size']),a['at']) for a in report['conditionalModelFills']]
    if expected!=actual:raise ValueError('Conditional actual-component allocations differ')
    totals={key:sum(D(a[field]) for a in allocator.audit) for key,field in
        [('venueQuantity','venueQuantity'),('allocatedQuantity','allocated'),('queueAbsorbed','queueAbsorbed'),('unusedQuantity','unused')]}
    engine=report['actualComponentAllocationDiagnostics']
    if any(totals[k]!=D(engine[k]) for k in totals) or len(allocator.audit)!=engine['uniqueMakerComponents']:
        raise ValueError('Independent actual component/queue conservation differs')
    if d['remainingShares']!=allocator.orders[0].remaining or d['remainingQueueAhead']!=allocator.orders[0].ahead:
        raise ValueError('Wrong final conditional quantity/queue')
    return dict(scope='REPRODUCED_OPTIMISTIC_QW0_TARGET_ONLY_CONDITIONAL_ALLOCATION_NOT_PROFIT',
        originalSequence=243583,originalLabelsConsumed=39,uniqueActualComponents=len(allocator.audit),
        initialQueueAhead=str(d['initialQueueAhead']),conditionalAllocatedShares=str(totals['allocatedQuantity']),
        queueAbsorbed=str(totals['queueAbsorbed']),conditionalFillTimes=[a['at'] for a in allocator.allocations],
        independentPythonActualComponentAllocationReproduced=True,restingRiskCancellationOmitted=True,
        counterpartExecutionOmitted=True,actualBotFillsCreated=0,netPnlRecomputed=False,
        candidateAccountSimulated=False,independentPaperQualificationAllowed=False,liveAllowed=False,
        decision='REQUIRE_ACTUAL_RESTING_LIFETIME_AND_COUNTERPART_BEFORE_ACCOUNT_OR_INDEPENDENT_PAPER')


if __name__=='__main__':print(json.dumps(verify(*load()),indent=2))
