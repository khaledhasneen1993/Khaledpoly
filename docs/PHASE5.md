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


## Source-isolated Binance / Bybit signal ablations

\`research.phase5.cex_signals\` replays **sealed** phase-four public.jsonl
collector tapes and rejects changed SHA-256 files and mixed venue symbols.
Per venue and symbol it independently computes two causal diagnostics:

- Price momentum in basis points over a fixed recent trade count.
- Signed aggressive buy/sell volume imbalance **only when the venue's
  raw trade response actually reports aggressor direction**. Binance
  aggregate-trade \`m\` (buyer-is-maker) and Bybit spot \`side\` are
  parsed under their separate documented identities.

No implied candles, fabricated volume, forced cross-venue arbitrage or
invented trade outcomes. Duplicate venue trade IDs cannot refresh the
window. HTTP 403, disconnections, excessive source age, missing side
or missing observations produce explicit abstentions. CEX price direction
does not directly predict an unrelated Polymarket market resolution.

    python3 -m research.phase5.cex_signals \
      research/output/phase4-btc/segments/segment-000001/public.jsonl \
      --lookback 5 --max-age-ms 2000 \
      --output research/output/cex-signal-research.json

Only per-venue signal/abstention counts are produced. Without paired
future labels, a pre-registered holdout and genuine fills, no profitable
strategy or edge is claimed.
