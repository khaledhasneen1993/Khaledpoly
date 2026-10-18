# Execution investigation — 2026-10-17

PAPER only. Starting point: `735fffb4e0671da7a51a66257a6ae35fba849a98`
(PR #8, not merged). Final lifecycle replay run: 39060818126.

Observed baseline: 44 orders, zero fills, $500 cash, zero realized PnL.
Terminal reasons: RESTING_NET_EDGE 22, RESTING_PRICE_INVALID 10,
POST_ONLY_WOULD_CROSS 6, PEER_REJECTED 6. This does not identify whether
prints were eligible or the queue was exhausted. It does not establish alpha.

This iteration adds measurements without changing pricing, eligibility, latency,
queue multiplier, fees, risk limits or cancellation decisions. Per-order diagnostics
record actual activation time and initial queue, active duration, eligible print
volume and mutually exclusive print rejection reasons. QUEUE_NOT_EXHAUSTED is
an additional annotation; do not sum it as an independent print. Counts are per
order, not unique venue trades. Timestamps absent before activation remain null.
RESTING_RISK_CHECK records own net edge and contemporaneous required edge when
canceling, to distinguish thin-depth premiums, volatility and price invalidation.

Workflow: `PAPER fill diagnosis and independent capture`, branch
`paper-fill-investigation`. Verify all tests before running either experiment.
Historical job replays the original full two-hour tape (lossless transport,
logical SHA retained). Fresh job records a new two-hour public PAPER baseline
with identical configuration and compressed journals. No reset/restart on losses.
Small reports and large compressed tapes are separate artifacts so reports remain
accessible. This fresh sample is diagnostic, not a seven-day qualification holdout.

Next iteration must read BOTH reports before selecting any behavioral change.
If eligible prints are absent, waiting longer or reducing the queue multiplier
is not an evidence-based fix. If valid opportunities are canceled by a measured
risk premium, evaluate a predeclared pricing/market-selection candidate without
weakening the existing floors. Replay baseline and candidate on the same input,
record all variants tried, then freeze a candidate before new independent data.
Keep existing `research/phase2/acceptance.json` unchanged: 100 maker fills,
100 resolved markets, seven heldout days, 95% pair completion, positive net
baseline and stress PnL, and all other existing safety/data gates.

Hourly follow-up is enabled in this conversation. Check current jobs before
starting any new run, and persist resulting diagnosis and next action here.
Do not declare profitability from a green build, a two-hour sample or zero loss.

## Historical result — reviewed 2026-10-18 00:40 Asia/Amman

Run 39067539123, historical job 117498492412, artifact 12113893739 succeeded.
All 141 Java and 200 Python tests passed before starting the two experiments.
Preserved evidence: `fill-investigation-20261018/` (full report, diagnosis,
logical tape provenance, cancellation risk checks and file checksums).

- 44 submitted / 38 activated / zero fills; cash $500 and realized PnL $0.
- 25 orders saw no same-token print while outstanding. One order had eligible
  prints: sim-research-17, two prints totaling 60 shares, versus initial queue
  ahead 141.78 and remaining queue 81.78. Displayed depth before the 2x
  multiplier was 70.89, also above the 60 eligible shares. This arithmetic is
  not a counterfactual replay or a justification to change the queue model.
- 62,094 aggregate active order-ms across all legs. Per-order classifications:
  21 wrong aggressor, 20 not active yet, 2 earlier than current book, 2 different
  price, 2 eligible prints. The 2 queue-not-exhausted annotations are a subset
  of eligible prints, not extra prints. These counts are not unique trades.
- 11 pair cancellations (22 legs) had valid prices but own net edge below the
  contemporaneous threshold as top depth thinned. Five pairs (10 legs) had
  invalid prices. Six post-only rejections caused six peer cancellations.
- Full replay source logical SHA remains
  330b3d65eff84abdcead2b84337d17bc52e84c4d022b32e8b9808a26e00873ce.
  Compressed file hashes can differ because gzip headers differ; use logical
  SHA for source identity. No new fill or profit has been demonstrated.

The fresh public PAPER job 117498492549 was still running at this review,
started 2026-10-17 23:39:38 Asia/Amman, expected to finish around 01:40
on October 18 plus inspection/upload time. Do not rerun or modify it.
Next action: read `fresh-paper-small-reports` and compare its eligibility and
cancellation evidence with this historical result BEFORE behavioral changes.
No current evidence supports loosening fills, stale-data limits or risk gates.
Select a pricing/market-selection hypothesis only after both reports are read.
This documentation checkpoint changes no code and skips CI to avoid a second
simultaneous two-hour capture.

## Fresh result and next predeclared experiment — 2026-10-18

Fresh capture completed normally at 01:39:39 Asia/Amman on October 18,
7,200.629 seconds, 240 samples, clean journal, no restarts. Run 39067539123
passed all jobs. Small artifact 12117291307, full compressed tape artifact
12117311261. Persisted metrics: `fresh-paper-20261018/`.

52 submitted / 45 activated / zero fills / zero eligible prints; $500 cash,
$0 realized PnL, no holdings or risk breaches. 18 orders had no same-token
print. Per-order observations: 86 before activation, 158 wrong aggressor,
13 earlier than current book, 5 different price. Aggregate active duration
34,600 order-ms. Terminal reasons: invalid-depth gap 16, net edge 16,
invalid price 10, stale book 2, post-only rejection 5, peer rejection 3.
Capture has 23,400 normalized gaps, including 22,506 stale-source and 852
invalid-depth events; 22,247 stale events were already stale at callback.
These are real data-quality limitations; do not remove the freshness gates.

Both diagnostic tapes have now been read. They are development data from this
point onward, never a frozen qualification holdout. The existing one-tick
improvement on each leg spends up to .02 of the pair edge and puts the quote
at prices where these observations rarely show eligible opposite-side prints.
This supports testing a less expensive quote, not assuming it will fill.

Predeclared candidate QB0 (one variant only): `makerImprovementTicks=0`, join
the current best bid on both legs. Baseline remains `1`, including missing
JSON fields, recovered legacy checkpoints and all existing callers. Existing
entry/reprice paths use the same price policy. Current PAPER default is still
baseline; the candidate is enabled only by `research/phase6/quote-candidate.json`.
Stress must preserve this quote policy while increasing existing execution costs.
Do not lower the dynamic/base edge threshold, minimum size, queue multiplier,
latency, fee estimates, freshness requirements, or inventory/loss limits.
Joining best bid may increase the real modeled queue and adverse selection.

Before viewing candidate performance, freeze this candidate/config and compare
baseline and QB0 on BOTH full diagnostic tapes with raw replay. Reproduce
known baseline order counts (44 and 52) and zero fills first. Retain every
candidate result, including losses. Exploratory screening requires positive
net realized PnL greater than baseline, at least one completed pair, no residual
holdings, no risk breach/halt, drawdown <= $50, and expiry residual <= $5.
This only decides whether another independent PAPER test is worth running;
it does not replace any criterion in `research/phase2/acceptance.json`.
If QB0 is not viable, record rejection and inspect its execution/risk diagnostics;
do not automatically launch another current-market capture or retune blindly.

Workflow `PAPER predeclared best-bid comparison` verifies all regressions before
two dataset comparison jobs. The prior two-hour capture workflow is now manual
only so a code push cannot silently start another two-hour run. No fresh
capture is scheduled as part of this comparison. Next review: inspect both
`quote-comparison-original` and `quote-comparison-fresh` artifacts and persist
their results here. Only a promising candidate proceeds to frozen baseline/
stress validation on independent future recordings; LIVE remains disabled.

## QB0 result — 2026-10-18 03:32 Asia/Amman

Run 39079812595 passed verification and both full comparisons. Candidate commit
d5ff383bd387e240f8a8f5deac720a0e036a04da. Artifacts: original 12118663413,
fresh 12119320792. Persisted comparison and full candidate reports:
`quote-qb0-20261018/`. Baselines reproduced exactly (44/52 orders, zero fills).

| Development recording | QB0 orders | Fills | Net realized PnL | Completed pairs | Halted |
| --- | ---: | ---: | ---: | ---: | --- |
| Original two hours | 119 | 2 | $0.16474 | 0 | true |
| Fresh two hours | 296 | 0 | $0 | 0 | false |

QB0 is REJECTED by its predeclared screen on both tapes. No new independent
capture, adoption, parameter sweep or profitability claim is justified.
The original two executions were one maker BUY of five shares at .37 and one
taker risk SELL at .42, fee .08526, after the unhedged timeout. The .16474 is
not complete-set alpha. Drawdown was .80, no numerical risk breaches; `halted`
reflects the existing latched entry stop after 30 seconds unhedged. Do not
remove that risk stop. Before timeout a hedge decision had positive completion
value .02107 but higher sale value .02307; the existing policy waited/quoted
a maker sale. This is a documented policy tradeoff, not proof of a missed fill.
Fresh QB0 had four eligible prints across four orders; all were absorbed by
the conservative queue (38.46 vs 305.2, 5 vs 7808.64, 64.32 vs 535.32, 2 vs
444.28). No evidence supports reducing the multiplier or granting touch fills.

Next diagnostic: count necessary quote-price/base-edge conditions on ALL
recorded public prints, including periods when strategy orders were absent.
This determines whether scarce eligible traffic is fundamental or confined to
current entry windows. `opportunity_census.py` uses prior normalized books,
source/metadata freshness, new-entry size, quote alignment, merge cost and the
base edge floor. It deliberately omits dynamic risk premiums, activation,
queue depletion, account/inventory limits and order placement before a print:
passing is an UPPER BOUND, never a feasible fill, probability, or PnL estimate.
No execution behavior or acceptance gate changes. Two local unit tests verify
gap invalidation, price alignment and no-fill/no-profit inference.

The QB0 workflow is now manual-only to avoid repeating completed comparisons.
The new `PAPER recorded opportunity census` workflow scans the same two
development tapes once and produces small reports. Next review: inspect
`opportunity-census-original` and `opportunity-census-fresh`, validate logical
tape hashes against preserved provenance, and assess print coverage before
predeclaring any further strategy candidate. Keep QB0 rejected/default legacy.

## Census transport correction — 2026-10-18 04:37 Asia/Amman

Run 39083353569 failed in both scans at the official resolution event: the
new analysis script incorrectly read `condition` instead of the recorded
`condition_id`. No census result was produced and no result may be inferred
from that run. Correct the schema handling, preserve temporary market
unavailability (fresh later metadata can restore it) and apply recorded tick
changes to the quote grid. Four unit tests now include the actual official
resolution field and tick changes. Rerun the same read-only census after
these corrections; do not change execution or launch another market capture.

## Direct-route census and complementary-match hypothesis — 2026-10-18 05:40

Run 39087175615 succeeded on both complete tapes. Reports persisted in
`opportunity-census-20261018/`; artifacts original 12121072531, fresh
12121675799. Original logical SHA matches preserved provenance exactly;
fresh logical SHA is cd850df52d7f9994526603130f2942008f8f49ba80495d82b70dea66f0dc6d8b.

| Recording | Public prints | BUY prints | Direct necessary conditions, improve 1 | Direct necessary conditions, join 0 |
| --- | ---: | ---: | ---: | ---: |
| Original | 6,377 | 5,640 | 3 | 12 |
| Fresh | 16,317 | 15,024 | 2 | 45 |

These are optimistic necessary conditions, NOT fills or fill probabilities.
The label WRONG_AGGRESSOR in the original census means wrong side for the
existing SAME-TOKEN maker-buy model only. It does not prove that a BUY print
cannot participate in any venue matching route. Do not conclude fundamental
market-wide opportunity scarcity from the direct-route counts alone.

Official primary sources reviewed 2026-10-18:
- https://github.com/Polymarket/ctf-exchange-v2/blob/main/README.md (Order
  Lifecycle): BUY/BUY MINT and SELL/SELL MERGE exist in addition to direct
  BUY/SELL matching. Complement tokens belong to the same binary condition.
