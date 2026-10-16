# Phase-one validation — 2026-10-16

## Verified locally

- Java 21 (Amazon Corretto 21.0.12.1), Maven 3.9.9, Spring Boot 3.5.16.
- All seven Maven reactor modules built successfully with `mvn verify`.
- 36 tests, zero failures, zero errors, zero skipped tests.
- Executor and strategy packaged applications both reached health UP in an isolated startup smoke test.
- PAPER available cash and total equity both reported 500; strategy disabled, no market connection or real orders in that smoke test.
- Authenticated account HTTP integration test verifies unauthorized access is rejected and correct available cash is returned.
- Source API checks used public Gamma metadata and the published OpenAPI specifications; no private account was used.
- Shell startup/shutdown scripts pass `bash -n`; `git diff --check` passes.

## Regression coverage

| Test suite | Tests | Failures | Errors | Skipped |
|---|---:|---:|---:|---:|
| com.polybot.analytics.AnalyticsServiceApplicationTests | 1 | 0 | 0 | 0 |
| com.polybot.hft.ExecutorServiceApplicationTests | 1 | 0 | 0 | 0 |
| com.polybot.hft.PaperAccountIntegrationTest | 1 | 0 | 0 | 0 |
| com.polybot.hft.executor.order.UserChannelServiceTest | 1 | 0 | 0 | 0 |
| com.polybot.hft.executor.settlement.PositionCallPlannerTest | 2 | 0 | 0 | 0 |
| com.polybot.hft.config.HftPropertiesBindingTest | 1 | 0 | 0 | 0 |
| com.polybot.hft.polymarket.crypto.ClobAuthEip712SignatureTests | 1 | 0 | 0 | 0 |
| com.polybot.hft.polymarket.crypto.OrderEip712SignatureTests | 1 | 0 | 0 | 0 |
| com.polybot.hft.polymarket.crypto.PolyHmacSignerTests | 1 | 0 | 0 | 0 |
| com.polybot.hft.polymarket.crypto.V2OrderTest | 3 | 0 | 0 | 0 |
| com.polybot.hft.polymarket.discovery.DataContractsTest | 2 | 0 | 0 | 0 |
| com.polybot.hft.polymarket.discovery.LocalOrderBookTest | 1 | 0 | 0 | 0 |
| com.polybot.hft.polymarket.discovery.MarketConstraintsTest | 1 | 0 | 0 | 0 |
| com.polybot.hft.polymarket.discovery.PolymarketMarketParserTest | 1 | 0 | 0 | 0 |
| com.polybot.hft.polymarket.discovery.PolymarketMarketParserTests | 3 | 0 | 0 | 0 |
| com.polybot.hft.polymarket.discovery.WebSocketFreshnessTest | 2 | 0 | 0 | 0 |
| com.polybot.hft.risk.AccountLedgerTest | 8 | 0 | 0 | 0 |
| com.polybot.hft.state.AtomicJsonStateTest | 1 | 0 | 0 | 0 |
| com.polybot.hft.polymarket.strategy.service.OrderManagerTest | 4 | 0 | 0 | 0 |

Coverage includes partial-fill ownership, failed cancellation, submission timeout deduplication,
orphan paper-order reconciliation, terminal-order recovery, cash reservation, overselling,
fee-inclusive basis, realized PnL, daily-loss latching, disk-write failure latching,
single-writer state, corruption rejection, stale/out-of-order market data, level deletion,
market constraints, Data API envelopes, outcome identifiers, user-channel event routing,
CTF/V2 position call planning and an independent typed-data signature recovery check.

## Not verified / rollout gates

- Real BUY/SELL orders, production account balances/fees and authenticated production user streams.
- Deposit-wallet signing wrappers and end-to-end production approvals, wrapping and settlement.
- Full Docker/ClickHouse/Redpanda/Grafana integration: Docker is unavailable in the execution environment.
- Profitability, queue/depth replay and realistic maker fills: phase two; fills remain disabled by default.

LIVE startup and settlement broadcast remain locked. This validation establishes the PAPER
foundation, not complete production readiness or a profitable strategy. Detailed rollout limits
and operator recovery instructions are in PHASE1.md.
