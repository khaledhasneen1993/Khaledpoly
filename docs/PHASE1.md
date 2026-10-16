# Phase 1 — execution and accounting foundation

This release is PAPER-only. It does not establish profitability. No wallet funding,
approval, real order or settlement broadcast is part of the verification workflow.
The original source is preserved in commit 898390b1810e4a64c0d590418af092866356250b.

## Implemented

- Exact terminal statuses: partial fills remain owned and monitored.
- Durable strategy order intents before submission; paper client IDs prevent duplicates.
- Failed/unconfirmed cancellation retains ownership; cancellation races reconcile matched quantity.
- Durable account cash, reservations, holdings, fee-inclusive basis, realized PnL,
  execution deduplication, equity high-water mark and daily-loss/drawdown latch.
- Atomic, fsynced state replacement, private state-file permissions and one writer per state file.
- Cash, order, token exposure, gross exposure and inventory availability checks.
- Mark-to-bid valuation; stale/missing inventory marks suspend entry and cancel resting paper orders.
- Recovery of paper reservations, cumulative filled quantity and held positions.
- Source-age checks, full price-level books, deletion handling, resnapshot after invalid messages,
  fresh-data invalidation on reconnect, PING and bounded connect/close waits.
- Tick-size events, current order size/tick/expiry/acceptance/asset-identity validation.
- Gamma outcome identifiers selected by explicit market version.
- CLOB v2 CTF domain 2 and Protocol V2 domain 3 signing support. Legacy signing is retained only
  for the original compatibility vector; the runtime builder uses current domains.
- Current Polygon contract registry distinguishing trading pUSD, CTF collateral,
  collateral adapters, PositionManager and Router.
- Offline merge/redeem calldata planning for CTF and Protocol V2; malformed IDs rejected.
- Authenticated user-channel adapter with reconnect, private order notifications triggering
  REST reconciliation, and account order-heartbeat support. This is dormant in PAPER mode.
- Data API v2 envelopes/cursors with explicit failure on malformed/repeated cursors.
  Legacy internal field aliases preserve the existing analytics consumers.
- Local executor token authentication, loopback defaults, private monitoring bindings,
  mandatory non-default Grafana password in Compose and hidden health details.
- Unified infrastructure Compose, lightweight startup, readiness checks and verified PID shutdown.
- Java 21 CI, Spring Boot 3.5.16 and regression/integration tests.

## Run

Requirements: Java 21, Maven 3.8+, curl. Full analytics mode also requires Docker
Compose with `include` support (2.20+).

```bash
mvn --batch-mode --no-transfer-progress verify
./start-all-services.sh
./stop-all-services.sh
```

The default launcher starts executor and strategy only, with event publishing disabled.
Use `POLYBOT_LIGHT=false` and export `GRAFANA_ADMIN_PASSWORD` for full infrastructure.
Export `.env` values explicitly; do not commit credentials or local state.
Set the same `POLYBOT_EXECUTOR_TOKEN` for executor and strategy. Non-loopback executor
binding without a token is rejected. A remote deployment also needs transport encryption
and network access controls; the provided deployment binds to loopback.

The account starts with 500 only when `state/paper-account.json` does not exist.
Changing `PAPER_INITIAL_CASH` does not reset an existing account. Limits are absolute
USD: order 25, token exposure 25, gross exposure 250, daily loss 25, drawdown 50.
These are conservative development defaults, not optimized strategy parameters.

Inspect `/api/polymarket/paper-ledger` and `/api/polymarket/bankroll` using
`X-Polybot-Token` when configured. Readiness is exposed at `/actuator/health`.

## Recovery and stop semantics

Keep both `state/paper-account.json` and `state/strategy-orders.json`. Never delete
state while a process is running. A second process cannot own the same state file.
A corrupt/unreadable journal fails startup; it is never silently replaced with seed cash.
Back up the state directory after an orderly shutdown.

A risk breach latches the account halt, cancels resting orders and rejects new entries.
It does not sell inventory blindly. The phase-2 exit policy will compare alternatives.
An unknown submission remains blocked rather than being automatically resent. Reconcile
its client ID against the executor ledger and order endpoint before operator recovery.
No manual reset endpoint is exposed in this phase.

## Deliberate rollout limits

- Fills are disabled by default. The inherited random-fill heuristic is retained only
  as an explicitly enabled legacy lifecycle diagnostic. It must not establish PnL.
  Depth/queue replay, pair completion, Taker fee economics, end-of-market cash settlement
  and profitability gates belong to phase 2.
- LIVE startup and transaction broadcast are locked. Current signing/position planning
  is verified offline, not by spending funds. Deposit-wallet signature wrappers and
  end-to-end production approvals/fills/reconciliation need a separately verified rollout.
- The private stream is fixture-tested, not tested against an authenticated production account.
  REST remains authoritative for order amounts and fees.
- Internal offset-style pagination is an adapter over v2 cursor walks. Separate offset calls
  are not one account-wide atomic snapshot; LIVE stays locked until snapshot parity is verified.
- Full Docker/ClickHouse/Kafka integration must run where Docker is available. Unit/context
  tests use isolated fixtures and do not claim a running analytics stack.
- Full market expansion, portfolio correlation optimization and predictive models are phase 2/3.

## Sources checked on 2026-10-16

- https://docs.polymarket.com/v2-migration
- https://docs.polymarket.com/migrate/polymarket-v2/api-integrations
- https://docs.polymarket.com/resources/contracts
- https://docs.polymarket.com/migrate/data-api-v1-to-v2
- https://data-api.polymarket.com/v2/openapi.json
- https://docs.polymarket.com/api-spec/clob-openapi.yaml
- https://docs.polymarket.com/trading/positions/manage

## Validation

See `docs/PHASE1_VALIDATION.md` for the exact checks and results for the submitted revision.
