# Phase 2 — implementation and acceptance

The shared closed-loop PAPER strategy, causal ingestor replay, inventory exits, verified public
resolution ingestion, execution reporting, alert outbox/adapters, and frozen heldout evaluator are
implemented. **Empirical acceptance is still NO_GO; phase 3 shadow engineering has started ([scope](PHASE3.md)); empirical promotion remains blocked.**

See [PHASE2_COMPLETION.md](PHASE2_COMPLETION.md) for current behavior, operating commands, limits,
provenance rules and the remaining data requirement. [PHASE2_VALIDATION.md](PHASE2_VALIDATION.md)
records the first delivery; [PHASE2_FINAL_VALIDATION.md](PHASE2_FINAL_VALIDATION.md) records this
completion work and the observed public-access failure.

- `./scripts/start-paper-research.sh`: fresh verified build, executor only, shared closed-loop engine,
  committed research configuration, PAPER, public metadata recording, legacy strategy disabled.
- `./scripts/collect-paper-data.sh`: strategy-independent public data only, no simulated account.
- `./scripts/closed-loop-replay.sh`: generate decisions and execution from public observations using
  the same strategy class as streaming PAPER. Accepts `--stress`, `--raw`, and `--freeze FILE`.
- `./scripts/replay.sh`: retain first-delivery action replay for execution/accounting regression;
  it cannot qualify as a strategy performance experiment.
- Dashboard: `http://127.0.0.1:8080/paper.html`. APIs require the existing executor token if set.
- Default research capital: 500 virtual collateral units; five shares per initial leg, bounded by
  displayed depth and current minimum size. Configuration is in `research/phase2/research-config.json`.
- 5-minute discovery stays opt-in. No oracle result is inferred from expiry, BTC candles or prices.
- The accepted source for residual payouts is the official condition-grain terminal resolution API;
  proposed results and conflicting payouts reject.
- Local alerts require no external account. Slack/Telegram delivery is disabled until configured.
- Runtime recordings and accounts are ignored by Git. LIVE is locked throughout.

`research/phase2/acceptance.json` is unchanged. A freeze for 2026-10-17 00:00 UTC through
2026-10-24 00:00 UTC is stored in `research/phase2/frozen-experiment.json` (03:00 through 03:00 in
Asia/Amman). It is a frozen candidate window, **not an automatically running seven-day collector**.
The source must be reachable and the collector must actually capture that window; otherwise create
a new future freeze before a later experiment, without tuning on heldout results.

No historical trades or synthetic accounting fixtures are substituted for the required seven complete
UTC days, 100 resolved traded markets, 100 maker fills and the other preregistered checks. The short
public-data smoke is diagnostic only. A passing build or a positive synthetic arithmetic example
cannot qualify a strategy for deployment or unlock LIVE.
