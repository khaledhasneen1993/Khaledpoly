# Phase 6 — central risk and account integration (engineering started)

This stage begins on top of the Phase-5 PAPER-only research branch. It
does not merge previous draft PRs, create wallets, handle credentials,
transfer funds, or enable funded orders.

## Initial multi-account risk integration

\`research.phase6.cross_account_gate.CrossAccountPaperGate\` reuses the
existing proven \`AccountRegistry\` and existing Java \`AccountLedger\`
as the sole durable account-reservation authority. It **never**
creates a second money ledger or writes into the Java state.

The gate inspects all *previously accepted* research snapshots,
requiring complete account presence, matching permission/policy
aliases and fresh independent valuation. It aggregates worst-case
book basis and pending BUY reservations across accounts into
per-account, global and correlated-settlement exposure. It
denies proposal study when any account is missing or stale, a
permission is absent, or limits are exceeded. Ambiguous held tokens
are conservatively grouped as unknown and block admission.

A successful screening result may *only* inform further PAPER
research. This API has no submit, sign, reserve or transfer method.

## Pending Phase 6

- Integrate strategy proposals with the existing central Java risk
  engine and transactional PAPER reservation path.
- Build a versioned restricted external Python strategy protocol,
  repeatable dry runs and untrusted-provider fail-closed tests.
- Benchmark read/poll/replay latency before changing transports;
  no unmeasured gRPC/Rust/C++ work.
- Add Polygon cost/settlement what-if accounting; chain execution
  remains disabled pending separate permissions/security validation.
- Stress test crash, restart, idempotency, per-account session
  reconciliation, simultaneous proposal groups and fee accounting.
- Complete staged CI and final go/no-go gate, then run the
  previously deferred external seven-day source capture.

**All stage-6 engineering is provisional. No account, settlement,
risk model, or strategy may trade real money from this branch.**


## Version 1 restricted external-strategy interface

\`research.phase6.external_strategy.ExternalStrategyReview\` accepts a
strict, versioned JSON envelope bound to one validated PAPER
\`sessionId/accountId/snapshotSequence/generatedMs\`. A proposed
\`edge\` is an unverified model claim, not an edge declaration that
can bypass the existing \`polybot_sdk.advanced.allocate\` central
paper risk/cash/inventory restrictions.

The external strategy **does not execute code** inside this process;
there is no dynamic import, network call, secret field, private key,
wallet or transfer mechanism. Undeclared fields, malformed order legs,
cross-account identities, unsafe/taker prices and conflicting identical
snapshot retries are rejected. Exactly identical retries produce an
idempotent read-only research receipt. Even admitted candidates do not
enter the Java ledger or trigger PAPER orders automatically, much less
real-money orders.

Further integration requires explicit PAPER executor acceptance,
durable idempotent receipt accounting, sandboxed third-party
code execution and independent interface security validation.


## Polygon batch cost vs settlement-delay scenarios

\`research.phase6.polygon_costs.compare_batching\` builds on the
Phase-3 \`gas_scenario\` concept. It compares explicit fixed gas
overhead, per-item gas, native USD, and operator-supplied batch waits
against waiting/settlement exposure costs, without requiring RPC,
wallet keys, signatures, fund transfers or on-chain operations.

A least-assumed-cost batch is a **scenario** and is not an
execution-ready batch selector. The gas estimates, risk of missed
redemption windows, Polygon base fee, gas token price and finality
need real-chain validation before production; all decisions remain
NO_GO.


## Durable Java PAPER SCREEN integration (not order submission)

The new \`research.phase6.paper_screen_bridge\` connects the versioned
restricted strategy envelope to the **existing Java
\`ResearchProposalInbox\`** via \`/api/research/v1/proposals/screen\`
only. The executor's original Java account ledger remains the sole
durable reservation authority; this endpoint *screens research
candidates*, it never calls \`/paper\`, \`/settle-paper-group\` or any
venue order routing. Every strategy candidate ID is deterministically
derived from \`(session, account, sequence, strategy, candidate)\` and
its exact JSON is persisted and fsynced **before** HTTP.

On lost HTTP responses the bridge refuses to invent a new ID or
automatically resubmit any POST. Restart queries only the new
authenticated \`GET /api/research/v1/proposals/screen-receipts/{id}\`
endpoint, which reads the Java inbox's persisted screening receipt
after sequence advancement, restricted to the same PAPER session and
account. A 404 remains explicitly UNKNOWN and needs reconciliation
rather than being counted as accepted. Conflicting requests, snapshots,
and journal rows fail closed. These are **not** durable venue order
receipts and do not make actual reservations; separate integration
with the Java PAPER execution ledger is still required.


### Operator invocation (PAPER SCREEN only)

Read-only receipts use the same authenticated executor token as the
existing research client. The token is passed via a local environment
variable, **never** CLI arguments, files, output logs or PR commits.
The externally generated envelope must be bound to the identical
recent validated snapshot.

    python3 -m research.phase6.paper_screen_bridge \
      --origin http://127.0.0.1:8080 \
      --snapshot ./recent-paper-snapshot.json \
      --envelope ./external-strategy-envelope.json \
      --outbox ./output/phase6-screen-001

First run may POST ONLY to Java \`/screen\`; restarting with that
exact archived snapshot and outbox performs **GET-only** reconciliation,
including when the original snapshot is now stale. Starting a fresh
outbox from a stale snapshot remains forbidden. The token and
execution permissions are never expanded to an exchange/wallet.


## Explicit, separate VIRTUAL PAPER execution adapter

\`research.phase6.virtual_paper_bridge\` is **NOT** the passive screening
bridge. It is the next stage and must be activated explicitly by
\`--enable-virtual-paper-only\`, with
\`snapshot.paperExecutionEnabled == true\` from the Java executor
and its separate \`paper.external-execution\` guard in PAPER mode.
It uses the existing \`PaperExecutionClient.retry_identical\` and
\`ResearchSession\`/Java \`AccountLedger.reserveBatch\` for **virtual**
reservations, rather than creating a second Python cash ledger.
No exchange APIs, signing, wallets, LIVE orders, or fund transfers.

Exactly one immutable request with deterministic ID and an fsynced
local journal is recorded before each virtual POST. After a lost
response, the adapter replays **identical** bytes/ID, and the Java
ledger is responsible for \`PAPER_ALREADY_RECORDED\` deduplication.
It does not treat a lost reply as success. A different
session/account or changed strategy fingerprint is blocked.

    python3 -m research.phase6.virtual_paper_bridge \
      --origin http://127.0.0.1:8080 \
      --snapshot ./recent-paper-snapshot.json \
      --envelope ./external-strategy-envelope.json \
      --outbox ./output/explicit-virtual-paper-001 \
      --enable-virtual-paper-only

Never activate in the absence of confirmed PAPER executor mode. All
settlement/fill labels remain hypothetical and actual user trading
permissions remain disabled.


## Change: one atomic virtual proposal group per executor snapshot

The explicit virtual PAPER adapter rejects more than one independent
admitted proposal group for a frozen account/sequence, **before**
creating the outbox or calling Java. A single group may still contain
multiple validated buy/sell legs reserved together by the Java
\`AccountLedger.reserveBatch\`. Sending a second separate group from
the same stale cash/holdings snapshot is forbidden: collect a fresh
\`ResearchSnapshot\`, re-evaluate the centralized budget, and use a new
generation/outbox. This deliberately trades throughput for correct,
atomic account reservation and prevents cross-strategy overspend.


## Java ledger concurrency, reconciliation and measured latency baseline

JUnit regression tests now exercise the original durable Java
\`AccountLedger\`, not a substituted Python cash ledger:

- 32 simultaneous two-leg reservation attempts share a gross-risk cap;
  only complete atomic batches may succeed. The surviving reservations
  and cash remain identical after process restart.
- 24 duplicate fill notifications share one execution ID; fees, share
  basis and cash are applied **once**, including after restart.
- 20 independent fully recorded buy/sell roundtrips reopen the durable
  ledger between buys and sells, verifying cash, fees, realized basis
  and 40 execution IDs against separate explicit arithmetic. Their
  artificial positive PnL is a **fixture value, not a real result**.
- A separate 12-roundtrip baseline measures reserve/fill/reopen P50
  and P95 monotonic-clock microsecond latency of the real persisted
  state writer. The output starts with
  \`PHASE6_PAPER_LEDGER_BASELINE\` in CI test logs. The runner and
  filesystem change between jobs, so this **is not** a production
  latency guarantee or a hard SLO. No gRPC/Rust/C++ redesign is justified
  until end-to-end network/strategy/execution timing is measured.

The Python tests also check a **single atomic two-leg virtual intent**
and the exclusive process lock on its durable outbox. Independent
virtual intents sharing one stale snapshot are rejected before any
remote PAPER request. These tests do not create actual venue fills.


## Registry-bound global risk integration hardening

A Phase-6 \`ExternalStrategyReview\` caller can no longer supply a
dict containing forged \`mayStudyPaperProposals=true\` flags. It must
provide an in-process \`CrossAccountPaperGate\` instance backed by
the accepted, isolated \`AccountRegistry\`. Each review **recalculates**
fresh/stale account balances, permissions, per-account/global and
correlated-group caps, and matches the exact SHA-256 of the candidate
PAPER snapshot to exactly one registry-held snapshot.

This is a risk/admission *defense in depth* in addition to Java's
single-writer ledger limits. If no independent registry gate has
been configured, the existing single-account Java risk allocator
remains authoritative. External untrusted JSON cannot directly
assert global permission. Neither path enables LIVE.


## Stage-6 real-public CI smoke evidence reconciliation

\`research.phase6.public_smoke_gate\` runs on **phase-six branch pushes**
after the bounded read-only Polymarket/CEX and *separate* virtual PAPER
smokes, Phase-5 source-isolated CEX signals, and forward-public-print
labels. It strictly reads their own independent JSON artifacts, verifies
PAPER-vs-read-only mode separation, Phase-4 tape integrity checks,
replay/action-audit parity, candidate qualification flags and exact
SHA-256 file digests. A missing, forged or swapped report fails CI.
Partial public source access (including Bybit 403) remains possible
and is recorded as a qualification blocker rather than fabricated.
All good artifacts still say \`NO_GO\` and \`liveAllowed=false\`.

The software-only release inventory runs **after** this reconciliation.
Neither a positive synthetic backtest nor passing CI can replace the
prospective seven-full-UTC-day and genuine terminal/venue-label evidence.
