# Atomic market frames and recorded-clock replay — 2026-10-16

## Confirmed diagnosis

The clean 897.503-second capture from run `38961694001` / artifact `12073757536` contains
465,646 raw messages, 907,451 normalized books and 878 public prints. Four venue closes explicitly
report 1013 / `slow consumer: send buffer full`. Several occurred with a nearly empty application
queue and low decoder wait. This evidence does not identify the remaining network/JDK/venue cause.
The bounded receiving change did not eliminate those closes.

The normalized strategy submitted one pair at 20:31:53.192 UTC: buys at 0.65 and 0.32. Decision
processing occurred after row 797322, the first outcome update of raw message 797321, before the
second outcome update at row 797323. The second outcome still had its previous source state.
At activation 250 ms later the first order's 0.65 price met the new 0.65 ask and was correctly
rejected as marketable. The second order was canceled 250 ms later; no public print occurred during
that attempt. No fill may be inferred from these price moves.

Raw replay also generated synthetic periodic ticks, while normalized replay used recorded ticks.
Equal final cash/zero fills did not establish intermediate decision equivalence. These are concrete
causality defects; a larger queue or relaxed edge threshold does not repair them.

## Changes

- A completed WS message produces one `FRAME` with a monotonically increasing `frameId` and ordered
  normalized events. `RAW_MARKET` carries the same ID. ResearchFeed records one `RESEARCH_FRAME`
  at its actual availability, after decoding. A concurrently recorded timer or metadata observation
  can see the preceding complete frame, never half of the new paired update.
- ResearchSession applies all frame observations before executing pending hedges, merging, marking,
  checking portfolio risk or evaluating new entries. Matching still processes observations in their
  original order and uses unchanged activation/cancel latency, queue assumptions and source clocks.
  Invalid frame event types/nesting are rejected; a partial session failure cannot resume trading.
- Legacy `onTape` consumers remain supported and receive individual events after the complete message
  has updated the WS caches. The closed-loop research feed uses the atomic `onFrame` interface.
- Recordings declare `normalized-public-v2`. Both replays use recorded input/timer clocks. Raw replay
  decodes the original message at its linked FRAME availability, not earlier at raw append time.
  Missing, duplicate, unordered or unmatched frame boundaries fail verification, including at end of
  recording. A heldout slice handles raw observations straddling its start/end without inventing data.
- Legacy v1 recordings remain readable, explicitly labeled `legacy-unframed`; their lost frame
  availability cannot be reconstructed exactly. They cannot qualify the corrected experiment. The
  evaluator checks atomic-frame and recorded-clock provenance; financial thresholds are unchanged.
- CI compares every normalized/raw baseline report field except `inputFormat`, plus the complete
  parsed action audit. Matching terminal maps preserve deterministic insertion order across JVMs.
  Stress uses the same observations with its existing conservative assumptions.
- Rejection counts now distinguish `MIN_SIZE`, `NET_EDGE`, both conditions, missing/stale books,
  empty depth and stale metadata. They are evaluation counts, not independent opportunities/trades.

## Connection diagnostics

`WS_HEARTBEAT` records actual ping attempts, completed/failed asynchronous sends, pending sends,
unanswered text pings, received text pongs, maximum attempt gap/send duration, queue state, cumulative
JVM GC count/time and heap use. Disconnect GAP rows preserve that connection's heartbeat and queue
snapshot. Reply counters update at callback receipt without disk IO; timer/close paths record them.
A completed send is not an acknowledged heartbeat. Text PONG has no identifier: once multiple
outstanding pings or failed sends make correlation uncertain, no unambiguous reply delay is claimed.
Probes reset on each connection and old send futures update only their own probe.

These metrics localize the next investigation; cumulative GC time is not a JVM pause trace, callback
receipt is not a wire timestamp, and periodic queue samples are not continuous queue-depth peaks.
No heartbeat schedule, connection endpoint, risk limit, fee assumption or fill rule was relaxed.

## Validation and limits

The regression suite covers a half-updated pair that previously submitted orders, complete-frame
WS delivery with legacy listeners, identical raw/normalized audits with real recorded timer jitter
and raw-to-availability delay, heldout boundary slicing, missing frame rejection, pending/failed
heartbeat sends and ambiguous PONG attribution. Python checks cover nested frame quality, raw/frame
binding and rejection of legacy provenance by the evaluator.

Local verification passed 97 Java tests and eight Python checks. Synthetic fixtures exercise
correctness; their positive PnL is not market evidence.

The next public CI capture is a bounded 300-second diagnostic followed by normalized baseline,
stress and raw baseline. Its actual results are recorded in PR #2 after review. This shorter run
checks the new recording/clock contract and collects heartbeat evidence; it cannot certify uptime,
seven-day acceptance or profitability. Previous four 1013 closes remain an unresolved stability
finding until independently diagnosed. PAPER only; empirical acceptance remains NO_GO.

The implementation freeze is renewed before the future Oct 17–24 UTC candidate window. Freezing
records a candidate; it does not schedule or start a seven-day collector.

A telemetry follow-up separates monotonic callback-silence age from the legacy last-activity clock,
which also advances during decoding. A regression proves decoder activity cannot make ingress appear
fresh. Earlier 4fd0c94 diagnostics labeled that combined clock `lastIngressAgeMs`; interpret that
older field as activity age. New captures retain both explicitly named clocks. Final local suite:
98 Java tests and eight Python checks. After the 300-second frame investigation, routine push
recordings return to 180 seconds; neither is an uptime or acceptance qualification.
