# Khaledpoly — PAPER Research Candidate v0.6.0

**Status: ENGINEERING VERIFIED / MARKET QUALIFICATION NO_GO / LIVE DISABLED.**
Khaledpoly is a Polymarket research and virtual-execution system. The current
release candidate uses **PAPER-only** accounts and read-only public exchange
data. Successful CI and short public-data integration tests do **not** prove
profitability, real maker fills, execution quality or permission for funded
orders. The seven full UTC-day prospective market capture has **not run**.

## The one maintained version

| Component | Version / source of truth |
| --- | --- |
| Khaledpoly Java / Maven modules | **0.6.0**, root `pom.xml` |
| Installable Python research extensions | **0.6.0**, root `pyproject.toml` |
| Canonical repository branch | `main` after promotion of the verified candidate |
| Build and acceptance checks | One workflow: `.github/workflows/verify.yml` |
| Runtime operation | **PAPER only**; real-money gate `NO_GO` |

The original internal Java package identifiers (`com.polybot`) and artifact
names remain unchanged for compatibility; they do **not** designate additional
application versions. Historical research documents and fixtures remain for
reproducibility, rather than representing separate supported releases.

## What's included

- Java 21 public Polymarket market discovery, WebSocket market-book capture,
  durable PAPER account ledger, atomic virtual reservations, settlement/replay
  research, idempotent receipt reconciliation, and bounded strategy screening.
- Versioned declarative Python SDK; Politics/Sports scenario hypotheses and
  CEX research signals. Missing source verification or ambiguous multi-outcome
  membership blocks trading hypotheses rather than inventing an edge.
- Independent Binance/Bybit public-data recorder, Polymarket CLOB recorder,
  replay and prospective capture supervisor.
- Offline fill and second-leg **PAPER_MODEL** diagnostics, joint-scenario
  portfolio research, portfolio/fee stress and purged walk-forward reports.
- Tests for concurrent reservations, duplicate fills, cash/inventory/fee
  conservation, restart recovery, strategy permissions and read-only data
  provenance.

## Build and verify

Prerequisites: **Java 21, Maven, Python 3.10+**. Docker is optional for
analytics; do not configure wallets or real exchange credentials.

```bash
git clone https://github.com/khaledhasneen1993/Khaledpoly.git
cd Khaledpoly
mvn --batch-mode --no-transfer-progress verify
python3 -m unittest discover -s research/phase2/tests -v
python3 -m unittest discover -s research/phase3/tests -v
python3 -m unittest discover -s research/phase4/tests -v
python3 -m unittest discover -s research/phase5/tests -v
python3 -m unittest discover -s research/phase6/tests -v
python3 -m pip install --no-deps .
khaledpoly-paper-sdk --help
```

The executor jar is `executor-service/target/executor-service-0.6.0.jar`.
Do not run the publicly networked PAPER smoke without reviewing source
availability and choosing a throwaway test environment. Its output is
**research data**, not trade performance. GitHub Actions runs this smoke
only on repository workflow pushes.

## PAPER research / replay commands

```bash
python3 -m research.phase6.sdk --help
python3 -m research.phase6.paper_screen_bridge --help
python3 -m research.phase6.virtual_paper_bridge --help
python3 -m research.phase5.cex_signals --help
python3 -m research.phase5.walk_forward --help
python3 -m research.phase4.final_gate --help
```

The virtual PAPER order bridge requires its own explicit
`--enable-virtual-paper-only` flag and a valid PAPER executor snapshot.
No untrusted external Python module is imported or run inside the bot.
Java's `AccountLedger` stays the only authoritative virtual cash ledger.

The existing ancillary analytics/ingestor/monitoring modules are optional
engineering components, **not** additional supported product versions.

## Next external validation (NOT completed)

Run the public-source supervisor on a **durable always-on external host**
only after verifying public market access, time sync and disk capacity.
See [capture instructions](docs/CAPTURE_SUPERVISOR.md) and the strict
[release/market evidence distinction](docs/SOFTWARE_RELEASE_GATE.md).
Seven consecutive complete UTC days, genuine venue fill/queue evidence,
independent Polymarket terminal resolution and a frozen holdout study are
all still required for any market qualification.

## Documentation and license

[Current verification gate](docs/SOFTWARE_RELEASE_GATE.md) ·
[Phase-6 engineering detail](docs/PHASE6.md) ·
[Research sources](research/README.md) ·
[Contributor requirements](CONTRIBUTING.md).

MIT license — [LICENSE](LICENSE). No profitability warranty or
authorization for real-money trading.
