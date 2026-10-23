"""DQ3-0: pure DEVELOPMENT quote screen, not wired to execution or service config."""
from decimal import Decimal as D
from itertools import product


def propose(witness,config):
    w=witness;m=w['market'];at=w['at']
    if 'quantity' not in w or 'requiredEdge' not in w:return None
    q=D(str(w['quantity']))
    # Keep ACTUAL original top-depth size and threshold, not a larger size or a
    # lower premium derived from a thicker/deeper level. Nothing is predicted.
    if (w['entryStopped'] or w['ledgerHalted'] or w['resolved'] or w['openOrderIds']
            or D(str(w['imbalance']))!=0 or not m['accepting'] or not m['startMs']<=at<m['endMs']
            or at-m['observedMs']>config['metadataMaxAgeMs'] or q<D(str(m['minSize']))):
        return None
    books=[w['firstBook'],w['secondBook']];tick=D(str(m['tick']))
    if any(not b or not b['bids'] or not b['asks'] or not 0<=at-b['sourceMs']<=config['maxBookAgeMs'] for b in books):
        return None
    cap=D(str(config['orderShares']));depth=min(D(str(b['bids'][0]['size'])) for b in books)
    expected=min(cap,depth*D('.1')).quantize(D('.01'),rounding='ROUND_DOWN')
    if q!=expected:raise ValueError('Do not increase original causal top-depth quantity')
    if any(last is not None and b['sourceMs']<=last for b,last in zip(books,[w['lastFirstTakerSource'],w['lastSecondTakerSource']])):
        return None
    levels=[]
    for book in books:
        eligible=[]
        for index,level in enumerate(book['bids'][:3]):
            p=D(str(level['price']));size=D(str(level['size']))
            if (tick<=p<=1-tick and p%tick==0 and p<D(str(book['asks'][0]['price']))
                    and size>=10*q):
                eligible.append((p,index,size))
        levels.append(eligible)
    required=D(str(w['requiredEdge']));merge=D(str(config['mergeCost']))
    redemption=D(str(config['redemptionCost']));budget=D(str(w['exitLossAvailable']))
    candidates=[]
    for a,b in product(*levels):
        net=(1-a[0]-b[0])*q-merge;cost=(a[0]+b[0])*q
        if (net<required*q or q*max(a[0],b[0])+redemption>budget
                or cost>D(str(w['availableCash'])) or D(str(w['gross']))+cost>D(str(config['portfolioBudget']))):
            continue
        candidates.append(dict(firstBid=a[0],secondBid=b[0],quantity=q,requiredEdge=required,
            firstLevelIndex=a[1],secondLevelIndex=b[1],firstDisplayedSize=a[2],secondDisplayedSize=b[2],
            netEdgeTotal=net,worstUnpairedLoss=q*max(a[0],b[0])+redemption,
            queuePriorityOrFillProven=False))
    if not candidates:return None
    # Fixed deterministic objective: nearest combined bid, then shallower levels,
    # then higher first-token bid. No later prints, fill outcomes or fitted score.
    return min(candidates,key=lambda r:(-r['firstBid']-r['secondBid'],
        max(r['firstLevelIndex'],r['secondLevelIndex']),r['firstLevelIndex']+r['secondLevelIndex'],-r['firstBid']))
