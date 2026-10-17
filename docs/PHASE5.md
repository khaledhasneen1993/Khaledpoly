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


## Own-order fill, completion, latency and quality diagnostics

\`research.phase5.fill_research\` independently evaluates the three
existing **censored, blocked/purged** label targets from
\`polybot_sdk.learning\`: order fill, *unconditional* initial-order-to-
second-leg group completion, and adverse post-fill markout. The second
target is explicitly **not** "probability of a second leg conditional on
a first fill"; those denominators must not be conflated.

    python3 -m research.phase5.fill_research \
      research/data/own-order-labels.jsonl \
      --holdout-start-ms 2000000000000 \
      --min-train 1000 --min-holdout 200 --min-class 20 \
      --output research/output/phase5-fill-research.json

The module reports every target separately: censored/positive/negative
counts, observed (not predicted) filled-order P50/P90 latency, Brier
vs base rate and calibration where sufficient. A censored order is
NEVER silently turned into a nonfill. Models remain unqualified even
if a small PAPER holdout yields an attractive fit; a string claiming
\`VENUE_EXECUTION\` is not independently authenticated venue evidence.
No synthetic FIFO or fill labels are generated.


## Politics, Sports, news, multi-outcome and Negative Risk scenarios

\`research.phase5.event_rules\` is a research-only **independent
scenario screener**, not a predictor or executable strategy. It
requires explicit causal market/forecast availability, a complete
probability simplex, explicit bounded fee/slippage assumptions and
category-specific safeguards. Politics abstains when rules are
missing or an oracle/dispute state is unknown; Sports uses separate
pregame/score-freshness and final-status rules. News must identify
the same event and have nonfuture publication and receipt clocks.
For multi-outcome and Negative Risk, incomplete membership abstains.

    python3 -m research.phase5.event_rules \
      research/data/event-forecast.json --decision-ms 1800000000000 \
      --output research/output/phase5-event-screen.json

Any positive "scenario edge" is an arithmetic *what-if* from
unverified input probabilities, not measured realized PnL or a market
mispricing finding. This module does not call Polymarket, dispatch
orders, or authenticate the oracle, fees, groups, match score or news.
A flag supplied by a data feed is not an independent truth check.


## Portfolio correlated scenario VaR, ES and settlement concentration

\`research.phase5.portfolio_risk\` computes empirical VaR and expected
shortfall from **whole-portfolio joint scenario outcome vectors**, not
a sum of unrelated venue/token marginal VaRs. Inputs must include
complete correlated settlement/group IDs and a common nonregressing
scenario observation clock; missing group payoffs, nonfinite numbers
or duplicated scenarios fail closed.

    python3 -m research.phase5.portfolio_risk \
      --positions research/data/portfolio-positions.json \
      --scenarios research/data/joint-scenarios.jsonl \
      --min-scenarios 100 --confidence 0.95 \
      --output research/output/portfolio-scenarios.json

Also reports gross acquisition exposure and concentration in the
largest correlated settlement group. Unlike actual market risk, this
calculation assumes every supplied joint scenario return is meaningful:
it **does not** model on-chain liquidation, negative-risk conversion,
oracle challenge/appeal, counterparties or missing tails. Real venue and
resolution evidence are unavailable, so results never qualify risk or
real execution.


## Forward-price research labels for venue-isolated signals

\`research.phase5.cex_forward\` evaluates the **future observed public
exchange print**, not a maker/taker order fill. Momentum and aggressive
flow are evaluated separately with a fixed price-label horizon and a
bounded receipt delay. At most one outstanding signal per strategy and
venue is evaluated at a time. HTTP gaps, future prices missing inside
the label window and unfinished observations are *censored*, never
turned into losing trades.

    python3 -m research.phase5.cex_forward \
      research/output/phase4-btc/segments/segment-000001/public.jsonl \
      --horizon-ms 1000 --max-label-delay-ms 2000 \
      --fee-bps 5 --slippage-bps 5 --min-labeled 100 \
      --output research/output/phase5-cex-forward.json

Reports hypothetical directional spot-price outcomes after **assumed**
round-trip costs. Prints are not executable quotes and do not support
claims about Polymarket fills, maker queue priority or net profits.
Binance and Bybit labels never substitute for each other. The absence
of seven-day prospective evidence still prevents strategy qualification.


## Embargoed cross-strategy walk-forward folds

\`research.phase5.walk_forward\` accepts a fixed list of
\`trainBeforeMs\`, \`testStartMs\`, \`testEndMs\` windows. Every fold
must have positive embargo, increasing nonoverlapping tests, and
purging of all market/settlement-group linked observations crossing
training/embargo/test boundaries **across strategy IDs**.

    python3 -m research.phase5.walk_forward \
      research/data/offline-trades.jsonl \
      --folds research/data/frozen-fold-calendar.json \
      --min-test-groups 30 --stress-multiplier 2 \
      --output research/output/phase5-walk-forward.json

Per strategy and fold the analyzer reports independently observed
group counts and explicitly declared hypothetical net cost/PnL
metrics. It will not select a winner based on one fold or declare
profitability: the source, fold calendar and experiment parameters
still require independent *prior* registration and real venue-label
verification.


## Phase 5 actual public PAPER integration smoke

On phase-five branch pushes, CI now reuses the Phase-3 public PAPER
capture (which includes a sealed phase-four-compatible
\`signals/public.jsonl\`) and runs both Phase-5 CEX signal and forward
price-label research on that **actual retrieved, time-stamped exchange
sample**, not only mocked unit tests. The results are uploaded as
\`phase5-public-spot-research\`; short and/or access-blocked samples
must remain \`NO_GO\`. Missing Bybit data is not filled using Binance.
This is **not** the prospective seven-day gate, and public prints are
not genuine maker fills.
