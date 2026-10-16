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
