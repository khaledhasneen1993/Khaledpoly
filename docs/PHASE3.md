# Phase 3 — PAPER research toolkit

Status: expanded engineering toolkit implemented; full third-phase acceptance is **not complete**.
See [delivery matrix, commands and unresolved requirements](PHASE3_COMPLETION.md).
The preserved phase-two reference is `bf9458a6b236522c95ef52f5e43bc184ada275c1`.
The empirical decision remains **NO_GO**, including after a passing build or an exact shadow replay.
No funded execution, signing, wallets or chain transactions are introduced.

## Implemented contract

An opt-in `GET /api/research/v1/snapshot` returns a detached snapshot under the same
`ResearchSession` lock used by the causal PAPER engine. A WebSocket frame increments the input
sequence once, irrespective of the number of book changes inside it. Session IDs change on restart.
Reading never advances the strategy clock or changes account state. The existing closed-loop engine
continues to own the PAPER account; new Python proposals do not enter that engine.

The snapshot includes cash and reservations, holdings, halt and pending-taker status, verified binary
market metadata and fee parameters, and depth with separate source and availability timestamps.
It exports at most 256 markets and 512 books with 50 levels per side. Truncation is explicit.
The SDK rejects truncated envelopes, and the strategy abstains on truncated depth. Expired markets
with inventory or outstanding orders are retained for risk accounting.

The endpoint is disabled by default. Enabling it requires a nonblank executor token of at least
24 characters; startup fails if it is absent or weak. Requests use the existing `X-Polybot-Token`
filter. Unavailable closed-loop state returns 503, and successful responses use `Cache-Control: no-store`.
POST to the snapshot route is unsupported. A separate [proposal screening route](PHASE3_COMPLETION.md#external-proposal-screen) persists shadow receipts without executing orders. The endpoint itself is read-only, but **the executor token is shared with existing
executor APIs and is not a scoped read-only credential**. Keep it local and only give it to trusted code.
The SDK allows plaintext HTTP only on loopback, requires HTTPS elsewhere, and refuses credentials in
URLs, redirects and responses above 8 MiB. It never logs the token or provides submission methods.

The standard-library Python SDK uses Decimal accounting, rejects duplicate/nonfinite JSON values,
checks reservation reconciliation and causal clocks, and rejects account/session changes or regressions.
Freshness ceilings are 2 seconds for books and 60 seconds for metadata, or the stricter configured values.
Offline inspection/replay uses explicit recorded availability time; online sampling uses the current clock.

The inventory maker produces hypothetical passive quotes only, with downward inventory skew and
owned-inventory sells. It reserves proposal cash across markets; sells do not finance buys in the same
observation. Existing outstanding orders suppress additional quotes for their token. Pending takers,
halted accounts, missing/stale books and stale metadata prevent proposals. Per-order, acquisition-exposure,
and group caps are enforced. Unknown holdings still count toward total exposure.

Default limits: 25 USDC per order and group, 100 USDC total acquisition exposure. An optional JSON
condition-to-group map makes correlated markets share a cap. These are research screening limits,
not a live portfolio optimizer. Proposals do not report expected net profit, rewards, actual fills or VaR.
No maker reward or fee exemption is assumed as an earned return.

## Run

Use Java 21, Maven and Python 3.10+. Commit code/configuration before starting a recording.
Choose a new output directory for each run. Supply an independently generated strong token through
`POLYBOT_EXECUTOR_TOKEN`; do not put credentials in command arguments or committed files.

```bash
./scripts/start-phase3-research.sh
# In another terminal with the same token in its environment:
python3 -m research.phase3 shadow --url http://127.0.0.1:8080 \
  --seconds 60 --interval 1 --output research/output/phase3-shadow-001
python3 -m research.phase3 replay-shadow research/output/phase3-shadow-001 \
  --output research/output/phase3-shadow-001-replay.json
```

An optional `--groups research/my-groups.json` accepts an object such as
`{"condition-one":"crypto-btc","condition-two":"crypto-btc"}`. Use actual condition IDs.
The mapping is fixed and hashed for that run. It is an explicit research assumption, not a measured correlation.

The SDK can also be installed with `python3 -m pip install ./research/phase3` and then invoked as
`polybot-research`. It has no runtime third-party dependencies. Installation may need setuptools
available locally or a package index for the build backend.

`manifest.json`, `observations.jsonl` and `report.json` use private permissions. Every observation is
flushed and fsynced. Configuration, implementation and tape hashes bind replay to the same inputs
and code. Replay rejects partial runs, changed code/configuration, noncausal identities, changed counts,
checksums or proposals. Output files/directories must be new, preventing accidental overwrite.
Network errors cause abstention; authentication/missing endpoint errors terminate the run. Throttling
and server errors impose a conservative 60-second cooldown. An invalid observation aborts with
`complete=false`. A run with no valid observations cannot pass replay.

All reports retain `fills=null`, `netPnl=null`, `decision=NO_GO`, `executionEnabled=false` and
`liveAllowed=false`. An exact match proves deterministic proposal calculation on supplied observations;
it does not prove execution quality, profitability or the safety of an external venue.

## Validation

```bash
mvn --batch-mode --no-transfer-progress verify
python3 -m unittest discover -s research/phase2/tests -v
python3 -m unittest discover -s research/phase3/tests -v
python3 -m research.phase3 inspect executor-service/target/phase3-snapshot.json --replay-clock
```

Maven's real HTTP integration test produces the snapshot consumed by the Python contract test.
That test is required: it fails if Maven has not generated its fixture. CI runs in the same order.
Coverage includes default-off routing, token guards and authorization, atomic-frame generation,
no-store responses, detached reads and POST rejection; SDK coverage includes real HTTP reads,
identity changes, stale/crossed data, cash/short constraints, inventory skew, shared risk budgets,
record/replay parity and tampering. Synthetic inputs qualify software contracts only.

## Delivery and qualification matrix

The original foundation has been extended with public CEX sampling, causal external forecasts,
complete-set candidates, censored fill/second-leg/markout learning, atomic portfolio screening,
joint-history VaR/ES, external proposal receipts, account isolation/NAV, multi-outcome/collateral
scenarios, profiling and public CI smoke. See [PHASE3_COMPLETION.md](PHASE3_COMPLETION.md) for
exact commands and implementation boundaries. Full acceptance remains blocked by explicit missing
market evidence, broader discovery and actual settlement/execution qualification; nothing unlocks LIVE.
