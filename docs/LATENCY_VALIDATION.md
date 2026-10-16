# Research recorder latency investigation — 2026-10-16

## Observed failure

Actual public capture from Actions run `38929277672` lasted 86.291 seconds and contained 77,838 raw
frames, 116,620 normalized books and 112 public trade prints. It reported 1,229 `stale_source`, five
`reconnect` and four `invalid_depth` signals. Full strategy baseline and stress each reported 1,242
invalidations, zero fills and cash 500. Source age at the callback was not independently instrumented;
therefore this recording cannot distinguish network/JDK buffering from application processing.
Repeated age ramps approaching two seconds and resets around reconnects justify examining backpressure.

The old recorder performed `FileChannel.force(false)` after every raw, normalized and application
record, on the same synchronous callback path that must request the next WS message. This creates a
concrete avoidable disk synchronization cost; it does not prove that all observed latency was disk IO.

## Implementation

- Research tape rows remain serialized under one lock with contiguous sequence and actual observation
  times. A 256 KiB buffer groups disk commits, targeting 25 ms or a 256 KiB batch threshold. An idle
  timer also commits pending data. Scheduling and disk stalls can exceed that target; it is not a
  real-time deadline. Large single rows may exceed the byte threshold.
- Closing writes RUN_END, flushes and forces the file before returning. IO failures latch; future
  producers fail and a known failed writer cannot attest a clean end. A crash can lose an uncommitted
  tail; missing clean termination disqualifies the recording. AccountLedger and durable order/alert
  state continue using their existing independently fsynced atomic persistence.
- RAW_MARKET includes `callbackReceivedMs`, captured before append/parse. This is application callback
  receipt, NOT a hardware/wire timestamp; upstream network and JDK queues are included.
- Stale-source diagnostics include source, callback and validation clocks, plus callback source age
  and processing age. Rejection still uses current processing time and the original two-second limit.
  No timestamp is rewritten and no stale book becomes tradable because it arrived earlier.
- WS_PIPELINE aggregates per-second frame counts, maximum callback duration, raw append duration and
  journal commit statistics. Its lock is independent of the connection/reconnect monitor.
- The streaming inspector uses bounded histograms and error examples, checks sequence/run/clock/end
  integrity, breaks down gap reasons and distinguishes already-stale callbacks from a source crossing
  the age limit during processing. Unknown measurements in old recordings remain explicitly unknown.
- The existing push CI captures 180 seconds of public record-only data and performs full strategy
  baseline/stress replay. No account, wallet, signing or live order flow is enabled in that collector.

## Local verification

All seven Maven modules passed verify: 77 Java tests with zero failures/errors/skips. Seven Python
checks passed, including the inspector's measured stage attribution, incomplete capture and clock/end
integrity. New Java regressions cover concurrent causal journal ordering, grouped/idle commits, clean
close/idempotent close, background disk failure and rejection after a simulated three-second recorder
stall. Existing risk, queue, settlement, restart and closed-loop HTTP tests remain passing.

An isolated local benchmark replaying the same first 12,000 captured rows used 105 group commits before
close, versus the old implementation's one force per row. Its observed runtime was 0.681 seconds;
the initial old run was 1.838 seconds. A separate run concurrent with a full build took 39.970 seconds,
so these timings are noisy diagnostic measurements, not a venue latency guarantee or controlled
production performance comparison. Fresh public CI data is required to assess the actual effect.

The acceptance file, fees, queue model, risk limits, strategy thresholds and live lock are unchanged.
This engineering smoke is training/diagnostic data, not the heldout seven-day experiment. The frozen
implementation digest is renewed before the still-future candidate window; freezing does not start
collection. Current acceptance remains NO_GO pending actual independent evidence.

## Completed public verification and recovery follow-up

