# Phase 2 completion work — validation

Date: 2026-10-16. Java 21, Maven 3.9.9. This is implementation evidence, not a claim of profitable
market performance or approval to proceed to phase 3.

## Verified locally

- All seven Maven reactor projects passed `verify`: **73 Java tests, zero failures/errors/skips**.
- Four Python evaluator tests passed. They verify retroactive-freeze rejection, training/holdout
  separation, NO_GO on missing evidence, and the complete-evidence GO branch on an explicitly
  synthetic unit fixture. LIVE remains false even in that fixture.
- The real Spring executor bridge runs `ResearchSession`, generates its own pair orders from public
  observation fixtures, accounts partial/full maker fills, merges cost bases, and reports the same
  result as standalone closed-loop replay. The manual legacy pair API is rejected in this mode.
- Closed-loop baseline/stress execute separate accounts. No recorded order, fill or decision is
  treated as a strategy input. Receive-clock regression, future metadata and missing raw snapshots
  reject or invalidate state. Tick changes cancel incompatible quotes.
- Tests cover maker inventory sale, delayed depth/fee-aware risk sale, separate exit-loss cap,
  conservative restart behavior, terminal resolution/idempotency, durable alert deduplication and
  retry, honoring long venue Retry-After headers, plus every first-delivery and phase-one regression.
- Packaged `ClosedLoopMain` ran the committed observation-only synthetic fixture: baseline cash
  500.89/net realized PnL 0.89 after a 0.01 merge; stress cash 500 with no fills. These are accounting
  assertions, not attainable market returns. The evaluator correctly returned NO_GO for these
  incomplete, non-heldout inputs.
- The dashboard script passed `node --check`, launch scripts passed `bash -n`, workflow YAML parsed,
  and `git diff --check` passed.

## Actual public-data attempt

The packaged record-only application was run locally with simulation and strategy disabled, no
wallet credentials, and a separate recording directory. It produced 112 scheduler ticks, two
`RESEARCH_FEED_ERROR` records (`ConnectException`), a clean `RUN_END`, and **zero market events or
fills**. Ticks continued while HTTP failed, exercising the independent clock scheduler. The observed
summary is in `research/phase2/validation/local-public-access.json`. No connection success, resolution
coverage, or market PnL was invented. A separate public Gamma slug probe returned HTTP 403.

GitHub verification additionally performs a bounded 90-second public-data smoke on a push to this
branch, preserving the recording and its actual error/count summary as `phase2-public-recording`.
That run is diagnostic only; network success depends on the runner and venue availability.

## Not satisfied

The local environment did not obtain a real-market validation dataset. Seven complete independent
UTC days, 100 resolved traded markets, 100 maker fills, measured holdout/stress profitability and
long-duration recorder behavior are not verified. External Slack/Telegram delivery was not enabled
or sent; adapters are opt-in and their local durable-outbox behavior is tested. Docker is unavailable.

The original acceptance thresholds are unchanged. The frozen candidate window is 2026-10-17 through
2026-10-24 UTC; capture is not automatically scheduled by a freeze file. Missing that window requires
a new future freeze. **Current gate: NO_GO; phase3Allowed=false; liveAllowed=false.**

## Real GitHub recording and data-driven regressions

Run `38927626046` successfully collected public venue data for 87.83 seconds: 12,637 raw WS frames,
24,339 normalized depth updates, 43 public prints, 20 metadata observations, and five clock samples.
There were 28 gap/invalidation signals (16 stale-source, six depth-invalidations, six reconnects).
The complete artifact is linked from that Actions run; summarized evidence is committed under
`research/phase2/validation/ci-public-initial.json`.

Closed-loop replay of that actual recording exposed an extreme-price/stale-tick boundary. It is
now guarded before reservation, with tick rounding and a regression test. Venue price-change batches
also now validate their final per-asset state atomically, rather than rejecting transient intermediate
crossings. Invalid final batches still fail closed and roll back. Inactive/future market instances are
excluded from WS subscriptions; unresolved conditions remain polled for explicit resolution. Shutdown
ignores late WS callbacks. These changes preserve the 2-second source-age requirement and original
risk/acceptance thresholds. They are engineering fixes derived from training/smoke data before the
heldout window, not optimization on heldout returns.

After the price-boundary fix, baseline and stress both completed the actual recording: cash 500,
net realized PnL 0, zero bot fills, and 28 recorded gaps. Evidence is in
`research/phase2/validation/ci-public-replay.json`. Public prints are not bot fills. This does not meet
the sample or profitability gate. The workflow now automatically runs both full-strategy replays
on every collected smoke dataset, so recording success alone cannot hide a replay failure.
