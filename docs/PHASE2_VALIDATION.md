# Phase-two first delivery — validation evidence

Date: 2026-10-16. Java 21.0.12.1, Maven 3.9.9, Spring Boot 3.5.16.
Scope: PAPER execution/replay foundation. Phase 2 remains in progress; see `PHASE2.md`.

## Automated checks

`mvn --batch-mode --no-transfer-progress verify`: all seven reactor projects successful.
**59 tests, zero failures, zero errors, zero skips.** This includes the existing phase-one regression
suite and new queue, latency, economics, recording, markout, interval rollover and integration tests.

Key assertions:
- Opposing observed print volume consumes queue before partial/full fills. Touches and external queue
  cancellations do not grant fills. Identical print fingerprints are not reused.
- Multiple own orders at the same level cannot collectively consume more observed trade volume.
- Activation uses a past book; crossing maker orders reject. Source clocks cannot resurrect an order
  across staleness or a gap. Cancellation delay permits race fills before acknowledgement; ties cancel.
- Partial fills remain nonterminal and visible in open orders; sells require opposite aggressor side.
- Failed two-leg reservation leaves neither reservation. Merges subtract both cost bases and their
  explicit cost; duplicate operations do not re-credit cash. Reserved sale inventory cannot be merged.
- A 30-second unhedged timer survives account/pair-registry restart and independently halts the
  executor at the deadline; outstanding reservations are released without inventing downtime fills.
- Streaming executor tape and standalone replay produce identical partial quantities, cash and
  merge PnL in the synthetic binary fixture.
- The fee curve matches the official worked examples; full-depth FOK evaluation rejects incomplete
  liquidity and includes fees. The hedge comparison distinguishes profitable completion, waiting,
  and risk reduction. These primitives do not enable streaming taker trading.
- Markouts do not look ahead, do not use pre-horizon source data, and preserve missing observations.
- Five-minute slug windows roll at the exact boundary.

## Packaged checks

- Launched the packaged executor with PAPER simulation, recording enabled, public WS disabled,
  a separate temporary account, and no wallet credentials.
- Readiness UP; authenticated `/api/polymarket/paper-metrics` returned HTTP 200, available cash 500,
  realized PnL 0, no fills, no gaps, and null pairing completion for an empty sample.
- The same API without its token returned HTTP 401. `/paper.html` returned HTTP 200.
- Dashboard JavaScript passed `node --check`; shell launch/replay scripts passed `bash -n`.
  No browser visual or cross-device accessibility certification is claimed.
- Standalone packaged `ReplayMain` ran the committed **synthetic** JSONL fixture in baseline and
  stress modes. Baseline: three fills, cash 500.49, realized PnL 0.49. Stress: zero fills, cash 500.
  Both returned `NO_GO`. These numbers verify accounting, not attainable market returns.
- `git diff --check` passed. Runtime state, private account data and recordings are excluded from Git.

## Not verified / not complete

No real-market profitability experiment, seven-day heldout run, full strategy closed-loop replay,
measured production fill probability, real resolution/redemption ingestion, streaming taker hedge,
external alert delivery, long-duration recorder benchmark, or Docker deployment was performed.
Docker is unavailable in this environment. No live orders or on-chain transactions were sent.
The full phase-two acceptance gates in `research/phase2/acceptance.json` remain unmet.