- https://github.com/Polymarket/ctf-exchange/blob/main/docs/Overview.md
  provides complementary-outcome mint/merge matching examples.
- https://docs.polymarket.com/market-data/realtime-data exposes public
  last-trade price/size/side and an optional transaction hash; it does not
  establish a particular resting order's queue allocation or guarantee that
  every opposite-outcome BUY print is a distinct MINT fill.

New hypothesis: the strict same-token SELL-only paper matcher omits a possible
complementary BUY/BUY route. This is NOT yet a confirmed missed execution.
Before changing matching, extend diagnostic census only: for a BUY on token B
test candidate BUY-A price 1-p(B), requiring known binary complement metadata,
fresh prior books/source, exact quote alignment and the same necessary base
edge/size checks. Exclude unverified negative-risk routes. Do not emit trades
or credit any queue/fill/fee/PnL from this diagnostic conversion. Identify
overlapping direct/complement fingerprints without assuming uniqueness; one
venue execution must never be counted twice. Inspect raw public trade field
coverage and five bounded samples for available transaction-level evidence.

Six local tests cover direct-route invariance, complementary candidate mapping,
overlapping route fingerprints, gaps, resolution, tick changes and reference
validation. The next full scan must preserve original direct counts (12/3 and
45/2 for policies 0/1) AND both logical tape hashes, or fail. No execution
model change, queue relaxation, new strategy variant or fresh capture occurs.
Next review: inspect route counts, overlap flags and transaction field coverage.
Only consider a separately frozen, default-off complementary execution model
after evidence resolves side semantics, queue allocation and duplicate prints.
