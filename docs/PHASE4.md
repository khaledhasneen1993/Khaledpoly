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


## Change 2: immutable session attestation and seven-day window audit

Each new PUBLIC capture stores a wall-clock start, monotonic elapsed time,
end timestamp, polling timestamp on every raw source event, and SHA-256 digests
of raw/feature append-only tapes. Failures preserve a report with complete=false.
An independent audit rejects missing/altered files, invalid feature and venue
accounting, out-of-order polling timestamps, clock drift, overlapping/duplicated
sessions, access-blocked venues and gaps over the configured threshold.

    python3 -m research.phase4.audit --output research/output/capture-audit.json \
      research/output/session-001 research/output/session-002

The seven-day criterion is a *continuous public sampling window* only; even
a clean result is not a complete exchange tape, does not prove fill quality,
and must never unlock models or LIVE. The capture must run on an always-on
host; a GitHub Actions job or this chat does not keep a seven-day process alive.


## Change 3: successful-sample freshness is a separate gate

A service can keep polling during a 403/backoff period without obtaining
usable market data. The archive auditor checks first/last successful samples,
their largest internal and inter-session gaps, and the end-of-session tail,
not just the heartbeat of the polling loop. Different market symbols may not
be mixed into a single qualification window.

The phase-four branch now runs the existing external PUBLIC PAPER/spot
integration smoke in CI and verifies its source archive against the session
integrity audit. It still cannot claim seven-day evidence from a short CI run.

The self-contained file hashes are consistency checks, **not cryptographic
authentication** if someone can edit both the report and the tape. Store
immutable artifacts or external digest attestations before claiming a
tamper-proof dataset.

## Change 4: checkpointable, atomic venue trade-watermarks

PUBLIC REST responses can share an exchange millisecond with distinct trades.
Watermark updates are now all-or-nothing; a malformed or bounded-overflow
response cannot leave a partially advanced state. Every schema-3 segment
includes initial and final per-venue trade-ID checkpoints. The audit rejects
gaps between checkpoints, mixed revisions, and legacy segments without
checkpoint evidence. Checkpoints preserve de-duplication across restarts,
but cannot reconstruct trades that were never returned by the REST source.
