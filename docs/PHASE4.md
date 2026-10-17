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


## Change 5: restartable long-running PUBLIC capture

A Linux host with a **clean committed** checkout may use:

    python3 -m research.phase4.recorder --root research/output/phase4-btc \
      --days 7 --segment-seconds 900 --interval 5

This command is foreground work on the operator's host. ChatGPT/GitHub CI
does **not** run it for seven days. A shorter operator check can supply
\`--max-new-segments 1\`, which deliberately remains NO_GO.

The recorder freezes its symbol, source Git commit, segment length, polling
interval and seven-day target in a single plan. It uses an exclusive OS file
lock; creates sealed numbered segments; validates each segment before using
the terminal per-venue ID checkpoint as the next starting checkpoint;
refuses silently changed parameters, corrupted complete segments or
uncommitted code. The \`latest-audit.json\` is a replaceable status summary;
raw segment files and manifests never get overwritten.

An interrupted segment remains in place by default and **blocks** restart.
An operator can explicitly retry using \`--quarantine-incomplete\`, preserving
that directory under \`interrupted/\` and recording recovery evidence in
\`recovery.jsonl\`. This *never* erases a data gap or qualifies seven days.

Source REST polling still cannot claim every venue trade or an actual FIFO
queue position. Even seven days of uninterrupted REST samples is not the
full Phase-4 market-data acceptance; CLOB, settlement and venue-label
validation remain separate.


## Change 6: independent public-source reachability probe

Each phase-four push includes a one-shot, public, read-only accessibility
probe of Binance/Bybit trade sampling, Polymarket CLOB server time and
the first bounded Gamma event page for Politics and Sports. Any 403,
rate limit, malformed response or unreachable endpoint is recorded
as a per-source result. Results are uploaded as a GitHub Actions artifact:

    python3 -m research.phase4.probe --output research/output/sources-001.json

The probe never uses accounts, wallets, secret tokens, signing, funded
orders or a live position. The probe reports no fills, complete market
universe or continuous coverage, even if every endpoint responds.


## Change 7: complete UTC-day acceptance

The recorder now targets **seven complete UTC calendar days**, not just
seven rolling 24-hour periods that can include partial first/last days.
It starts sampling immediately, but the qualification clock begins at
the next UTC midnight (or the current midnight if exactly aligned).
The audit independently reports \`firstFullUtcDayMs\`, \`fullUtcDays\`
and blocks an insufficient day count. Continued restarts and failures
still preserve NO_GO.


## Change 8: persist source-specific retry/cooldown state across segments

A 403/429/418 cooldown or network backoff must not reset when a fifteen-minute
segment is sealed or the recorder restarts. Schema-4 segments therefore
checkpoint source-specific \`notBeforeMs\` and failure counts in addition to
trade watermarks. The independent audit rejects missing/changed cross-segment
retry states. This avoids hammering a blocked venue after every process
restart. Source access remains an operational limitation, not proof of
complete coverage.


## First source probe — measured access, not strategy results

A real GitHub Actions runner checked five publicly accessible source paths.
[Workflow 39024931161](https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39024931161),
artifact \`12098162398\`, commit \`9f54e5c4\`:

- Binance spot: sampled 100 public trades in a single REST response.
- Bybit spot: HTTP 403 (zero observations).
- Polymarket CLOB time: available.
- Gamma Politics: first bounded page available (three events).
- Gamma Sports: first bounded page available (three events).

The four reachable checks are **not** market coverage or venue fill evidence.
A precise, auditable summary is checked in at
\`research/phase4/validation/first-source-probe.json\`. The underlying
GitHub run/artifact is the primary evidence; the checked-in file does not
override it. Bybit access from the intended long-running host is still
unverified; the CI runner returning 403 cannot be called a successful source.


## Change 9: Polymarket category/event identity and sampled CLOB evidence

The bounded \`research.phase4.market_evidence\` tool reads only PUBLIC
Gamma category tags, bounded event pages and per-event detail, plus an
optional single V1 book and CLOB market-info snapshot. Every retained
binary market must expose a valid condition ID, market identity and
exactly two version-appropriate outcome IDs. V1 CLOB token IDs and V2
position IDs must **never** be treated as equivalent. Invalid/duplicated
markets remain explicit missing evidence, not tradable candidates.
Network and unexpected API schemas become structured errors.

    python3 -m research.phase4.market_evidence --category sports --limit 2 \
      --max-books 2 --output research/output/phase4-sports-001.json

A market-info hash is not validation of fee schedules; a V1 sampled book
is not continuous depth; V2 books are marked adapter-unverified pending
explicit protocol validation. A multi-market event is NOT assumed a complete
negative-risk settlement universe. Neither tag/category nor one-shot
snapshots prove canonical terminal payouts. All output remains \`NO_GO\`,
independent of public endpoint reachability or green tests.


## Change 10: independent CEX/CLOB joint acceptance gate

The \`research.phase4.final_gate\` command re-inspects original sealed CEX
segments and Polymarket raw/normalized CLOB journal tapes, requiring closed
frame-atomic recordings, actual book observations, zero unexplained data
gaps or feed errors, and **at least seven overlapping full UTC days**.
Disjoint seven-day runs can never satisfy this shared gate.

    python3 -m research.phase4.final_gate \
      --cex research/output/CEX/segments/segment-* \
      --polymarket research/data/paper/*/events.jsonl \
      --days 7 --output research/output/phase4-final-gate.json

The tool does not trust self-asserted success in \`latest-audit.json\`;
it re-reads the underlying event tapes. Passing public data continuity,
if achieved on an always-on host, remains **not** venue FIFO execution
evidence, a verified complete negative-risk universe, independent resolution
oracle truth, or strategy profitability. These separate acceptance
requirements remain explicit, and neither LIVE nor a funded account is
enabled.


## Change 11: trade-clock freshness as an independent data gate

HTTP 200 success, or a series of identical REST trade lists, is **not**
proof of fresh observations. The auditor now checks progression of each
venue's highest source trade timestamp independently from poll heartbeats,
with first/last and inter-session freshness gaps. An unchanged/absent
clock cannot satisfy a continuous capture, even if network polling succeeds.
This is still only sampled CEX evidence; it is not complete exchange
trades, observed FIFO, or venue order-fill data.
