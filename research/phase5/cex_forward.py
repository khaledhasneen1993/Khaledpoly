"""Causal non-overlapping CEX spot forward-price diagnostics, NOT fills.

Uses sealed PUBLIC trade print tapes. A future observed spot print is not
a price executable by the Polymarket bot, nor proof of a crypto strategy edge.
"""
import argparse
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from research.phase3.polybot_sdk.model import decode, dumps, integer, number
from research.phase3.polybot_sdk.runtime import private_write
from research.phase5.cex_signals import SignalState, parse_sample

MAX_RECORDS = 100000


def forward_test(rows, horizon_ms=1000, max_label_delay_ms=2000, fee_bps='5',
                 slippage_bps='5', min_labeled=100, lookback=5):
    if (type(horizon_ms) is not int or not 100 <= horizon_ms <= 600000
            or type(max_label_delay_ms) is not int or not 100 <= max_label_delay_ms <= 60000
            or type(min_labeled) is not int or not 1 <= min_labeled <= 100000):
        raise ValueError('Invalid preregistered research timing')
    fee, slip = number(fee_bps), number(slippage_bps)
    if not 0 <= fee <= 10000 or not 0 <= slip <= 10000:
        raise ValueError('Invalid explicit round-trip cost assumptions')
    if not isinstance(rows, list) or len(rows) > MAX_RECORDS:
        raise ValueError('Invalid observation bound')
    states, pending, counters, outcomes, last_now = {}, {}, defaultdict(int), defaultdict(list), -1
    for row in sorted(rows, key=lambda r:(integer(r['polledMs']),r.get('venue',''))):
        now=integer(row['polledMs'])
        if now < last_now:
            raise ValueError('Invalid global observation clock')
        last_now=now
        key=(row['venue'],row['symbol'])
        if key not in states:
            states[key]=SignalState(lookback=lookback,max_age_ms=max_label_delay_ms)
        state=states[key]
        fresh=[]
        if row.get('status')=='SAMPLED_PUBLIC_TRADES':
            _,_,fresh=parse_sample(row)
        for strategy in ('momentum','flow'):
            ticket=pending.get((key,strategy))
            if ticket is None:
                continue
            target=ticket['atMs']+horizon_ms
            # Any source outage invalidates the active forecast immediately,
            # even if it precedes the label horizon; no silent gap bridging.
            if row.get('status')!='SAMPLED_PUBLIC_TRADES':
                counters[(key,strategy,'censored_source_gap')]+=1
                pending.pop((key,strategy))
                continue
            if now>=target:
                eligible=[x for x in fresh
                          if target<=x['sourceMs']<=target+max_label_delay_ms
                          and x['receivedMs']<=target+max_label_delay_ms]
                if eligible:
                    price=min(eligible,key=lambda x:(x['receivedMs'],x['sourceMs'],x['id']))['price']
                    gross=(price/ticket['price']-1)*10000*ticket['direction']
                    # Pure arithmetic at observed public print prices.
                    net=gross-Decimal(2)*(fee+slip)
                    outcomes[(key,strategy)].append(net)
                    counters[(key,strategy,'labeled')]+=1
                    pending.pop((key,strategy))
                elif now>target+max_label_delay_ms:
                    counters[(key,strategy,'censored_missing_forward_price')]+=1
                    pending.pop((key,strategy))
        # Each source-specific rejected sample resets causal signal history.
        status=state.event(row)
        if status.get('status')!='RESEARCH_SIGNALS_UNQUALIFIED':
            counters[(key,'all',status['status'])]+=1
            continue
        for strategy,label in (('momentum',status['momentumDirection']),
                               ('flow',status['aggressiveFlow'])):
            sign = 1 if label in ('UP','BUY') else -1 if label in ('DOWN','SELL') else 0
            if sign==0:
                counters[(key,strategy,'neutral_or_missing')]+=1
                continue
            # One open forecast per strategy and venue keeps outcomes
            # independent of overlapping speculative backtests.
            if (key,strategy) in pending:
                counters[(key,strategy,'overlapping_skipped')]+=1
                continue
            pending[(key,strategy)]={'atMs':now,'price':state.rows[-1]['price'],
                                    'direction':sign}
            counters[(key,strategy,'created')]+=1
    for (key,strategy) in pending:
        counters[(key,strategy,'censored_at_end')]+=1
    report={}
    for (venue,symbol),state in sorted(states.items()):
        for strategy in ('momentum','flow'):
            values=outcomes[((venue,symbol),strategy)]
            created=counters[((venue,symbol),strategy,'created')]
            label_count=len(values)
            report[venue+'/'+symbol+'/'+strategy]={
                'signals':created,'labeledNonoverlapping':label_count,
                'censoredGap':counters[((venue,symbol),strategy,'censored_source_gap')],
                'censoredPrice':counters[((venue,symbol),strategy,'censored_missing_forward_price')],
                'censoredAtEnd':counters[((venue,symbol),strategy,'censored_at_end')],
                'overlapsSkipped':counters[((venue,symbol),strategy,'overlapping_skipped')],
                'minimumHeldoutLabelsMet':label_count>=min_labeled,
                'meanAssumedNetBasisPoints':str(sum(values,Decimal(0))/label_count) if values else None,
                'theoreticalPositiveOutcomeFraction':str(sum(v>0 for v in values)/label_count) if values else None,
                'orderFillsObserved':False,'qualified':False}
    return {'schema':1,'scope':'PUBLIC_CEX_FORWARD_PRICE_DIAGNOSTICS',
            'horizonMs':horizon_ms,'maxLabelDelayMs':max_label_delay_ms,
            'feeBpsPerSide':str(fee),'slippageBpsPerSide':str(slip),
            'perVenueStrategy':report,'dataSource':'PUBLIC_PRINT_NOT_EXECUTABLE_QUOTE',
            'prospectivelyPreregistered':False,'netTradeProfitabilityProven':False,
            'decision':'NO_GO','liveAllowed':False}


def main():
    parser=argparse.ArgumentParser(description='Offline CEX forward-price research, not fill backtest')
    parser.add_argument('tapes',nargs='+',help='Sealed public.jsonl tapes')
    parser.add_argument('--horizon-ms',type=int,default=1000)
    parser.add_argument('--max-label-delay-ms',type=int,default=2000)
    parser.add_argument('--fee-bps',default='5')
    parser.add_argument('--slippage-bps',default='5')
    parser.add_argument('--min-labeled',type=int,default=100)
    parser.add_argument('--output',required=True)
    opts=parser.parse_args()
    from research.phase4.audit import inspect_session
    if len(set(str(Path(p).resolve()) for p in opts.tapes))!=len(opts.tapes):
        raise ValueError('Duplicate archives')
    source=[]
    for path in opts.tapes:
        entry=Path(path)
        if entry.name!='public.jsonl':
            raise ValueError('Expected public.jsonl')
        inspect_session(entry.parent)
        with entry.open(encoding='utf-8') as handle:
            for line in handle:
                if line.strip():
                    source.append(decode(line))
                if len(source)>MAX_RECORDS:
                    raise ValueError('Unbounded forward-price source')
    result=forward_test(source,horizon_ms=opts.horizon_ms,
                        max_label_delay_ms=opts.max_label_delay_ms,
                        fee_bps=opts.fee_bps,slippage_bps=opts.slippage_bps,
                        min_labeled=opts.min_labeled)
    private_write(opts.output,result)
    print(dumps(result))


if __name__=='__main__':
    main()
