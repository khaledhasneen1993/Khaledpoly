# Prospective CEX and Polymarket read-only collection supervisor

**Code is prepared; the seven-day experiment has NOT been run.**
A stable Linux host running continuously with sufficient persistent
storage remains necessary before external market acceptance is possible.
GitHub Actions and Termux short sessions cannot replace a full audited
prospective seven-UTC-day tape.

Before running:

- Install Java 21+, Maven, Python 3.11+, `timeout` and use a clean
  committed Git checkout. Build/tests run when the Java public collector
  launches, to preserve code identity.
- Choose a **new, empty, durable directory outside the Git checkout**
  (e.g. `/srv/khaledpoly/capture-2026-xx`). Do not store keys or
  wallet secrets. Only public API data will be sampled.
- Verify the host has reliable time sync, sufficient capacity, public
  connectivity to Binance/Bybit and Polymarket, and the expected
  exchange/oracle endpoint terms.

    python3 -m research.phase4.capture_supervisor \
      --root /srv/khaledpoly/capture-NEW \
      --symbol BTCUSDT --days 7 --interval 5 --segment-seconds 900

This launches the existing strictly PAPER, **executor disabled** Java
public Polymarket collector and the independent CEX REST segment
recorder, under one supervisor. It writes a frozen source-revision
manifest and separate `polymarket/` and `cex/` subtrees. It stops its
other child if one exits. An interrupted run receives **NO_GO**, never
automatically repairs missing trades or fills gaps with synthetic data.

Java source flags are frozen by
`scripts/collect-paper-data.sh`:
`--hft.mode=PAPER --executor.sim.enabled=false
--hft.events.enabled=false --hft.strategy.gabagool.enabled=false
--hft.polymarket.market-ws-enabled=true --paper.market-data.enabled=true`.
No funded API or private key is used by this supervisor.

**After** observation, audit the actual CEX segment directories and
find only the real Java `events.jsonl` files in each dated run before
using `research.phase4.final_gate`. Do not pass an invented,
concatenated, duplicated or copied journal. Java service crash,
Polymarket WebSocket gaps, 403 source failures, and missing terminal
evidence invalidate qualification. A clean supervisor exit is not
a market acceptance statement.

The software release manifest, snapshot validation, venue fill labels,
settlement/oracle proofs and later prospectively registered strategy
holdouts must still pass their own gates. Even 7 full UTC days of
uninterrupted REST sampling alone is not a complete trade tape.
