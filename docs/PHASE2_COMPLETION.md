# Phase 2: remaining implementation and evidence gates

The previously listed implementation gaps are now implemented on `phase2-paper-validation`.
**The empirical gate remains NO_GO. Phase 3 is not approved or started.** A successful build is not
proof of profitable fills; seven complete independent UTC days and the registered sample are still
required. No criteria have been weakened. No live funds, keys, signing or chain broadcasting are used.

## One strategy in streaming PAPER and replay

`ResearchSession` owns the causal strategy, cash reservations, matching, cancellation lifecycle,
virtual merge, inventory exits, and explicit resolution accounting. The executor adapter and
`ClosedLoopReplay` instantiate this same class. Replay consumes `RESEARCH_*` public observations,
never recorded orders, decisions, fills or historical account balances. All experiment accounts start
from the frozen initial cash. `RawTapeNormalizer` additionally supports ingestor `RAW_MARKET` frames
and the recorded market metadata; missing snapshots produce gaps rather than invented depth.

The record-only collector is independent of the strategy. It writes the documented raw WS frames,
normalized depth/trades/ticks, current Gamma/CLOB metadata and fee evidence, venue clock samples,
resolution responses and errors. It retains unresolved conditions after market expiry. A dedicated
clock scheduler prevents HTTP polling from blocking risk ticks. Receive-order delivery is serialized;
replay never sorts by exchange timestamp. Old, future or missing source data fails closed. Tick-size
changes cancel incompatible quotes until current metadata is available.

The normal research entry point is:

```bash
./scripts/start-paper-research.sh
```

This now runs the executor alone, sets `paper.closed-loop.enabled=true`, selects the committed
`research/phase2/research-config.json`, records the code revision, and disables the legacy strategy
service. A clean verified build is required. Direct legacy/manual order APIs cannot concurrently
control a closed-loop account. Existing phase-one/first-delivery APIs remain available for their
original mode and regression tests.

For strategy-independent data only:

```bash
PAPER_RECORD_SECONDS=3600 ./scripts/collect-paper-data.sh
```

This launches a public-data ingestor with simulation and strategy disabled; it creates no trading
account. `timeout` ends it cleanly; forced shutdown or API failures are visible in the recording.
No private keys are required. Default discovery is BTC/ETH 15-minute and hourly; 5-minute discovery
is opt-in with `PAPER_FIVE_MINUTE=true`. Versionless legacy Gamma token arrays are recognized only
in the read-only collector and are cross-checked against both CLOB books. This does not select or
change a signing protocol. Fees use the documented Gamma `feeSchedule.rate` and `exponent`, with no
category-rate guesses. Missing/unsupported curves stop that experiment's entry path.

## Inventory reduction and payouts

After the second-leg wait, the strategy cancels outstanding pair orders and waits for their modeled
cancellation acknowledgements. It can quote a maker sell against owned, unreserved inventory. After
the unhedged deadline it suspends new entry and compares completion against sale, using current
cost basis, full available depth and exact per-level taker fees. Positive-edge completion must leave
its configured margin. A loss-reducing exit has a separate cumulative loss budget; pending maker
loss exposure reserves that budget across markets. It never opens a short.

Taker risk actions have activation latency, an explicit price bound, FOK depth checks, current fees,
and fresh-book requirements. Each price level is accounted separately, avoiding VWAP rounding cash
creation. They cannot reuse the same public depth source snapshot. Missing liquidity or an exceeded
loss budget leaves the inventory visible; there is no assumed exit. Below-minimum dust waits for
verified resolution. Rewards remain zero.

The official `GET https://data-api.polymarket.com/v2/resolutions?condition=...` response must match
prior outcome-slot metadata and have `status=resolved`, a transaction hash, resolved block/time, and
a valid binary payout vector. Proposed/challenged prices and expiry candles are rejected. Payouts
are normalized by their vector denominator (including split payouts), and redemption is idempotent.
This verifies the terminal public API evidence; it is not an independent cryptographic finality proof.

