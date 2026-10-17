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
