"""Counterfactual depth-consumption cost. Never creates a fill or rewrites observed prices."""
from decimal import Decimal as D
from research.phase3.polybot_sdk.model import validate,number


def scenario(snapshot,token,buy,size,*,at_ms=None):
    snap=validate(snapshot,at_ms); q=number(size)
    if type(buy) is not bool or not 0<q<=D('1e12'): raise ValueError('Invalid impact side/quantity')
    book=snap['books'].get(token)
    if not book or not book['bids'] or not book['asks'] or book['depthTruncated']:
        raise ValueError('Complete two-sided fresh depth required')
    if int(snap['generatedMs'])-int(book['sourceMs'])>=int(snap['maxBookAgeMs']): raise ValueError('Stale impact depth')
    side=book['asks'] if buy else book['bids']; left=q; cost=D(0); post=None
    for level in side:
        price,available=number(level['price']),number(level['size']); used=min(left,available)
        cost+=used*price;left-=used
        if used<available: post=price;break
    reference=number(side[0]['price']); filled=q-left
    vwap=cost/filled if filled else None
    other=number(book['bids' if buy else 'asks'][0]['price'])
    return {'scope':'UNVERIFIED_DEPTH_IMPACT_SCENARIO','requestedShares':str(q),'depthAvailableShares':str(filled),
        'complete':left==0,'assumedVwap':str(vwap) if vwap is not None else None,
        'assumedSlippagePerShare':str((vwap-reference)*(1 if buy else -1)) if vwap is not None else None,
        'counterfactualPostMid':str((post+other)/2) if post is not None else None,
        'feesIncluded':False,'fillsCreated':0,'observedBookModified':False,'liveAllowed':False,'decision':'NO_GO'}
