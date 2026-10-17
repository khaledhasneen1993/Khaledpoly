# Phase 5 — offline research evidence and strategies (in development)

This branch begins software implementation while deferring the **seven-day
prospective external capture** until after Phase 4–6 engineering work.
Deferral is not waiver: no part of this work authorizes LIVE, funded
trading, a qualified fill model or claims of net profitability.

## First module: purged offline strategy cost baseline

\`research.phase5.offline_benchmark\` accepts local JSONL trade evidence
with explicit, immutable identifiers and pre-cost gross PnL, with one
market/group, strategy, causal open/close timestamp and **explicit**
per-side fee and slippage assumptions per row.

    python3 -m research.phase5.offline_benchmark \
      research/data/offline-trades.jsonl \
      --holdout-start-ms 2000000000000 \
      --min-heldout-groups 30 --stress-multiplier 2 \
      --output research/output/phase5-strategy-baseline.json

It refuses duplicate trades, noncausal data, non-finite/negative
costs, and mixed PAPER-vs-real-venue provenance. Purging links all trades
within each market and user-designated group, across strategies, so
training and holdout never share connected evidence. It reports
heldout cash PnL **after** explicit cost assumptions, 2x-slippage stress,
closed-trade drawdown, and whether two strategies were observed on exactly
the same market groups. It does not assume a trade made in simulation
would have filled on the venue.

It never declares a tested model or profit strategy qualified. This is
an accounting baseline for the upcoming independent Binance/Bybit
signals, events, Sports, Politics and multi-outcome experiments.

## Engineering to continue

- Add independently versioned strategy adapters for CEX signals and
  event/forecast inputs (unknown source => abstain).
- Isolate category rules and verify group outcome/settlement boundaries.
- Run fixed, blocked/purged walk-forward comparisons against baseline
  with measured latency/fees/slippage and stop if labels are insufficient.
- Test several replay regimes (including data gaps and oracle disputes).
- Extend model labels only from real venue evidence, never PAPER inferred
  touches, once external datasets are collected.
- Keep risk, accounting and execution centralized in the existing engine.

**External acceptance still deferred:** a stable seven-day host, consistent
Polymarket/CEX book data, independent terminal settlement, real queue/fill
labels, and prospective pre-registered holdout. Deferred is not passed.
