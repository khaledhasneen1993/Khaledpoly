# Phase 3 engineering delivery and qualification status

This branch supplies the PAPER/shadow research implementation and opt-in virtual-order execution below. **Full third-phase acceptance
remains incomplete** because market evidence and execution qualification have not been obtained.
The implementation must not be described as a qualified ML trading system, latency-arbitrage bot,
verified multi-outcome executor or deployed fund manager. Nothing here enables LIVE.

## Delivered and bounded scope

| Area | Implementation | Operational boundary |
| --- | --- | --- |
| Current Polymarket parameters | `ClobMarketParameters` and `ResearchFeed` read `/clob-markets/{condition}` and validate membership, lot/tick, fee curve and acceptance | Unknown fees/unsupported maker fees/risk universe fail closed. No category defaults or signing migration. |
| Maker research | Inventory maker plus cash/owned-inventory limits | Shadow by default; explicit external PAPER mode routes passive quotes through the shared Java matching engine. |
| Complete-set research | Equal-size atomic proposal groups, volatility/expiry threshold, optional fill-model inference | Unknown volatility raises the screening threshold. Fill/second-leg estimates stay unknown without qualified data; no artificial fills. |
| Events and oracle risk | Availability-time forecast and explicit resolution-risk join | Hashes bind inputs, not the truth of a forecast. Unknown or disputed risk abstains; no news-to-probability claim. |
| CEX signals | Public Binance/Bybit spot sampling, payload evidence, source/receipt clocks, deduplication, bounded joins, rate-limit backoff | REST samples are incomplete and do not measure latency arbitrage. CEX price basis is not a Polymarket probability. |
| Fill/second-leg/adverse selection | Censored labels, market-group temporal purging, logistic baseline, heldout Brier and calibration, inference | No real venue training dataset exists in this delivery. PAPER and venue labels cannot be mixed. All models remain unqualified. |
| Portfolio research | Atomic edge-ranked cash/group/exposure allocation and historical joint VaR/ES/correlation | Allocation is a deterministic greedy heuristic. Missing joint history yields unknown risk; acquisition cost remains separately reported. |
| External strategies | Authenticated `/api/research/v1/proposals/screen`, durable idempotent receipts, expiry/generation/lot/tick/cash/inventory checks | Screening never submits an order. Separate opt-in `/proposals/paper` atomically reserves virtual orders in the shared ledger; durable order IDs prevent duplicate execution. Bodies are capped at 64 KiB. Screening receipts are bounded at 10,000. |
| Multiple accounts | Distinct endpoint/state-directory registry, observation/session binding, read/research roles and indicative fund NAV | Registry does not create accounts or transfer capital. Each executor needs an independently configured durable ledger and token. Unknown/stale prices produce unknown NAV. |
| Politics/sports | Public tag/keyset discovery preserves CLOB/position IDs and reports partial universes; category-independent binary proposal contracts | External PAPER mode optionally discovers politics/sports through canonical Gamma event metadata, validates V2 token/fee/risk identity and subscribes to public CLOB books. Partial discovery is explicit; no strategy profitability is established. |
| Multi-outcome/negative risk | Explicit basket/conversion scenarios plus atomic virtual terminal settlement for complete standard negative-risk groups | 2–16 known binary members, verified terminal evidence and exactly one YES winner required. Augmented, incomplete or fractional groups defer. No chain conversion or venue settlement is implemented. |
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
SDK version 0.3.0 is source-installable and has no runtime dependencies beyond Python 3.10+.
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

## Opt-in shared PAPER execution

The default research launcher preserves shadow behavior. Use a **separate durable account** for
external strategies; switching an existing session between baseline and external modes is refused.
The new launcher supplies isolated default state/recording directories. It requires a clean commit,
a fresh verified Maven build and the same strong `POLYBOT_EXECUTOR_TOKEN` environment variable.
Do not run two processes against one account path.

```bash
# Optional broader discovery, bounded to canonical politics/sports events:
export PAPER_PHASE3_DISCOVERY_TAGS=politics,sports
./scripts/start-phase3-paper.sh
# Another terminal, with the same token:
python3 -m research.phase3 execute-paper --url http://127.0.0.1:8080 \
  --strategy inventory-mm-shadow --seconds 60 --output research/output/paper-execution-001
python3 -m research.phase3 reconcile-paper research/output/paper-execution-001 \
  --url http://127.0.0.1:8080 --output research/output/reconciliation-001.json
python3 -m research.phase3 build-labels research/data/phase3-paper/RUN_ID/events.jsonl \
  --output research/output/paper-labels-001
```

`PaperClient` remains GET-only. `PaperExecutionClient` adds only the fixed internal PAPER routes.
Snapshot `paperExecutionEnabled=true` advertises virtual execution; `executionEnabled=false` and
`liveAllowed=false` still prohibit venue execution. Baseline automatic entry is disabled in this mode;
matching, account reservations, merge fees, expiry, markouts, exits and risk controls use the existing
engine. An accepted proposal is not a fill or a profitability estimate.

