"""CS-MINT-LAB0: opt-in, fixed-lifecycle allocation calibration, NOT trading/PnL.

Receipts are offline environment labels. No account, strategy, SDK or runtime
imports and no network. Partial coverage cannot qualify PAPER profitability.
"""
import argparse
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
import json
import hashlib
from pathlib import Path
from research.phase6.order_window import read_evidence
from research.phase6.receipt_audit import EXCHANGES

D = lambda value: Decimal(str(value))
UNIT = Decimal(1000000)


@dataclass
class Order:
    id: str
    token: str
    buy: bool
    price: Decimal
    remaining: Decimal
    ahead: Decimal
    activation: int
    terminal: int
    submitted: int = 0


def validated_portions(result, pair):
    """Require conserved actual group shares AND collateral before any allocation."""
    sample = result['sample']; groups = defaultdict(list)
    if sample['asset_id'] not in pair or sample['side'] != 'BUY':
        raise ValueError('Lab supports fixed binary BUY-taker calibration only')
    for row in result['matches']:
        groups[(row['exchange'],row['ordersMatchedLogIndex'],row['taker']['orderHash'])].append(row)
    matched = []
    for rows in groups.values():
        taker = rows[0]['taker']
        if (taker['token'] == sample['asset_id'] and taker['side'] == sample['side']
                and D(taker['takingRaw'])/UNIT == D(sample['size'])):
            matched.append(rows)
    if len(matched) != 1: raise ValueError('Ambiguous or absent public aggregate identity')
    rows = matched[0]; taker = rows[0]['taker']; portions = []; identities = set()
    total_shares = total_collateral = 0
    for row in rows:
        maker = row['maker']; exchange = row['exchange']
        if exchange not in EXCHANGES or row['taker'] != taker:
            raise ValueError('Untrusted or inconsistent settlement group')
        if any(type(maker[k]) is not int or maker[k] <= 0 for k in ('makingRaw','takingRaw')):
            raise ValueError('Invalid maker integer amounts')
        if row['matchType'] == 'MINT':
            if maker['side'] != 'BUY' or {maker['token'],taker['token']} != set(pair):
                raise ValueError('Invalid binary MINT identity')
            shares, collateral = maker['takingRaw'], maker['makingRaw']
            taker_cost = shares-collateral
        elif row['matchType'] == 'DIRECT':
            if maker['side'] != 'SELL' or maker['token'] != taker['token']:
                raise ValueError('Invalid direct identity')
            shares, collateral = maker['makingRaw'], maker['takingRaw']
            taker_cost = collateral
        else: raise ValueError('Unsupported settlement route')
        if not 0 < collateral < shares: raise ValueError('Invalid maker price')
        identity = (exchange,result['transactionHash'],row['ordersMatchedLogIndex'],maker['logIndex'])
        if identity in identities: raise ValueError('Duplicate maker portion in group')
        identities.add(identity); total_shares += shares; total_collateral += taker_cost
        portions.append(dict(identity=identity,token=maker['token'],buy=maker['side']=='BUY',
            price=D(collateral)/D(shares),quantity=D(shares)/UNIT,route=row['matchType']))
    if (total_shares != taker['takingRaw'] or total_collateral != taker['makingRaw']):
        raise ValueError('Settlement shares/collateral do not conserve')
    return portions


