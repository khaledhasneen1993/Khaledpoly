# Phase 2 — paper validation and coordinated complete sets

Status: **in progress; first implementation delivered for review**. This branch is stacked on
`phase1-reliability` (PR #1), which has not been merged. LIVE remains locked.
No live keys, wallet changes, or broadcasts were used.

## Implemented in this delivery

- Shared `PaperMatchingEngine` for streaming executor and receive-order action replay. Replaces and
  removes the random per-poll fill heuristic and its probability configuration.
- Pending activation and cancellation latency (250ms each by default). Exact-price opposing prints
  must consume conservative queue ahead (visible size × 2). Partial fills, buys and sells, duplicate
  print suppression, multiple own orders at a level, cancel/fill races, and post-only activation checks.
  Quote touches, book-size reductions and cancelled external liquidity never grant fills.
- Full raw market WS frames plus normalized full-depth observations; append-only JSONL with local
  sequence, arrival/source clocks, monotonic elapsed time, run manifest and code revision. No Kafka
  dependency for recording; application decisions and order lifecycle events are recorded too.
  Recording failures propagate; matching errors halt the account. Sequence gaps, mixed runs, reversed
  arrival clocks, malformed data and missing matching configuration reject replay. A missing clean
  `RUN_END` is reported as an incomplete run.
- On disconnect/invalid data: invalidate depth and cancel simulated resting orders. On restart:
  cancel recovered resting orders, preserving filled quantities and cash; no invented queue priority.
- Atomic same-quantity pair reservations after verifying distinct tokens in the same ordinary binary
  condition. Both legs are funded before either is submitted. Negative-risk and multi-outcome sets
  are excluded. Uncertain pair submissions remain blocked for reconciliation.
- Virtual complete-set merge after actual simulated fills: remove both cost bases, credit one unit per
  set, deduct an explicit assumed merge cost (0.01 per merge), persist before publication. This does
  not call the chain. Redemption accounting accepts explicit payouts as a library operation only.
- Global conservative correlated pair budget of 100 (default), in addition to phase-one order/token/
  gross caps. No diversification credit between BTC and ETH. No new pairs while inventory is
  unhedged. Persist unhedged age; halt at 30 seconds or 25 worst-case collateral units. The executor
  enforces this independently of the strategy; restart cannot reset the timer.
- Coordinated maker-pair strategy with equal sizing, visible-depth size cap, causal opportunity
  ranking, limited quote churn, and transparent edge premiums for recent price changes, expiry,
  depth, latency and inventory. Merge cost must leave the required net margin. These are conservative
  heuristics, **not fitted fill probabilities, volatility forecasts or optimized portfolio weights**.
- Fetch `/fee-rate` and fail closed on unknown values. Current market constraints and fee schedules
  are recorded. Maker fee is zero; rewards/rebates are never assumed. `FeeModel`, full-depth FOK
  sweep evaluation, and completion-versus-sale-versus-wait comparison are tested research primitives.
  The old crossing/taker top-up paths are removed from the strategy. Streaming taker execution is
  still disabled until the next validation work below is finished.
- Optional 5-minute BTC/ETH discovery and rolling boundaries, alongside configurable 15-minute and
  hourly discovery. Five-minute quoting stays off by default; every actual order still requires
  current binary membership, active/accepting state, tick, size, expiry and fee metadata.
- Authenticated `/api/polymarket/paper-metrics` and `/paper-ledger`; local `/paper.html` dashboard for
  cash, available cash, realized net PnL, settlement costs, open reservations, inventory, quantity
  pairing, residual expiry exposure, data gaps, and 1s/5s/30s markouts. Missing markouts stay missing.
  Dashboard token stays in page memory; no external assets or token storage. Fill/markout metrics
  describe the current process; persisted cash, realized PnL and pair completion cover account history.

## Run and replay

Java 21 and Maven are required. From a clean committed checkout (the wrapper runs `mvn verify` before starting):

```bash
./scripts/start-paper-research.sh
```

The wrapper sets PAPER mode, enables conservative fills, and records the exact Git revision.
It refuses a dirty checkout. Existing services are not restarted silently; stop them first with
`./stop-all-services.sh` if necessary. Runtime tapes and state are ignored by Git.
Normal `./start-all-services.sh` still leaves fills disabled unless explicitly enabled.

The dashboard is at `http://127.0.0.1:8080/paper.html`. Set `POLYBOT_EXECUTOR_TOKEN` when needed.
The existing loopback bind and non-loopback authentication requirements remain in force.

Recorder configuration (common to the services):

| Property / environment | Default | Meaning |
| --- | --- | --- |
| `paper.record.directory` / `PAPER_RECORD_DIRECTORY` | empty | Empty disables recording; use one parent directory, separate run directory per service |
| `paper.record.revision` / `PAPER_RECORD_REVISION` | `unrecorded` | Exact committed revision; unrecorded runs cannot support promotion |
| `paper.matching.activation-ms` | 250 | Pending maker activation |
| `paper.matching.cancel-ms` | 250 | Cancellation acknowledgement delay |
| `paper.matching.queue-multiplier` | 2 | Visible external queue multiplier, at least 1 |
| `paper.settlement.merge-cost` | 0.01 | Assumed collateral cost per virtual merge, not a measured gas estimate |
| `paper.portfolio.gross-budget` | 100 | Correlated pair exposure cap, holdings basis plus pending buy cost |
| `paper.universe.five-minute` | false | Experimental 5-minute discovery |
| `paper.universe.fifteen-minute` | true | 15-minute discovery |
| `paper.universe.hourly` | true | Hourly discovery |

Use a **single executor run's** `events.jsonl`, not a concatenation of executor/strategy/ingestor files:

```bash
./scripts/replay.sh research/phase2/fixtures/synthetic.jsonl research/output/phase2-baseline
./scripts/replay.sh research/phase2/fixtures/synthetic.jsonl research/output/phase2-stress --stress
```

Output directories must not exist. Replay starts from the account snapshot and limits recorded in
that run. It produces a separate ledger and `report.json`; it never edits the running account.
Stress uses 1000ms activation/cancel latency, queue multiplier 4, and an extra 0.05 per merge.
The sample fixture is **synthetic arithmetic**, not historical market performance. Expected baseline:
cash 500.49, realized net PnL 0.49, three fills; stress: zero fills and cash 500.

## Evidence and remaining phase-two gates

`research/phase2/acceptance.json` freezes the intended acceptance criteria before performance testing:
100 resolved markets, 100 maker fills, seven complete heldout UTC days, quantity completion at least
95%, drawdown at most 10%, expiry residual at most 5, zero gaps/breaches, positive net PnL under base
and stress assumptions. These thresholds are starting research requirements, not tuned results.
They **do not constitute approval for LIVE**.

The current replay deliberately returns **NO_GO**. It replays recorded actions and can verify the
execution/accounting machinery. It does not yet rerun the whole strategy against an independent
heldout ingestor dataset. Treating frozen historical decisions under different fills as a closed-loop
strategy backtest would be incorrect.

Before claiming phase 2 complete:

1. Build and test the closed-loop strategy replay driver using ingestor raw events and a simulated
   clock, including cancellations, bankroll updates, market metadata changes and actual resolution
   events. Prove every decision uses only information received by that time.
2. Complete maker inventory reduction / sell quoting and integrate the tested hedge comparison with
   depth-aware, fee-aware PAPER risk reduction. Separate positive-edge entry from explicitly capped
   loss-reducing exits. A timeout currently suspends and alerts through events; it does not invent a
   risk-free exit or automatically re-enable the account.
3. Add verified resolution ingestion and explicit payout provenance for residual inventory. No
   expiry price, external exchange candle or presumed Up/Down winner is accepted as resolution.
4. Join decision edges, actual fills, pair completion durations, measured latency and rejection reasons
   into the reporting/dashboard pipeline; add alert deduplication and configured delivery adapters.
   No external Slack/Telegram messages have been sent or configured by this change.
5. Collect sufficient real recordings, check gaps and source lag, freeze the chronological split,
   calibrate queue/latency assumptions on training data only, then run heldout base and stress
   evaluations against the preregistered criteria. Include fee-doubling for taker experiments once
   that execution path is integrated; maker fees remain zero.

Public L2/print data does not expose exact FIFO position, hidden liquidity or all sequence gaps.
Identical print fingerprints are suppressed conservatively and may undercount legitimate identical
prints. The exact-price-only model deliberately forgoes inferred through-price fills. Full snapshots
and synchronous durable writes favor auditability over latency; benchmark and rotate recordings
before long unattended collection. The one-million-trade dedup bound fails closed, rather than
silently forgetting old fingerprints. Replayed marks with missing inventory prices are identified
as incomplete evidence. Real fees, capital lockup, resolution disputes and settlement costs still
need measurement in the research dataset.

Official references checked 2026-10-16:
- https://docs.polymarket.com/api-reference/wss/market
- https://docs.polymarket.com/trading/fees

The WS subscription uses the documented `assets_ids` key; `custom_feature_enabled` enables extra
market events. Public prints carry price, size, side, timestamp and may carry transaction hash.