Run `38932952075` at commit `8c6018d9d5a1b69c10ad4841a4c08bbe51f6cf41` passed all checks.
The 176.218-second clean recording captured 60,808 raw frames, 119,721 books and 51 venue prints.
There were **zero stale-source signals**; maximum callback source age was 717 ms and maximum
normalized book source age 707 ms. Callback-processing maximum was 11.991 ms. The last periodic
journal sample showed 181,855 records / 4,241 commits with no failed writer. Traffic and durations
differ from the previous capture, so this is encouraging observational evidence, not a controlled
causal benchmark or a promise that future feeds cannot lag. Full summary and baseline/stress outputs
are preserved in `research/phase2/validation/latency-public-summary.json` and artifact `12059223402`.
Both full strategy replays completed with cash 500, PnL 0, zero fills and 10 invalidations: six WS
signals (four depth invalidations, two reconnects) plus four HTTP feed errors. Acceptance stays NO_GO.

Inspection of the actual frames found two split updates affecting both outcome tokens: the first
frame produced a locked reconstructed book, the next frame at the same source timestamp explicitly
removed the opposing level, followed immediately by full venue book snapshots. The client correctly
invalidated/canceled at the first frame, but a sticky resnapshot flag forced a redundant reconnect
even after valid full snapshots had restored both assets. Recovery now tracks invalidated assets
individually. Only a fresh, source-monotone, validated full snapshot clears that asset's recovery
requirement. A delta or a best-price hint cannot restore a missing book. Unrecovered assets still
trigger the existing bounded reconnect policy. These invalidations remain visible; no fills or
queue cancellation credit are inferred from those split messages. Raw decoding now rejects a crossed
delta as a recorded invalidation and can continue to a subsequent full snapshot instead of crashing.

A missing CLOB book in one discovery row previously aborted the entire metadata poll. Discovery now
skips already-expired tradable-book lookups, reports the exact public URL/status for a per-market
404, continues the remaining universe and resolution polling, and disables a known affected market
without refreshing its metadata timestamp. Its maker cancels retain modeled acknowledgement delay;
pending takers are removed. The disabled metadata persists across restart until verified META restores
it. Rate limits, network/server failures and errors in resolution polling still fail/back off globally;
404 is not a fabricated empty response or resolution. Official API reference checked:
https://docs.polymarket.com/market-data/realtime-data and https://data-api.polymarket.com/v2/docs .

The recovery follow-up passes **83 Java tests and seven Python tests** locally, including failed-book
isolation, global Retry-After, expired discovery, split-frame snapshot recovery, raw crossed-book
recovery and disabled-market restart behavior. Test HTTP mocks use the subclass mock maker to avoid
requiring runtime Java agent attachment. The push collector is extended to 900 seconds to include at
least one 15-minute clock boundary, followed by baseline/stress replay. This longer run remains a
bounded diagnostic, separate from the registered seven-day acceptance experiment.

## Raw decoder isolation correction

A raw replay diagnostic on the same 176.218-second tape initially counted 13,696 invalidations.
Direct decoder inspection traced 13,683 to repeated delta-without-snapshot fallout after one old
source event globally deleted every cached book. This differed from the streaming adapter. Raw
normalization now ignores source regressions without refreshing state, isolates an invalid/missing
book to its token, preserves that token's source watermark even before an initial snapshot, and
requires a non-regressing full snapshot to restore it. Repeated deltas while awaiting that snapshot
remain untradable; no synthetic snapshot, fill or cancellation credit is introduced. Actual transport
reconnects reset decoder state. Derived depth invalidations are not counted again when raw frames
have already independently produced them.

The complete raw strategy replay now reports 10 invalidations, cash 500 and zero fills/PnL on that
same diagnostic recording, matching its normalized report's invalidation count. This is a bug fix in
book-state isolation and duplicate accounting, not a change to acceptance or an inference of missing
fills. New tests cover unrelated-book isolation, incomplete snapshot recovery, transport reset and
rejecting an older snapshot after a newer delta. The full suite now contains 86 Java tests, plus the
existing seven Python checks. CI also runs raw baseline alongside normalized baseline and stress.

The investigation's 900-second collector is running at commit `ddb11d0c0067056e5da619ed8bfda03c48df3e1c`
in run `38957407035`. Subsequent routine pushes return to the 180-second smoke rather than launching
another 15-minute collection for a decoder-only correction; that does not shorten or cancel the
already-running investigation. Its recorded collector revision and the replay implementation revision
remain separately visible. Neither duration substitutes for the heldout acceptance window.
