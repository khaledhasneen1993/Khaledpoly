"""Preregistered QW0, pure selected-development-state pricing; never executions."""
from decimal import Decimal as D,ROUND_CEILING
from itertools import product
from research.phase6.depth_quote_lab import propose as dq3


def propose(w,config):
    # A stronger edge floor has a subset of DQ3's lawful price pairs. Its existing
    # pure admission check enforces original size/freshness/flatness/budgets.
    if dq3(w,config) is None:return None
    books=[w['firstBook'],w['secondBook']];m=w['market'];q=D(str(w['quantity']))
    depth=min(D(str(b['bids'][0]['size'])) for b in books)
    thin=min((D(1)/max(depth,D(1))).quantize(D('.00000001'),rounding=ROUND_CEILING),D('.02'))
    reserve=D('.02')-thin;required=D(str(w['requiredEdge']))+reserve
    tick=D(str(m['tick']));multiplier=D(str(config['queueMultiplier']))
    if multiplier<1:raise ValueError('Do not relax the queue model')
    levels=[]
    for book in books:
        levels.append([(D(str(l['price'])),i,D(str(l['size']))) for i,l in enumerate(book['bids'][:3])
            if tick<=D(str(l['price']))<=1-tick and D(str(l['price']))%tick==0
            and D(str(l['price']))<D(str(book['asks'][0]['price'])) and D(str(l['size']))>=10*q])
    candidates=[]
    for a,b in product(*levels):
        net=(1-a[0]-b[0])*q-D(str(config['mergeCost']));cost=(a[0]+b[0])*q
        loss=q*max(a[0],b[0])+D(str(config['redemptionCost']))
        if (net<required*q or loss>D(str(w['exitLossAvailable'])) or cost>D(str(w['availableCash']))
                or D(str(w['gross']))+cost>D(str(config['portfolioBudget']))):continue
        candidates.append(dict(firstBid=a[0],secondBid=b[0],quantity=q,requiredEdge=required,
            originalRequiredEdge=D(str(w['requiredEdge'])),thinPremiumReserve=reserve,
            firstLevelIndex=a[1],secondLevelIndex=b[1],firstDisplayedSize=a[2],secondDisplayedSize=b[2],
            firstDisplayedQueueProxy=a[2]*multiplier,secondDisplayedQueueProxy=b[2]*multiplier,
            netEdgeTotal=net,worstUnpairedLoss=loss,queuePriorityOrFillProven=False))
    if not candidates:return None
    return min(candidates,key=lambda r:(max(r['firstDisplayedQueueProxy'],r['secondDisplayedQueueProxy']),
        r['firstDisplayedQueueProxy']+r['secondDisplayedQueueProxy'],-r['firstBid']-r['secondBid'],
        max(r['firstLevelIndex'],r['secondLevelIndex']),r['firstLevelIndex']+r['secondLevelIndex'],-r['firstBid']))
