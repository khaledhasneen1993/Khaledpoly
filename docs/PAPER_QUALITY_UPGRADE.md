# PAPER quality upgrade (0.6.0 research candidate)

This branch extends the existing implementation. It does not qualify a strategy, train a venue-calibrated model, or enable funded execution. All strategy acceptance remains `NO_GO`.

## Correctness fixes

- Screen/virtual bridges bind the original account state, session, sequence rules and 250 ms observation lifetime. An advancing GET response clock alone no longer invalidates admission. No IDs, quote expiries or observations are rebased. Java still checks current books and risk. Changed accounts and expired quotes fail before POST.
- Event candidates recompute probability minus **actual passive quote price**, assumed fees, slippage and the existing two-cent risk margin. A positive edge at a different reference price cannot justify entry. Actual negative-risk market metadata also vetoes binary admission.
- Offline and walk-forward evidence counts use transitive market/group components. Thirty linked markets count as one independent group. Exact common strategy coverage and purging are retained.
- The common full-UTC-day capture window scopes reconnect/error/source-silence checks. Warmup faults outside it do not invalidate an otherwise complete window; in-window faults still fail. Full-tape framing, sequence and clean-close inspection remains mandatory.

## Strategy and portfolio

`PairPolicy.requiredEdge` already prices observed movement, latency, expiry, depth and inventory. It remains the central transparent policy. The second-leg maker wait now shrinks with observed movement and time remaining: at most five seconds, half the unhedged deadline, and one quarter of remaining life. Existing fee-aware choice, taker source freshness, loss budget and position limits still decide whether completion or sale is admissible. It is a heuristic that needs prospective comparison.

`research.phase5.portfolio_admission.plan` connects exact small-universe joint-scenario optimization to existing admission review. It includes held basis and pending buy reservations in group exposure and scenario risk, and emits one atomic portfolio envelope. Exits remain with the central bounded risk engine. Limits: 12 candidates, 128 aligned scenarios, four selected positions by default and 16 Java legs per atomic group. Each input candidate is one market; every known condition needs an explicit correlation group. Missing held-token scenarios fail closed. Inputs are declared assumptions, not measured correlations or probabilities.

```bash
python3 -m research.phase5.portfolio_admission \
  --snapshot snapshot.json --candidates candidates.json \
  --scenarios joint-scenarios.json --groups correlation-groups.json \
  --output portfolio-plan.json
```

Candidates use the existing `{id, edge, legs}` contract (additional research annotations are permitted before final envelope construction). Scenario JSON maps scenario IDs to **all held and proposed tokens**, each with its assumed net return on acquisition basis in `[-1,10]`. Example: `{"up":{"tokenA":"0.2","tokenB":"-1"},"down":{"tokenA":"-1","tokenB":"0.2"}}`. Group JSON maps conditions to group IDs. Do not invent independent settlement scenarios for correlated outcomes. Extract a non-null `envelope` for the existing opt-in virtual PAPER bridge; planning itself submits nothing.

Politics/Sports forecasts remain explicit, unverified research inputs. This upgrade corrects entry economics; it does not add a validated news classifier or semantic event exit model. The central inventory/expiry/gap risk controls remain responsible for bounded execution exits.

## Fill research and execution assumptions

Own-order telemetry preserves the original six `features` and adds `featuresV2`: spread, queue ahead, inventory imbalance, source age, seconds to expiry, movement, order size, order/depth ratio and bid/ask size imbalance. Labels preserve that causal vector. Inference now uses queue at the actual quote, the configured queue multiplier and the same normalized inventory imbalance as training.

```bash
python3 -m research.phase3 train-model labels.jsonl --feature-schema v2 \
  --target fill --holdout-start '2026-11-01T00:00:00Z' --output fill-v2.json
```

Choose and record the cutoff **before** holdout collection; the example timestamp is not a registered experiment. Default evidence minima and market/group purging remain. Legacy v1 artifacts work. Mixed provenance, insufficient labels and missing features do not produce a qualified model. A pair's minimum marginal fill prediction is advisory, not a calibrated joint completion probability. The matching engine never substitutes probabilistic predictions for prints.