class Allocator:
    """Allocation kernel with explicit measured queue prefixes, no cancellation credit.

    Prefixes at a price include prior own orders, as in the baseline matcher.
    This lab deliberately does not reconstruct unobserved queue events or a
    strategy's changed decisions after a counterfactual allocation.
    """
    def __init__(self, orders, *, enabled=False):
        self.enabled = enabled
        self.orders = [Order(**vars(order)) for order in orders]  # never mutate baseline inputs
        self.seen = set(); self.allocations = []; self.audit = [];self.now=-1
        if len({o.id for o in orders}) != len(orders): raise ValueError('Duplicate virtual order ID')
        for order in orders:
            if (not 0 < order.price < 1 or order.ahead < 0 or order.remaining <= 0
                    or not 0<=order.submitted<=order.activation or order.terminal <= order.activation):
                raise ValueError('Invalid measured order lifecycle/queue')

    def invalidate(self, tokens, at):
        if at<self.now:raise ValueError('Lab receive clock regressed')
        self.now=at
        for order in self.orders:
            if order.token in tokens and order.submitted<=at<order.terminal:
                order.terminal=at

    def advance(self, at, books):
        if at<self.now:raise ValueError('Lab receive clock regressed')
        self.now=at
        for order in self.orders:
            if order.activation<=at<order.terminal:
                book=books.get(order.token)
                if not book or not 0<=at-book['sourceMs']<=2000:
                    order.terminal=at

    def accept(self, portions, *, at, source, books, pair, legacy_aggregate_used=False):
        if legacy_aggregate_used: raise ValueError('Cannot combine aggregate and component liquidity')
        if not self.enabled: return []
        if len({p['identity'] for p in portions}) != len(portions):
            raise ValueError('Duplicate portion batch')
        if any(p['quantity']<=0 or not 0<p['price']<1 or p['token'] not in pair for p in portions):
            raise ValueError('Invalid portion batch')
        self.advance(at,books)
        emitted = []
        fresh = all(token in books and books[token]['bids'] and books[token]['asks']
                    and 0 <= at-books[token]['sourceMs'] <= 2000 for token in pair)
        causal = fresh and 0 <= at-source <= 2000 and all(source>=books[t]['sourceMs'] for t in pair)
        for portion in portions:
            identity = portion['identity']
            if identity in self.seen:
                self.audit.append(dict(identity=list(identity),reason='DUPLICATE_COMPONENT',allocated='0'))
                continue
            # A discarded pre-activation/stale/gap event cannot be replayed later as new volume.
            self.seen.add(identity)
            remaining = portion['quantity']; absorbed = D(0); used = D(0)
            if causal:
                eligible = [o for o in self.orders if o.remaining>0 and o.token==portion['token']
                    and o.buy==portion['buy'] and o.activation < source <= at < o.terminal
                    and (o.price>=portion['price'] if o.buy else o.price<=portion['price'])]
                levels = defaultdict(list)
                for order in eligible: levels[order.price].append(order)
                for price in sorted(levels,reverse=portion['buy']):
                    if remaining<=0: break
                    orders = sorted(levels[price],key=lambda o:(o.activation,self.orders.index(o)))
                    # Known own-order prefix is never silently reduced if lifecycle diverged.
                    prefix = D(0)
                    for order in orders:
                        order.ahead=max(order.ahead,prefix)
                        prefix=order.ahead+order.remaining
                    incoming=remaining; level_used=D(0); extent=max(o.ahead+o.remaining for o in orders)
                    for order in orders:
                        quantity=min(max(incoming-order.ahead,D(0)),order.remaining)
                        order.ahead=max(order.ahead-incoming,D(0))
                        if quantity:
                            order.remaining-=quantity;level_used+=quantity
                            allocation=dict(orderId=order.id,token=order.token,buy=order.buy,
                                price=str(order.price),quantity=str(quantity),at=at,sourceMs=source,
                                portionIdentity=list(identity),route=portion['route'],
                                counterfactualNotActualBotFill=True)
                            emitted.append(allocation)
                    consumed=min(incoming,extent)
                    if level_used>consumed:raise AssertionError('Virtual volume conservation failed')
                    absorbed+=consumed-level_used;used+=level_used;remaining-=consumed
            if used+absorbed+remaining != portion['quantity']:
                raise AssertionError('Component volume conservation failed')
            self.audit.append(dict(identity=list(identity),reason='PROCESSED' if causal else 'NONCAUSAL_OR_BOOK_UNAVAILABLE',
                venueQuantity=str(portion['quantity']),allocated=str(used),queueAbsorbed=str(absorbed),
                unused=str(remaining),accountMutated=False))
        self.allocations.extend(emitted)
        return emitted


def trade_matches_sample(data, result):
    raw = data.get('tradeId','')
    if not raw.startswith('{'): return False
    recorded = json.loads(raw); sample = result['sample']
    return (recorded.get('transaction_hash')==result['transactionHash']
        and data['token']==sample['asset_id']==recorded.get('asset_id')
        and data['side']==sample['side']==recorded.get('side')
        and D(data['price'])==D(sample['price'])==D(recorded['price'])
        and D(data['size'])==D(sample['size'])==D(recorded['size'])
        and data['sourceMs']==int(sample['timestamp'])==int(recorded['timestamp']))