Checkpoint and ledger files survive restart. Recovered orders lose queue priority and are canceled.
If nonempty inventory is recovered, entry remains suspended and the exit loss budget is conservatively
considered spent until reconciliation; restarting cannot buy a fresh loss allowance. Profitable exits
and explicit resolution remain possible. File corruption or persistence failure stops the session.

## Reporting and alerts

The account dashboard additionally shows decision/rejection counts, expected-edge distribution,
actual per-level fills with fees and purpose, decision-to-fill times, pair completion durations and
realized net edge per merged set. Markouts keep missing samples missing. PAPER activation/cancel
latencies are assumptions; decision-to-fill durations are measurements of this model, not venue
execution acknowledgements. Public API RTT and source lag are measured separately.

`/api/polymarket/paper-alerts` exposes a durable local outbox. Repeated alert keys are throttled;
failed deliveries back off and survive restart. External delivery is optional and disabled unless
configured with `paper.alerts.slack-webhook` or `paper.alerts.telegram-token` plus
`paper.alerts.telegram-chat`. Never put those values in tracked files. No external messages were sent.
Delivery is at least once: transport retries may duplicate a notification after a lost acknowledgement.

## Freeze, train and test

The replay wrapper verifies a clean fresh build and records the strategy revision separately from the collector revision. The original `acceptance.json` is unchanged. Freeze must precede the heldout window. It binds the
configuration, acceptance criteria, and implementation digest. A historical date cannot be declared
heldout retroactively. Calibration reads training data only and refuses any row in the heldout window.
It reports source lag/clock RTT and conservative latency bounds. Public L2 lacks own FIFO labels;
queue multipliers are uncertainty assumptions, not fitted fill probabilities.

```bash
python3 research/phase2/experiment.py calibrate TRAIN/events.jsonl 2026-10-17T00:00:00Z
python3 research/phase2/experiment.py freeze research/phase2/research-config.json 2026-10-17T00:00:00Z research/phase2/frozen-experiment.json
./scripts/closed-loop-replay.sh HOLDOUT/events.jsonl research/output/heldout-base research/phase2/research-config.json --freeze research/phase2/frozen-experiment.json
./scripts/closed-loop-replay.sh HOLDOUT/events.jsonl research/output/heldout-stress research/phase2/research-config.json --stress --freeze research/phase2/frozen-experiment.json
python3 research/phase2/experiment.py evaluate research/phase2/frozen-experiment.json research/output/heldout-base/report.json research/output/heldout-stress/report.json research/output/phase2-gate.json
```

Choose a future UTC midnight when creating a new freeze; never reuse the example date after it has
passed. Replay primes only already-known market metadata before the split; trading and performance
begin inside the declared heldout window. Future resolutions do not leak into earlier decisions.
Baseline and stress use the identical input hash, separate ledgers, and the full closed-loop strategy.
Stress doubles fees, increases activation/cancel latency and queue ahead, and adds settlement cost.

The evaluator verifies seven complete UTC days of coverage, 100 resolved **traded** markets and 100
maker fills, completion, drawdown, expiry residual, marks/markouts, no gaps or breaches, no unresolved
inventory or pending actions, and positive realized PnL in both runs. Missing provenance, incomplete
recordings, changed frozen code/configuration, or insufficient samples mean NO_GO. `liveAllowed`
always remains false. A GO only permits extended PAPER / phase-three research.

GitHub verification also runs a bounded 90-second independent public-data smoke on pushes to the
phase-two branch and runs both baseline/stress closed-loop replays before saving `phase2-public-recording` as an artifact. This checks the collector, not
the seven-day performance gate. `inspect_recording.py` reports actual errors and counts without
inventing fills when a public endpoint is blocked or unavailable.

Official endpoint schemas checked 2026-10-16:
- https://docs.polymarket.com/api-reference/markets/get-resolution-state
- https://docs.polymarket.com/api-reference/markets/get-market-by-id
- https://docs.polymarket.com/trading/fees
