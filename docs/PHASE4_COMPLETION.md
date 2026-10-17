# Phase 4 — evidence-backed completion matrix

This document is an engineering status inventory, not a claim that Phase 4
has passed its market-data acceptance gate. The PR remains a draft.

## Implemented, regression-tested
- Public spot data source polling with bounded IDs, equal-millisecond
  trade identity, persistent per-venue watermark, retry and cooldown state.
- Sealed, restartable capture segments; pinned Git commit and frozen config;
  recorded receipt clocks and hashed raw/feature tapes.
- Immutable-segment verification, missing/rotated/changed data and
  overlapping-session detection, seven **complete UTC** days rather than
  seven rolling days; per-venue successful sample and trade-clock freshness.
- Public read-only category/event market-identity and bounded book
  diagnostics that preserve V1 CLOB token IDs vs V2 position IDs.
- Independent joint capture gate requiring seven *overlapping* full UTC days
  of CEX and Polymarket recorded frame-atomic market data.
- CI including Java, phase2, phase3, phase4 Python regression suites,
  PUBLIC integration smoke, source accessibility and category/book probes.

## Observed external facts (not assumptions)
- First short GitHub runner public access check: Binance sampled 100 trades,
  Bybit returned HTTP 403, Polymarket CLOB time available, bounded Politics
  and Sports discovery pages available.
- [Original source probe run](https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39024931161),
  artifact 12098162398, source revision 9f54e5c4.
- Archived raw source checks remain short and are **not** market
  continuous data coverage, real order fills, or evidence of net edge.

## Requirements still preventing full phase-four acceptance
1. A **persistent independent host** must run the frozen code and capture
   at least seven full UTC days while retaining honest source outages.
   Chat sessions and ordinary short-lived GitHub Actions jobs cannot
   provide the continuous process.
2. Verify *actual* Bybit data access on that chosen host or document its
   absence. An HTTP 403 is not success and does not authorize a substituted
   source or fictitious trade data.
3. Collect overlapping Polymarket frame-atomic CLOB books/trades, original
   source/receipt clocks, market identifiers, metadata/fee evidence, disconnect
   and stale-source events. Audit raw/normalized replay and every gap.
4. Obtain independent complete market-universe and official terminal
   settlement/oracle evidence for Politics, Sports and negative-risk groups.
   Page samples, partial tags, and group PAPER settlements cannot certify it.
5. Run the independent full gate across original recordings, archive an
   external digest and freeze evidence/holdout boundaries; reject tampered,
   changed, partial or unreachable sources.

## Truthful acceptance state

| Gate | Present state |
| --- | --- |
| Code and reproducible test scaffolding | Implemented; CI links attached to PR |
| Binance sample reachability | Observed in short CI probe only |
| Bybit sample reachability | BLOCKED_HTTP_403 in first CI probe |
| Gamma Politics/Sports page identity | Bounded samples only |
| V2 CLOB book identity and fee verification | Not independently qualified |
| Continuous seven full UTC days of dual-source data | NOT_COLLECTED |
| Polygon/terminal independent evidence | NOT_QUALIFIED |
| Independent venue fill/second-leg labels | NOT_COLLECTED |
| Phase-4 data acceptance | **NO_GO** |
| LIVE or funded trading | **DISABLED** |

The CLI tools live under `research/phase4/`; see
[PHASE4.md](PHASE4.md) for session and audit commands.
No change to trading permissions, wallets, signing or live order routing
is authorized by this branch.