def run(evidence, receipts, audit, *, enabled=False):
    cancels={r['data']['id']:r['at'] for r in audit['events'] if r['kind']=='CANCEL_REQUEST'}
    bindings=[]; outputs=[]; all_matched=set(); all_seen=set()
    labels=[r for r in receipts['results'] if r['sample'].get('logicalTapeSha256')==evidence['logicalTapeSha256']]
    submitted={r['data']['id']:D(r['data']['quantity']) for r in audit['events'] if r['kind']=='ORDER'}
    for window in evidence['windows']:
        spec=window['spec'];pair=set(spec['tokens']);orders=[]
        for row in spec['orders']:
            if row['activatedMs'] is None:continue
            if submitted.get(row['id']) != D(row['remainingShares']):
                raise ValueError('Fixed-lifecycle lab requires measured unfilled baseline orders')
            terminal=min(row['terminalMs'],cancels.get(row['id'],row['terminalMs'])+250)
            orders.append(Order(row['id'],row['token'],row['buy'],D(row['price']),D(row['remainingShares']),
                                D(row['initialQueueAhead']),row['activatedMs'],terminal,row['submittedMs']))
        allocator=Allocator(orders,enabled=enabled);allocator.seen=all_seen; books={}
        for row in window['rows']:
            at=row['arrivalMs']
            events=(row['data']['events'] if row['kind']=='RESEARCH_FRAME' else
                    [dict(kind=row['kind'].removeprefix('RESEARCH_'),data=row['data'])]
                    if row['kind'].startswith('RESEARCH_') else [])
            for position,event in enumerate(events):
                kind=event['kind'];data=event['data'];index=event.get('originalEventIndex',position)
                allocator.advance(at,books)
                if kind in ('GAP','FEED_ERROR'):
                    allocator.invalidate(pair,at);books.clear()
                elif kind=='BOOK' and data['token'] in pair:
                    prior=books.get(data['token']);source=data['sourceMs']
                    if not 0<=at-source<=2000 or prior and source<prior['sourceMs']:
                        allocator.invalidate({data['token']},at);books.pop(data['token'],None)
                    else:books[data['token']]=data
                elif kind=='TRADE':
                    candidates=[r for r in labels if trade_matches_sample(data,r)]
                    if len(candidates)>1:raise ValueError('Ambiguous receipt binding')
                    if not candidates:continue
                    result=candidates[0];tx=result['transactionHash']
                    if tx in all_matched:raise ValueError('Duplicate recorded binding; no remapping after outcome')
                    all_matched.add(tx);parts=validated_portions(result,pair)
                    bindings.append(dict(transactionHash=tx,seq=row['seq'],eventIndex=index,at=at,
                        sourceMs=data['sourceMs'],publicTradeIdSha256=hashlib.sha256(data['tradeId'].encode()).hexdigest()))
                    allocator.accept(parts,at=at,source=data['sourceMs'],books=books,pair=pair)
        outputs.append(dict(orderIds=spec['orderIds'],conditionalAllocations=allocator.allocations,
                            componentAudit=allocator.audit))
    return dict(experiment='CS-MINT-LAB0',enabled=enabled,scope='FIXED_BASELINE_LIFECYCLE_COMPONENT_CALIBRATION_NOT_CLOSED_LOOP',
        logicalTapeSha256=evidence['logicalTapeSha256'],bindings=bindings,windows=outputs,
        receiptSamplesMatchingTape=len(labels),boundReceiptSamples=len(bindings),
        conditionalAllocatedShares=str(sum(D(a['quantity']) for w in outputs for a in w['conditionalAllocations'])),
        baselineMeasuredFillsForTheseOrders=0,baselineWasNotRecomputedByThisLab=True,
        labelCoverageIsPartial=True,futureReceiptLabelsAreEnvironmentOnly=True,
        queueSeedsAreMeasuredBaselineDiagnosticsNotProjectedDepth=True,
        changedStrategyDecisionsAfterAllocationNotSimulated=True,
        matchingAssumptions=dict(activationMs=250,cancelMs=250,maxBookAgeMs=2000,queueMultiplier='2'),
        hiddenLiquidityAndCrossPriceQueueUncertainty=True,accountMutated=False,
        executionCostsNotEvaluated=True,riskPolicyNotResimulated=True,
        notClosedLoopCandidateComparison=True,
        netPnlAfterCosts=None,feesOrRiskChanged=False,actualBotFillsAsserted=False,
        independentPaperQualificationAllowed=False,decision='NO_GO',liveAllowed=False)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--enabled',action='store_true')
    parser.add_argument('--output',required=True);args=parser.parse_args()
    folder=Path('research/experiments/order-window-20261018')
    result=run(read_evidence(folder/'evidence.json.gz.b64'),
        json.loads(Path('research/experiments/candidate-receipt-audit-20261018/offline-volume-labels.json').read_text()),
        json.loads((folder/'baseline-order-audit.json').read_text()),enabled=args.enabled)
    with Path(args.output).open('x') as target:target.write(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
