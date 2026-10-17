# Phase 3 engineering delivery and qualification status

This branch supplies the PAPER/shadow research implementation below. **Full third-phase acceptance
remains incomplete** because market evidence and execution qualification have not been obtained.
The implementation must not be described as a qualified ML trading system, latency-arbitrage bot,
verified multi-outcome executor or deployed fund manager. Nothing here enables LIVE.

## Delivered and bounded scope

| Area | Implementation | Operational boundary |
| --- | --- | --- |
| Current Polymarket parameters | `ClobMarketParameters` and `ResearchFeed` read `/clob-markets/{condition}` and validate membership, lot/tick, fee curve and acceptance | Unknown fees/unsupported maker fees/risk universe fail closed. No category defaults or signing migration. |
| Maker research | Inventory maker plus cash/owned-inventory limits | Shadow proposals only; baseline Java PAPER still owns its account. |
| Complete-set research | Equal-size atomic proposal groups, volatility/expiry threshold, optional fill-model inference | Unknown volatility raises the screening threshold. Fill/second-leg estimates stay unknown without qualified data; no artificial fills. |
| Events and oracle risk | Availability-time forecast and explicit resolution-risk join | Hashes bind inputs, not the truth of a forecast. Unknown or disputed risk abstains; no news-to-probability claim. |
| CEX signals | Public Binance/Bybit spot sampling, payload evidence, source/receipt clocks, deduplication, bounded joins, rate-limit backoff | REST samples are incomplete and do not measure latency arbitrage. CEX price basis is not a Polymarket probability. |
| Fill/second-leg/adverse selection | Censored labels, market-group temporal purging, logistic baseline, heldout Brier and calibration, inference | No real venue training dataset exists in this delivery. PAPER and venue labels cannot be mixed. All models remain unqualified. |
| Portfolio research | Atomic edge-ranked cash/group/exposure allocation and historical joint VaR/ES/correlation | Allocation is a deterministic greedy heuristic. Missing joint history yields unknown risk; acquisition cost remains separately reported. |
| External strategies | Authenticated `/api/research/v1/proposals/screen`, durable idempotent receipts, expiry/generation/lot/tick/cash/inventory checks | Screening never submits an order. 64 KiB request and 10,000-receipt bounds; archive and start an isolated research account when full. |
| Multiple accounts | Distinct endpoint/state-directory registry, observation/session binding, read/research roles and indicative fund NAV | Registry does not create accounts or transfer capital. Each executor needs an independently configured durable ledger and token. Unknown/stale prices produce unknown NAV. |
| Politics/sports | Public tag/keyset discovery preserves CLOB/position IDs and reports partial universes; category-independent binary proposal contracts | Baseline execution discovery remains crypto intervals. Discovered broader markets require an evidenced adapter before execution. |
| Multi-outcome/negative risk | Explicit complete-universe basket and NO-conversion scenarios; augmented/incomplete universe refusal | Actual venue conversion, settlement and execution are not implemented or verified. |
| Collateral/gas | pUSD/Polygon identity-evidence validation and batch gas-cost scenarios | Evidence is not a chain check. No approvals, wrapping, native-USDC substitution or broadcast. |
| Performance | Reproducible in-process validation/proposal benchmark with p50/p95/p99 | Does not measure network/venue latency. Rust/gRPC migration remains unjustified without a measured production bottleneck. |
| Operations | CLI commands, causal shadow tape/replay, source-installable SDK, CI and bounded public integration capture | Integration smoke does not replace seven complete heldout days or qualify strategies. |

## Current API correction

Official V2 migration documentation says production CLOB V2 is live, collateral is pUSD, and per-market
fee parameters come from `getClobMarketInfo()` (`fd.r`, `fd.e`, `fd.to`), rather than treating the legacy
`/fee-rate` base fee as the actual curve. The ingestor now reads the public V2 market-info endpoint.
It requires explicit fee details or explicit zero maker/taker base fees and fails closed on unknown data.
A field omitted by the venue is not permission to trade. Existing reference results are historical and
must not be retroactively relabeled as evidence for this changed collector.

References checked 2026-10-17:

- https://docs.polymarket.com/v2-migration
- https://docs.polymarket.com/market-data/discover-markets
- https://docs.polymarket.com/trading/fees
- https://github.com/Polymarket/py-clob-client-v2/blob/main/py_clob_client_v2/endpoints.py
- https://github.com/Polymarket/py-clob-client-v2/blob/main/py_clob_client_v2/client.py
- https://docs.polymarket.com/concepts/negative-risk
- https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints
- https://developers.binance.com/en/docs/products/spot/rest-api
- https://bybit-exchange.github.io/docs/v5/market/recent-trade
- https://bybit-exchange.github.io/docs/v5/rate-limit

## Commands

All outputs must be new paths; runtime data belongs under ignored `research/output/`. Do not commit
credentials or raw private account data. SDK token inputs use environment variables.

```bash
python3 -m research.phase3 discover --category politics --output research/output/politics.json
python3 -m research.phase3 discover --category sports --output research/output/sports.json
python3 -m research.phase3 collect-signals --seconds 60 --output research/output/signals-001
python3 -m research.phase3 shadow --strategy complete-set --features research/output/signals-001/features.jsonl \
  --seconds 60 --output research/output/complete-set-001
python3 -m research.phase3 replay-shadow research/output/complete-set-001 --output research/output/complete-set-001-replay.json
python3 -m research.phase3 train-model research/output/labels.jsonl --target fill \
  --holdout-start 2026-10-25T00:00:00Z --output research/output/fill-model.json
python3 -m research.phase3 predict research/output/fill-model.json research/output/feature-vector.json
python3 -m research.phase3 portfolio-risk research/output/snapshot.json research/output/joint-bids.json --output research/output/risk.json
python3 -m research.phase3 profile executor-service/target/phase3-snapshot.json --output research/output/profile.json
python3 -m research.phase3 accounts research/output/accounts.json --output research/output/accounts-report.json
python3 -m research.phase3 basket research/output/basket-scenario.json --output research/output/basket-report.json
```

