"""Verify source snapshots behind immutable actual-engine activation diagnostics.

No candidate account/lifetime simulation; compare seeds to complete optimistic
actual-price volume bounds. This cannot establish a fill or global rejection.
"""
import base64
from decimal import Decimal as D
import gzip
import hashlib
import io
import json
from pathlib import Path
import zipfile
from research.phase6.dq3_bottleneck_receipts import ROOT

SHA='bb9a933dd12035eb1c46a08f60662e3c19150ad5ad137e54dc0df93f6124d1ae'


def load():
    raw=base64.b64decode((ROOT/'activation-result/artifact.zip.b64').read_bytes())
    if hashlib.sha256(raw).hexdigest()!=SHA:raise ValueError('Changed activation artifact')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if {i.filename:i.file_size for i in z.infolist()}!={'activation.json':5391,'context.json.gz':1028320}:
            raise ValueError('Wrong activation artifact members')
        with gzip.GzipFile(fileobj=io.BytesIO(z.read('context.json.gz'))) as gz:b=gz.read(64000001)
        if len(b)>64000000:raise ValueError('Oversized context')
        return json.loads(b),json.loads(z.read('activation.json'),parse_float=D)


def verify(context,result):
    f=json.loads(Path('research/phase6/dq3-activation-freeze.json').read_text())
    if (context['spec']!=f['spec'] or context['logicalTapeSha256']!=f['spec']['logicalTapeSha256']
            or context['sourceRows']!=6163831 or not context['fullNormalizedDepthUnmodified']
            or not context['originalRawFramesUnmodified'] or context['fillsInferred'] or context['pnlInferred']):
        raise ValueError('Wrong full-depth original source scope')
    if (result['scope']!='ISOLATED_NO_CANCEL_ACTIVATION_SEED_ONLY_NOT_ACTUAL_ACCOUNT'
            or not result['allTradeVolumeSuppressed'] or result['fillsCreated']!=0
            or result['netPnlRecomputed'] or result['actualRestingCancellationSimulated']
            or result['independentPaperQualificationAllowed'] or result['liveAllowed']):
        raise ValueError('Wrong no-fill isolated-probe scope')
    if [r['state'] for r in result['results']]!=f['spec']['states']:raise ValueError('Wrong selected starts')
    bounds=json.loads((ROOT/'overlap-result/coverage.json').read_text())['legs'];out=[]
    for r in result['results']:
        state=r['state'];d=r['diagnostic'];quote=state['targetQuote'];token=quote['token']
        pair={q['token'] for q in state['quotes']};book=None;book_anchor=None;last_seq=-1;last_at=-1;first_due=None;found=False;submit_seen=False
        for record in context['records']:
            row=record['input'];seq=row['seq'];at=row['arrivalMs']
            if seq<=last_seq or at<last_at:raise ValueError('Changed original input chronology')
            last_seq=seq;last_at=at
            if seq==state['originalSequence']:
                if at!=state['submitMs']:raise ValueError('Changed submit anchor')
                submit_seen=True
            if submit_seen and at>=state['activationDueMs'] and first_due is None:first_due=seq
            kind=row['kind'][9:];events=row['data']['events'] if kind=='FRAME' else [dict(kind=kind,data=row['data'])]
            if kind=='FRAME' and record['raw']['data']['frameId']!=row['data']['frameId']:
                raise ValueError('Unbound original RAW input')
            for ix,e in enumerate(events):
                if seq==r['activationOutcomeSequence'] and ix==r['activationOutcomeEventIndex']:
                    outcome=row;found=True;break  # PRE-event book only, never incoming BOOK.
                ed=e['data'];k=e['kind']
                if k in ('GAP','FEED_ERROR'):
                    affected=set(ed.get('tokens',[]))|({ed['token']} if 'token' in ed else set())
                    if not affected or affected&pair:book=None;book_anchor=None
                elif k=='BOOK' and ed['token']==token:
                    source=ed['sourceMs']
                    if source<0 or source>at or at-source>2000 or book is not None and source<book['sourceMs']:
                        book=None;book_anchor=None
                    else:book=ed;book_anchor=dict(originalSequence=seq,eventIndex=ix,receivedMs=at,sourceMs=source)
            if found:break
        if (not found or not submit_seen or not book or not r['sameFirstDueInput'] or r['tickChangeSinceSubmission']
                or first_due!=r['firstInputAtOrAfterDueSequence'] or first_due!=r['activationOutcomeSequence']
                or outcome['arrivalMs']-book['sourceMs']>2000):raise ValueError('Missing/ambiguous causal seed')
        if (d['submittedMs']!=state['submitMs'] or d['activationDueMs']!=state['activationDueMs']
                or d['price']!=D(quote['price']) or d['token']!=token or not d['buy']
                or d['eligiblePrintVolume']!=0 or d['remainingShares']!=D(quote['quantity'])):
            raise ValueError('Changed isolated order/volume scope')
        bound=next(l for l in bounds if l['originalSequence']==state['originalSequence'] and l['quote']['token']==token)
        if not bound['complete'] or bound['quote']!=quote or bound['actualPriceCompatibleSharesRaw']!=state['actualPriceCompatibleUpperBoundSharesRaw']:
            raise ValueError('Incomplete/wrong upper-bound receipt evidence')
        asks=[D(str(l['price'])) for l in book['asks'] if D(str(l['size']))>0]
        bids={D(str(l['price'])):D(str(l['size'])) for l in book['bids'] if D(str(l['size']))>0}
        upper=D(bound['actualPriceCompatibleSharesRaw'])/1000000
        if d['terminalReason']=='POST_ONLY_WOULD_CROSS':
            if d['activatedMs'] is not None or d['initialQueueAhead'] is not None or d['terminalMs']!=outcome['arrivalMs'] or D(quote['price'])<min(asks):
                raise ValueError('Unsupported post-only rejection')
            finding=dict(reason='POST_ONLY_WOULD_CROSS',initialQueueAhead=None)
        else:
            initial=bids.get(D(quote['price']),D(0))*2
            if (d['activatedMs']!=outcome['arrivalMs'] or d['initialQueueAhead']!=initial
                    or d['remainingQueueAhead']!=initial or initial<upper or D(quote['price'])>=min(asks)):
                raise ValueError('Queue insufficient to prove isolated no-fill bound')
            finding=dict(reason='INITIAL_QUEUE_EXCEEDS_COMPLETE_ACTUAL_PRICED_UPPER_BOUND',
                initialQueueAhead=str(initial),minimumQueueNotCleared=str(initial-upper))
        out.append(dict(originalSequence=state['originalSequence'],price=quote['price'],preEventBook=book_anchor,
            outcomeMs=outcome['arrivalMs'],outcomeSequence=r['activationOutcomeSequence'],
            completeActualPricedUpperBoundShares=str(upper),**finding))
    return dict(scope='THREE_ISOLATED_NO_CANCEL_STARTS_REJECTED_NOT_GLOBAL_POLICY_OR_ACCOUNT',results=out,
        actualRestingCancellationSimulated=False,overlappingVolumeMustNotBeSummed=True,fillsCreated=0,
        netPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False,
        decision='REJECT_THESE_THREE_ISOLATED_STARTS_UNCHANGED_QUEUE_AND_POST_ONLY')


if __name__=='__main__':print(json.dumps(verify(*load()),indent=2))