`POST /api/research/v1/proposals/paper` uses the same proposal schema as screening. A registered
observation must be no more than 250 ms old, and every leg is revalidated against current books,
metadata, ownership and risk limits. A refresh cannot extend the original observation's lifetime.
Worst-case independent leg fills, including existing reservations, must stay within the configured
unhedged share cap; a low price cannot bypass it. Every leg reserves in one durable ledger commit
before any order is activated. Owned sells cannot
finance unfilled buys. Duplicate token/side legs and self-crossing prices fail. The engine retains its
activation/cancellation latency, conservative queue model and trade-print matching. Orders request
automatic cancellation after 5 seconds; cancellation latency still applies. Missing/stale books or a
disconnect trigger existing cancellation/risk handling rather than assumed fills.

The client writes and fsyncs the exact request and SHA-256 **before** POST. A lost response retries
the identical ID and payload; `reconcile-paper` recovers unknown outcomes from that durable outbox.
Accepted IDs are bound to payload hashes in durable ledger order history, surviving restarts and
fills/cancellations. Different content under that ID rejects. On restart, unknown queue positions are
cancelled and holdings/cash persist. Restart does not reconstruct an unknowable venue queue.

Public recordings include issued observations, external intents, accepted group membership, causal
order features and measured 1/5/30-second markouts. `build-labels` requires a clean journal and
censors gaps, early cancellation and missing horizons; it never derives fills from price touches.
Queue-ahead is a configured displayed-depth proxy, not observed venue FIFO rank. Missing features
remain unavailable. Second-leg completion requires every explicit group member to fill. Training
purges temporally and across connected markets sharing an atomic intent; insufficient labels produce
no trained model. PAPER labels remain distinct from venue evidence.

For reproducible execution audits:

```bash
java -Dloader.main=com.polybot.hft.executor.replay.ClosedLoopMain \
  -cp executor-service/target/executor-service-0.0.1-SNAPSHOT.jar \
  org.springframework.boot.loader.launch.PropertiesLauncher \
  research/data/phase3-paper/RUN_ID/events.jsonl research/output/execution-replay-001 \
  research/phase2/research-config.json --external-paper
# Use a different output directory and add --raw for raw-WebSocket parity.
```

The audit restores the journal's captured initial **virtual** account/checkpoint, including prior
holdings after recovery. It replays recorded external intents rather than rerunning Python decisions;
`strategyIndependentDataset=false`, a starting-account hash and `NO_GO` make that boundary explicit.
A changed configuration over a recovered account is rejected. Independent strategy qualification
still requires a new prospective experiment. CI compares complete raw/normalized reports and action
audits, not only final cash.

For standard negative-risk groups, per-market terminal evidence is retained until the complete
canonical event can be verified. `settle-paper-group EVENT_ID` asks the executor to fetch official
Gamma metadata; it never accepts caller-supplied payout vectors. Payouts, membership proof and all
holdings redeem in one idempotent ledger operation with one configured redemption cost. Incomplete,
changed, augmented or ambiguous universes defer. This is terminal PAPER accounting, not a Polygon
transaction, token conversion, approval, capital transfer or LIVE deployment.

## What prevents full acceptance

1. Seven independently recorded complete heldout days and registered resolved/fill samples are still
   absent. Existing `research/phase2/acceptance.json` is unchanged; all new code needs a new freeze.
2. Venue-calibrated fill/second-leg/markout labels, untouched evaluation and a demonstrated net edge
   are absent. No model is promoted and no reward income is assumed.
3. Broader-market PAPER adapters and virtual group settlement have accounting/contract tests;
   sustained public execution/fill coverage is still required. Chain conversion and venue settlement
   remain outside this implementation; PAPER receipts cannot qualify them.
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

## Execution replay regressions

Public admission recording `17ebbc54aadee6eb16501cab5e8c6a908cab6131` (run `39021614053`,
artifact `12096494914`) exposed two collector/replay differences: stale historical trade notifications
were creating replay-only gaps, and token-specific stale snapshots were clearing unrelated replay
depth. The decoder now follows the streaming policy: stale trades are dropped, missing snapshots
remain unavailable, and source watermarks cannot be replaced by older snapshots. Future source
timestamps are refused in both paths. Malformed full-snapshot frames discard all partial frame
outputs. Contract tests compare streaming and replay decoders directly. Replaying that captured
public tape now matches every report field except input format and every ordered action value;
see `research/phase3/validation/local-validation.json` for its tape hash. This is an external-intent
execution audit with zero observed fills, not independent strategy qualification.

Volatility EWMA values use 18 decimal places to prevent precision growth on sustained updates.
Markout telemetry identifies each partial fill separately; simultaneous fills are weighted by actual
quantity. Missing markout quantity censors the label instead of creating an optimistic sample.
