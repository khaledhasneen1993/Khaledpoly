"""Default-off offline probe: quarantine split depth groups, never publish/fill orders."""
from copy import deepcopy
from decimal import Decimal as D
import re


class Probe:
    def __init__(self, token, snapshot, at, enabled=False, ttl_ms=250):
        self.token=token;self.enabled=enabled;self.ttl=ttl_ms;self.pending=None;self.closed=False
        self.source=int(snapshot['timestamp']);self.at=at
        if (snapshot['event_type']!='book' or snapshot['asset_id']!=token
                or not 0<=at-self.source<=2000 or ttl_ms<=0):
            raise ValueError('Fresh complete snapshot required')
        self.book={side:{D(str(x['price'])):D(str(x['size'])) for x in snapshot[side]
            if D(str(x['size']))>0} for side in ('bids','asks')}
        if not self.coherent(self.book):raise ValueError('Invalid starting snapshot')

    @staticmethod
    def coherent(book):
        return bool(book['bids'] and book['asks'] and max(book['bids'])<min(book['asks']))

    @staticmethod
    def top(book):return max(book['bids']),min(book['asks'])

    def fail(self, reason):
        self.closed=True;self.pending=None
        return dict(status='WAIT_FULL_SNAPSHOT',reason=reason,bookPublished=False)

    def accept(self, message, at):
        if self.closed:return self.fail('ALREADY_INVALIDATED')
        source=int(message['timestamp'])
        if at<self.at or source<self.source or not 0<=at-source<=2000:
            return self.fail('CLOCK_OR_SOURCE')
        self.at=at
        rows=[x for x in message.get('price_changes',[]) if x['asset_id']==self.token]
        if not rows:return dict(status='UNRELATED',bookPublished=False)
        if message.get('event_type')!='price_change':return self.fail('NOT_DELTA')
        hashes={x.get('hash') for x in rows}
        hints={(x.get('best_bid'),x.get('best_ask')) for x in rows}
        if (len(hashes)!=1 or not re.fullmatch('[0-9a-f]{40}',next(iter(hashes)) or '')
                or len(hints)!=1 or None in next(iter(hints))):
            return self.fail('MISSING_OR_AMBIGUOUS_GROUP')
        signature=(source,next(iter(hashes)),next(iter(hints)))
        if self.pending:
            if signature!=self.pending['signature']:return self.fail('GROUP_CHANGED')
            if at-self.pending['at']>self.ttl:return self.fail('QUARANTINE_EXPIRED')
            book=deepcopy(self.pending['book'])
        else:book=deepcopy(self.book)
        for row in rows:
            price=D(str(row['price']));size=D(str(row['size']))
            if row['side'] not in ('BUY','SELL') or not 0<=price<=1 or not size.is_finite() or size<0:
                return self.fail('INVALID_LEVEL')
            side='bids' if row['side']=='BUY' else 'asks'
            if size==0:book[side].pop(price,None)
            else:book[side][price]=size
        hint=tuple(D(x) for x in signature[2])
        ready=self.coherent(book) and self.top(book)==hint
        if self.pending:
            if not ready:
                self.pending['book']=book
                return dict(status='QUARANTINED',bookPublished=False)
            delay=at-self.pending['at'];self.closed=True;self.recovered_book=book
            return dict(status='RECOVERY_CANDIDATE',delayMs=delay,bestBid=str(hint[0]),bestAsk=str(hint[1]),
                hash=signature[1],sourceMs=source,bookPublished=False,
                hashCryptographicallyVerified=False,priorGapRetracted=False)
        self.source=source
        if ready:
            self.book=book
            return dict(status='PREFIX_CONSISTENT',bookPublished=False)
        if not self.enabled:return self.fail('DEPTH_GROUP_INCOMPLETE')
        self.pending=dict(signature=signature,book=book,at=at)
        return dict(status='QUARANTINED',bookPublished=False)