The sample holdout timestamp above is an example, not a registered experiment. Use a prospectively
frozen cutoff and untouched evaluation dataset. The trainer does not certify preregistration.
SDK version 0.2.0 is source-installable and has no runtime dependencies beyond Python 3.10+.
The wheel excludes compiled caches; CI also installs it in an isolated environment and runs the HTTP snapshot contract through its console entry point.

For event research, use `--strategy event-probability --features your-append-only-features.jsonl`.
Provide `forecast/CONDITION/first_outcome_probability` and `forecast/CONDITION/resolution_risk` rows
with source and receipt timestamps and evidence SHA-256. Only an explicit fresh risk value of zero
permits a hypothetical proposal. `research/phase3/examples.json` illustrates schemas and is synthetic.
It is not usable market evidence. Feature time-to-live is 2 seconds by default, including forecasts.
A rotated/truncated feature file, a changed session, future data or incomplete JSON row never produces
an optimistic feature update. Incomplete trailing lines wait for completion.

`--fill-model` embeds the entire unqualified artifact in a shadow manifest. Optional complete-set
fill inference also requires a fresh explicit `polymarket/CONDITION/volatility` input. Missing inputs
leave probability unknown. The second-leg target is supported by training/inference, but combining
marginal fill probabilities is not treated as a measured joint completion probability.

A label contains own-order ID, market ID, submission and feature-availability times, end of observation,
actual fill/cancel times where known, provenance and the exact six features listed in `learning.py`.
An early cancellation before the target horizon is censored. Second-leg labels require an explicit
second-leg time after first fill. Adverse selection requires a markout observed after the complete
post-fill horizon. Never derive own fills, FIFO rank, pairing, negative labels or markouts from price
touches or incomplete public samples. Missing own-order feature/label instrumentation is missing data,
not a license to synthesize rows. Real venue label acquisition is outside this PAPER-only deployment.

Historical risk panels are `[availability_ms, {token: bid}]` rows in strict receipt order, up to 10,001
rows. Only complete joint adjacent intervals contribute. Default minimum is 100 intervals of 1 second.
Future panels fail and stale/missing panels abstain. Constant histories have unknown correlation;
VaR zero is not a bound on future loss. Indicative account NAV uses fresh top bids without pretending
that an entire position can be liquidated at that price.

## External proposal screen

POST authenticated JSON to `/api/research/v1/proposals/screen` with `id`, `strategy`, `accountId`,
`sessionId`, `sequence`, and `legs`. Each leg carries `condition`, `token`, boolean `buy`, `price`,
`size`, and `expiresMs` from the current observation. JSON prices/sizes may be strings.
The route accepts chunked bodies but bounds bytes before JSON parsing. A valid receipt has
`status=SCREENED_SHADOW_ONLY`, an expiry and `executionEnabled=false`; it is never an execution ack.
Repeated IDs with different content conflict; identical current-generation retries return the original
receipt across a restart of the inbox. Stale session/generation requests conflict. Multiple receipts in
a generation share the cash and market/gross budgets and cannot reuse a token. Failed atomic groups
do not consume the screening budget. The durable inbox is next to the account state file.

Screening caps are fixed at 25 per order/market and 100 total acquisition exposure, with existing
holdings/open reservations included. Python research may impose stricter explicit correlation groups;
the HTTP screen does not claim to infer correlations. SDK `PaperClient` remains GET-only.
The shared executor token is still privileged; read/research registry roles are local orchestration
permissions, not independently scoped server credentials. Do not give that token to untrusted code.

## What prevents full acceptance

1. Seven independently recorded complete heldout days and registered resolved/fill samples are still
   absent. Existing `research/phase2/acceptance.json` is unchanged; all new code needs a new freeze.
2. Venue-calibrated fill/second-leg/markout labels, untouched evaluation and a demonstrated net edge
   are absent. No model is promoted and no reward income is assumed.
3. Broader market discovery and actual multi-outcome settlement/execution require verified adapters
   and replay evidence. Scenario arithmetic is deliberately not an executable venue integration.
4. Production multi-account/fund administration, chain-verified collateral operations and LIVE remain
   outside the authorized PAPER-only system. Observation isolation does not certify those operations.

These are explicit incomplete requirements, not completed tasks hidden behind passing unit tests.
The delivered toolkit makes them measurable and testable; it does not manufacture their evidence.

## First public integration evidence

Commit `1db1277b693a17613418da7497bb474feea345d8`, GitHub run
[39018408308](https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39018408308), artifact
`12095344346`: 45 valid streaming PAPER observations, exact shadow replay, four discovered markets
and four fresh books at the last observation. Shadow fills and PnL remain unknown. New strategies
were not executed. The CEX collector recorded 317 Binance feature rows; Bybit returned HTTP 403,
then all later attempts remained in backoff. This is **partial CEX coverage**, not a successful Bybit
connection or an arbitrage result. The summary now exposes per-venue counts explicitly.

The CI job succeeding means the software checks and recording procedure completed. It does not
turn network restrictions, missing venue data or empirical NO_GO into a pass for trading.