ResearchConfig adds `latencyJitterMs` (0..60000) and `latencySeed`. Missing fields default to zero for older configuration files. Activation, cancellation and pending-taker delay use a reproducible hash of action and identity. Default jitter is zero. Stress profile adds at least 500 ms of nonnegative jitter, higher queue, fees and settlement assumptions. Freeze the full serialized configuration and source revision before a new run; do not compare old/new configuration hashes as identical.

The conservative maker model still requires real recorded aggressor prints, consumes queue and supports partial fills. No touch fills, cancellation queue credit or fills across gaps. Existing markouts remain adverse-selection diagnostics. Maker/taker fees and settlement costs retain the current validated implementation; gas remains a declared scenario, and rebates are zero.

`research.phase5.book_impact.scenario(snapshot, token, buy, size, at_ms=...)` sweeps recorded visible depth to estimate VWAP, slippage and a counterfactual remaining-book mid. Incomplete/truncated/stale depth is not extrapolated. It creates **zero fills**, modifies no observed book, excludes fees and is not a fitted impact model. Execution already caps takers to observed top-level depth; this helper is for conservative research comparisons.

## Minimal operation

Requires Java 21, Maven, Python 3.10+, a committed source checkout and a strong `POLYBOT_EXECUTOR_TOKEN` of at least 24 characters supplied through your environment. Do not commit it.

```bash
./scripts/run-paper-minimal.sh
# Open http://127.0.0.1:8080/paper.html
# Ctrl-C performs graceful shutdown.
```

One executor process contains the causal research strategy and virtual matching engine. Kafka, ClickHouse, Grafana and a separate strategy process are unnecessary for this profile. The launcher runs Maven verification when its revision build stamp is absent/stale. State defaults to `state/minimal`; journals to `research/data/minimal`. A fixed state directory preserves account, checkpoints, risk stops and alert outbox. A lock rejects a second supervisor for that directory. It binds loopback and strips venue credential environment variables. Public-data collection can still fail due to network access/rate limits; that does not grant permission to invent missing data.

Optional environment overrides: `PAPER_MINIMAL_PORT`, `PAPER_MINIMAL_STATE`, `PAPER_MAX_RESTARTS` (0..5, default **0**). With an explicit restart budget, unexpected process exit or persistent failed health after a 60-second startup grace triggers bounded backoff and restarts with identical state. A risk halt with healthy HTTP does **not** trigger a restart or reset the risk stop. Inspect logs and the ledger when the budget is exhausted. Do not share an account state directory with another launcher.

## Monitoring

The existing `/paper.html` adds active market freshness, source age, time to expiry, inventory imbalance, session drawdown, order fill rate and per-fill-sample latency percentiles. Percentiles are **decision-to-fill per fill sample**, not HTTP or venue transport latency. `orderFillRate` counts each submitted order once if it received any quantity; it is not a queue calibration statistic. Session metrics reset on restart; ledger cash/realized PnL remain cumulative.

The durable alert outbox retains existing optional Slack/Telegram adapters. Stale depth cancellation and explicit capture gaps generate warnings; account risk halts and inventory breaches carry CRITICAL severity. Unhedged output is limited to once per market per minute before existing durable dedup/retry handling. Unset channels keep alerts local. No messages were sent for verification. This does not implement an independent external capture-gap pager or per-channel delivery acknowledgement.

## Verification and remaining evidence

Local Maven reactor verification passed 130 Java tests; all phase2..6 Python suites passed 190 tests. Wheel installation and new-module imports outside the checkout also passed. CI runs once on this branch push and retains its separate public smoke evidence; a successful build is software evidence only. Short public smoke may legitimately produce zero orders/fills.

Before any economic acceptance: collect the preregistered common seven-day source window, enough independent held-out market groups, actual execution labels for queue/fill calibration, and explicit resolution/oracle evidence. Validate event forecasts, joint scenarios and impact/latency assumptions on held-out data. No profitability, venue-calibrated fill model, Bybit availability, rebate income or permission for funded execution is claimed.
