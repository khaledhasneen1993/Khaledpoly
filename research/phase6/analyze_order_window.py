"""Causal book/receipt observations only. No counterfactual execution or PnL."""
import argparse
from decimal import Decimal
import json
from pathlib import Path
from research.phase6.candidate_receipt_audit import label_candidate
from research.phase6.order_window import related, read_evidence


def analyze(evidence, receipts, max_age=2000, audit=None):
    settled = {r['transactionHash']:r['matches'] for r in receipts['results']}
    cancel_requests = {}
    for row in (audit or {}).get('events',[]):
        if row['kind']=='CANCEL_REQUEST':
            cancel_requests.setdefault(row['data']['id'],row['at'])
    windows = []
    for window in evidence['windows']:
        spec = window['spec']; tokens = set(spec['tokens']); books = {}; observations = []; gaps = []
        seen_makers = set(); book_timeline={token:[] for token in tokens}
        for row in window['rows']:
            at = row['arrivalMs']
            if row['kind'] == 'RESEARCH_FRAME':
                events = row['data']['events']
            elif row['kind'].startswith('RESEARCH_'):
                events = [dict(kind=row['kind'].removeprefix('RESEARCH_'),data=row['data'])]
            else: continue
            for index, event in enumerate(events):
                index=event.get('originalEventIndex',index)
                kind = event['kind']; data = event['data']
                if kind in ('GAP','FEED_ERROR') and related('RESEARCH_'+kind,data,tokens,spec['condition']):
                    scope = set(data.get('tokens',[]))
                    if data.get('token'): scope.add(data['token'])
                    # A strategy pair GAP invalidates both pair books.
                    books.clear()
                    for token in tokens: book_timeline[token].append((at,None))
                    gaps.append(dict(seq=row['seq'],at=at,eventIndex=index,reason=data.get('reason',kind),scope=sorted(scope)))
                elif kind == 'BOOK' and data['token'] in tokens:
                    token = data['token']; source = data['sourceMs']; prior = books.get(token)
                    if (not 0 <= at-source <= max_age or prior and source < prior['sourceMs']):
                        books.pop(token,None)
                    else: books[token] = data
                    book_timeline[token].append((at,books.get(token)))
                elif kind == 'TRADE' and data['token'] in tokens:
                    tx = None
                    raw = data.get('tradeId','')
                    if raw.startswith('{'): tx = json.loads(raw).get('transaction_hash')
                    source = data['sourceMs']
                    for order in spec['orders']:
                        if not order['buy'] or order['token'] == data['token'] or data['side'] != 'BUY': continue
                        activation = order.get('activatedMs'); terminal = order.get('terminalMs')
                        active = activation is not None and terminal is not None and activation <= at < terminal
                        if not active: continue
                        snapshot = {}
                        for token in sorted(tokens):
                            book = books.get(token)
                            snapshot[token] = None if book is None else dict(sourceMs=book['sourceMs'],
                                fresh=0 <= at-book['sourceMs'] <= max_age,
                                bestBid=str(max(Decimal(str(x['price'])) for x in book['bids'])) if book['bids'] else None,
                                bestAsk=str(min(Decimal(str(x['price'])) for x in book['asks'])) if book['asks'] else None)
                        ready = all(b and b['fresh'] and b['bestBid'] and b['bestAsk'] for b in snapshot.values())
                        after_books = ready and all(source >= b['sourceMs'] for b in snapshot.values())
                        sample = dict(asset_id=data['token'],side=data['side'],price=str(data['price']),size=str(data['size']),
                                      targetToken=order['token'],targetPrice=str(1-Decimal(str(data['price']))))
                        label = label_candidate(sample,settled[tx]) if tx in settled else None
                        maker_rows = []; groups = label['identityMatchingGroups'] if label else []
                        if label and label['uniqueIdentityConservedGroup']:
                            group = groups[0]
                            for match in settled[tx]:
                                if (match['exchange'] != group['exchange'] or match['ordersMatchedLogIndex'] != group['ordersMatchedLogIndex']
                                        or match['matchType'] != 'MINT' or match['maker']['token'] != order['token']): continue
                                maker = match['maker']; identity = (match['exchange'],tx,match['ordersMatchedLogIndex'],maker['logIndex'])
                                maker_rows.append(dict(identity=list(identity),shares=str(Decimal(maker['takingRaw'])/1000000),
                                    makerPrice=str(Decimal(maker['makingRaw'])/maker['takingRaw']),
                                    botBuyPriceAtLeastMakerPrice=Decimal(str(order['price']))*maker['takingRaw'] >= maker['makingRaw'],
                                    alreadyObserved=identity in seen_makers))
                                seen_makers.add(identity)
                        cancel=cancel_requests.get(order['id'])
                        observations.append(dict(seq=row['seq'],eventIndex=index,at=at,sourceMs=source,
                            transactionHash=tx,reportedToken=data['token'],reportedPrice=str(data['price']),reportedSize=str(data['size']),
                            orderId=order['id'],orderPrice=str(order['price']),activeAtArrival=active,
                            sourceStrictlyAfterObservedActivation=source > activation,
                            tradeSourceFresh=0 <= at-source <= max_age,bothBooksFresh=bool(ready),
                            tradeNotBeforeEitherBook=bool(after_books),booksBeforeTrade=snapshot,
                            receiptAvailable=label is not None,settlementLabel=label,mintMakerPortions=maker_rows,
                            queueAtEventNotProven=True,cancelRequestTimeNotReconstructed=cancel is None,
                            cancelRequestMs=cancel,cancelDueMsFromFrozen250ms=None if cancel is None else cancel+250,
                            observedBeforeCancelRequest=None if cancel is None else at<cancel,
                            observedBeforeCancelDue=None if cancel is None else at<cancel+250))
        quote_context=[]
        for order in spec['orders']:
            reference=next((o for o in observations if o['orderId']==order['id'] and o['mintMakerPortions']
                and o['bothBooksFresh'] and o['tradeNotBeforeEitherBook'] and o['sourceStrictlyAfterObservedActivation']),None)
            if reference is None: continue
            horizons=[]
            for delay in (0,100,250,500,1000,2000):
                deadline=reference['at']+delay; prior=[b for at,b in book_timeline[order['token']] if at<=deadline]
                book=prior[-1] if prior else None
                fresh=bool(book and 0<=deadline-book['sourceMs']<=max_age and book['bids'] and book['asks'])
                bid=max(Decimal(str(x['price'])) for x in book['bids']) if fresh else None
                ask=min(Decimal(str(x['price'])) for x in book['asks']) if fresh else None
                horizons.append(dict(horizonMs=delay,at=deadline,bookFresh=fresh,
                    bid=None if bid is None else str(bid),ask=None if ask is None else str(ask),
                    mid=None if bid is None else str((bid+ask)/2),
                    gapSinceReference=any(reference['at']<g['at']<=deadline for g in gaps),
                    coveredByWindow=deadline<=spec['endMs']))
            quote_context.append(dict(orderId=order['id'],orderPrice=str(order['price']),referenceAt=reference['at'],
                                      referenceIsNotBotFill=True,quoteObservations=horizons))
        windows.append(dict(orderIds=spec['orderIds'],complementTradesDuringRecordedActiveOrders=observations,
                            gapObservations=gaps,uniqueMintMakerIdentities=len(seen_makers),
                            quoteContextNotPnl=quote_context))
    return dict(scope='CAUSAL_ORDER_BOOK_SETTLEMENT_DIAGNOSTIC_NOT_EXECUTION',
        logicalTapeSha256=evidence['logicalTapeSha256'],windows=windows,
        sourceHashVerifiedByExtractor=evidence.get('recordingClosedCleanly') is True,
        fillsInferred=False,pnlInferred=False,decision='NO_GO',liveAllowed=False,
        note='Lifecycle comes from baseline report. A receipt label or price priority never establishes counterfactual queue allocation or a live executable fill.')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--windows',required=True)
    parser.add_argument('--receipts',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--audit')
    args=parser.parse_args()
    result=analyze(read_evidence(args.windows),json.loads(Path(args.receipts).read_text()),
                   audit=json.loads(Path(args.audit).read_text()) if args.audit else None)
    with Path(args.output).open('x') as target:target.write(json.dumps(result,indent=2)+'\n')


if __name__ == '__main__':main()
