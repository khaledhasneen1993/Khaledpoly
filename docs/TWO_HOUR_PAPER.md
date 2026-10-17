# Single two-hour PAPER experiment

Workflow: `Two-hour PAPER experiment`, on branch `paper-two-hour-experiment`.
The initial push creates one run; ordinary subsequent pushes do not rerun it unless the workflow file changes. No schedule or automatic retry is configured. The existing verification workflow does not run for this experiment branch.

The tested 0.6.0 base is `2ccbf5b2d4b13509dd736e0c069445b7281d01ea` (PR #7). Build once with tests skipped because that Java source already passed verification; run the new supervisor tests before launch.

The central complete-set strategy and virtual matching run in one loopback-only executor with a new $500 PAPER ledger. The timer is 7,200 seconds from process launch, including startup. Shutdown begins at the deadline. No restarts, risk resets, forced entries, signing credentials or alert deliveries. Existing fee, freshness, inventory and drawdown limits apply. A risk halt remains halted while recording continues. Public feed failure or no positive entry can result in zero fills; that is evidence, not an invitation to relax limits.

Every 30 seconds the runner preserves metrics; it also saves the last successful observation, final metrics/ledger, exact revision, elapsed duration, raw/normalized ingestor journal and clean-close inspection. Signals/termination trigger shutdown and a partial manifest. Four consecutive API failures after startup grace stop the experiment early and fail the job. Runner/process failure can still leave incomplete data, which must not be interpreted as a completed run.

A single compressed artifact `two-hour-paper-RUN_ID` is retained three days. Packaging/upload uses `always()` so early failures retain available evidence. Whole job timeout is 140 minutes and execution step timeout is 124 minutes; additional time is for build and artifact upload, not more trading. GitHub service cancellation, disk exhaustion or provider outage can prevent full retention. The upload is a private account snapshot only in the PAPER sense; it contains no venue secrets.

No full two-hour replay or trained event/ML model is enabled in this experiment. The retained tape supports subsequent replay, fill analysis, markout, PnL, residual inventory and gap review. Two hours do not establish seven-day capture coverage or profitability. Economic acceptance remains `NO_GO`.
