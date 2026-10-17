# Phase 4 — Source integrity checkpoint (work in progress)

This branch starts phase four from phase three without changing main, the frozen
phase-two evaluation, trading strategy decisions, wallets or live permissions.

## Change 1: public trade ID integrity

Before this change the public collector kept only trades with source timestamps
strictly greater than the previous highest millisecond, dropping **new trade IDs
that share the same millisecond**. The bounded per-venue watermark now:

- accepts distinct IDs at the last recorded millisecond exactly once;
- drops older observations and duplicates at the high-water mark;
- rejects oversized same-millisecond identity sets instead of silently emitting
  duplicates; applies only after strict normalized payload validation;
- reports sampled polls, HTTP/network errors, backoff, per-venue feature rows,
  older observations and duplicates, and whether an HTTP 403 blocked access.

A 403 is **not** treated as a valid Bybit sample. No proxying, IP circumvention
or invented alternative is used. Public REST trade sampling is never asserted
to be a complete venue tape. Source gaps remain unknown, not filled.

## Validation

Run:

    python3 -m unittest discover -s research/phase4/tests -v
    python3 -m unittest discover -s research/phase3/tests -v

The existing GitHub Actions workflow must run these alongside the Java and
phase-two suites. Recorded CI evidence is distinct from the local tests.

## Remaining phase-four acceptance requirements

1. Validate current Polymarket Gamma/CLOB, Binance and Bybit availability
   from the **actual chosen recording host**, documenting blocked sources
   rather than silently substituting one.
2. Build/resume bounded, append-only session archives with recorded server
   and receipt clocks, committed source/config revisions and sequence/gap
   evidence; detect rotation, truncation and incomplete sessions.
3. Freeze a forward-looking capture and acceptance manifest, then collect at
   least seven complete independent UTC days on an always-on host.
4. Validate Politics/Sports and multi-outcome discovery/terminal identity,
   publisher disconnect/reconnect behavior, depth, fees, settlement evidence
   and raw-vs-normalized causal replay.
5. Demonstrate coverage and reconcile public data against recordings.
   **Do not** interpret absent observations as zero activity or create
   fills from touches.
6. Deliver a gate report separating data collection uptime, source-specific
   outages, independent labels and market qualification. Nothing unlocks LIVE.

Engineering checks here do not qualify fills, profit models or a strategy.
