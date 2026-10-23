Warning: truncated output (original token count: 76630)
Total output lines: 4682

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

## Complement route census — 2026-10-18 06:39 Asia/Amman

Run 39091061373 passed both scans. Artifacts original 12122577227, fresh
12123270316; full reports persisted in `complement-census-20261018/`.
Both logical hashes AND direct-route reference counts reproduced exactly.
Additional optimistic complementary BUY candidates: improve-1 original 9,
fresh 41; join-0 original 60, fresh 502. No direct/complement fingerprint
overlap was observed; this does not establish execution uniqueness or prove
that any candidate exhausted a queue. No fills or PnL inferred.

Raw trade field coverage provides a stronger next check: all 6,410 original
and 16,411 fresh RAW last-trade messages include `transaction_hash`. Counts
differ from accepted normalized prints because raw observations also include
messages rejected or deduplicated by the feed. Five bounded raw samples per
tape retain transaction hashes, token, side, price, size, timestamp and market.
Do not retroactively change matching from candidate counts alone.

Next step is a bounded PUBLIC READ-ONLY receipt audit of those ten fixed
samples, using Polygon chain ID 137. Only `eth_chainId`,
`eth_getTransactionReceipt`, `eth_getBlockByHash` are allowed; all signing and
transaction-submission methods are rejected before any network call. Persist
raw receipts/block headers and exact RPC errors. Validate hash/status/block
identity, then decode CTF Exchange V2 events only from official allowlisted
addresses. Join per-maker events to ONE taker aggregate event using order hash,
taker maker address and log order; never count aggregate+maker as separate
traded volume. Classify BUY/BUY MINT, SELL/SELL MERGE and direct routes only
when event fields agree. Unknown contracts/ABIs remain uncorroborated.

Primary sources reviewed 2026-10-18:
- https://docs.polymarket.com/resources/contracts — current Polygon addresses.
- https://github.com/Polymarket/ctf-exchange-v2/blob/main/src/exchange/mixins/Events.sol
  — exact event signatures, indexed fields and word layouts.
- https://polygon.publicnode.com/ — public Polygon RPC.

The optional isolated audit environment pins pycryptodome 3.23.0 solely for
Ethereum Keccak event topics; no wallet/keys/signing are used and no production
dependency changes. Three local unit tests verify maker/taker grouping,
duplicate/unclosed groups, untrusted addresses and the read-only RPC allowlist.
Next review: `public-receipt-audit` artifact, route types and exact sample
token/side/price/size comparison. Receipt settlement evidence alone cannot prove
a hypothetical order's allocation, causal queue position or profitability.
If RPC is transiently unavailable, retain errors without manufacturing evidence.

## Receipt corroboration result — 2026-10-18 06:46 Asia/Amman

Run 39094538217 succeeded; artifact 12123388351. All TEN fixed public samples
returned successful Polygon receipts and matching block headers; no RPC or
decoding errors. Across these ten taker matching groups there were 27 MINT
maker portions and 5 DIRECT maker portions. Every sampled transaction included
MINT; one included both DIRECT and MINT. These portions are not 32 independent
public prints and must not be added to the ten taker aggregates as new volume.
Recorded token/side matched the taker event; sizes matched exactly, and price
differences were zero or below 0.00000001 (integer settlement rounding).
Full receipt report is persisted in `receipt-audit-20261018/`; raw RPC evidence
is retained in the linked workflow artifact.

This corroborates an incomplete route representation in the same-token-only
model; it does NOT establish the queue allocation of any hypothetical bot
order. The ten samples are the first five per tape, not necessarily the
previous quote-aligned candidates. Do not extrapolate MINT share to all prints
or convert these samples into historical fills. Receipts arrive after the WS
matching messages: they are offline ground-truth labels, never features for
earlier decisions or permission to backdate a fill after an order was canceled.

Harden the decoder to reject invalid aggregate sides/amounts and to retain
separate matching groups even when the same taker order hash repeats. All ten
actual saved receipts were revalidated OFFLINE through the hardened decoder;
match types and aggregate counts were unchanged. Eleven local tests now pass.
The completed RPC audit workflow becomes manual-only: no repeat public requests
are needed for decoder-only changes.

Next required evidence is the transactions of the actual quote-aligned
candidates. The original normalized `tradeId` already retains the full public
message JSON, including transaction_hash; no production feed or execution
change is needed. Extract a typed transaction hash and binary token pair into
the diagnostic candidate rows, increase the bounded example limit to 2000
and explicitly flag truncation. At current counts this retains all 84/590
necessary-condition rows. Keep source hashes and direct-route counts frozen.
This yields a compact candidate evidence set for future receipt audits without
continually rescanning 20 GB recordings. Next review: validate candidate hashes,
then audit a fixed bounded sample of actual complement candidates and assess
mixed-route volume/identity before designing a default-off matching experiment.
No execution model or profitability qualification changes in this iteration.

## Transaction-linked candidate evidence — 2026-10-18 07:37 Asia/Amman

Run 39094813284 completed successfully. Original artifact 12123834350 and fresh
artifact 12123563657 preserve all 84 and 590 necessary-condition rows, with no
truncation and a transaction hash on every row. Both logical tape SHA-256 values
and frozen direct counts (12/3 original, 45/2 fresh for zero/one tick) matched.
Persist the compact reports under `transaction-linked-census-20261018/` so no
further 20 GB tape scan is needed for these candidate identities.

Freeze the first five UNIQUE one-tick complementary candidate transactions per
tape, sorted by source time, observed time and transaction hash BEFORE public
receipt queries. The full population remains 9/41 rows; do not cherry-pick a
different sample after outcomes. `fixed-selection.json` records the ten chosen
samples, source digests, target token/price and condition. Fail closed on missing
hashes, truncated evidence, inconsistent binary pairs or counts.

The bounded candidate audit compares the exact recorded public aggregate size,
token/side and rounded price against each settlement group. It reports actual
target-token MINT maker shares separately from DIRECT shares, checks share
conservation and counts matching groups without collapsing repeated taker hashes.
Even conserved MINT volume at the implied price is NOT a hypothetical order fill
and does not establish queue exhaustion, priority or a pre-cancel match. Receipt
data is future information, offline validation only. Seventeen local unit tests
pass, including mixed routes, ambiguous groups, wrong size/price and conservation
failures. No execution, fees, risk, latency or acceptance changes.

Next: inspect fixed-candidate-receipt-audit selection/report/raw receipts. If
target-token volumes and identity corroborate, specify a conservative default-off
experimental route model with causality, deduplication and queue assumptions
explicitly frozen before another comparison. Otherwise record the exact mismatch;
do not convert full public BUY volume into complement fills. Existing QB0 is
still rejected; net PnL results remain +0.16474 original / 0 fresh, not qualified.

## Fixed-candidate audit results — 2026-10-18 07:43 Asia/Amman

Run 39097821365 succeeded, artifact 12124454874. All ten frozen transactions
returned receipts with no errors; runtime selection exactly matched the
pre-query committed selection. Persisted original strict report, all ten raw
receipts/block headers, selection and reproducible offline labels under
`candidate-receipt-audit-20261018/`. The completed workflow is now manual-only.

Nine samples contain target-token MINT; one is DIRECT-only; three of the nine
mix MINT and DIRECT. Across ten taker aggregates, total shares are 623.652586:
595.592586 target MINT plus 28.06 DIRECT, not those amounts PLUS the taker total.
Only 530.97 MINT shares meet the strict implied-price comparison (1e-8), or
536.06804 when separately reporting integer collateral rounding within ONE
micro-unit. Neither number is an eligible bot fill or a relaxed execution rule.
The remaining MINT volume traded at other prices. Blind complementing the
entire public print therefore misallocates both route and price-level volume.

Five samples passed the initial exact public-price/aggregate comparison and
five did not. Retain that result. Offline inspection found all ten have a
unique conserved aggregate with matching token/side/size; in four samples the
public price differs materially from the aggregate weighted price (up to
0.004444...), and one differs by integer collateral rounding. Separate identity
matching from the strict price result; do not pretend the public price is
necessarily the weighted average. No RPC repeated; unchanged decoded maker
groups checked against original reports. These are offline ground-truth labels,
not earlier decision features. Reproduce with:

`python -m research.phase6.candidate_receipt_audit --offline-from research/experiments/candidate-receipt-audit-20261018 --output /tmp/candidate-labels-new.json`

Also join ALL 9/41 one-tick candidates to actual baseline order lifecycles:
original has zero active target-token orders; fresh has 11 overlapping rows,
all with a MORE aggressive live BUY price, none at the public implied price.
Ten overlap sim-research-4 (0.64, initial queue zero, active for 752 ms before
RESTING_NET_EDGE); one overlaps sim-research-42 (0.15, initial queue 1240.32,
later invalid-depth GAP). More aggressive does not mean a proven fill: current
book validity, priority, queue and unique route volume still need validation.
Do NOT conclude that absent exact-price overlap proves no potential execution.
Historical compressed-input SHA differs from logical uncompressed SHA by
design; the join verifies retained report/provenance manifest hashes, lossless
storage declaration, logical tape hash and row count instead of ignoring it.

Next concrete investigation: inspect the already compact receipt labels and
raw order/book evidence around sim-research-4, including source-vs-arrival book
ordering and its peer leg. Specify a default-off, development-only
settlement-labelled fill experiment with unique (exchange, transaction,
OrdersMatched index, maker log index) identity, price priority and per-price
volume conservation. Labels may describe the replay environment but must never
enter strategy decisions, activate an order before its latency, survive a GAP,
resurrect a canceled order, or be mistaken for an independently validated live
model. Do not launch another two-hour capture until a justified frozen candidate
passes same-development comparison. Strategy/execution and acceptance remain
unchanged; NO_GO, no new PnL. Seventy-nine phase6 unit tests pass locally, including
offline re-decoding of all actual candidate receipts with no network calls.

## Bounded causal window extraction — 2026-10-18

No overlapping runs remain: 39097821365 and 39094813284 completed successfully;
PR #9 remains draft/open on unchanged stacked bases, head 479426a9d5ada64a413828a606be9d7d3c81cec4.
Extract two fixed windows from the EXISTING fresh tape, not another market
capture or census. Specs retain both peer order lifecycles, token pair/condition,
three seconds before submission and three seconds after terminal, and the
previously verified full logical tape hash. Keep original rows and frame order,
RAW messages concerning either token, scoped/global gaps and preceding metadata.
The context is deliberately wider than the frozen 2000ms book freshness limit.
Do not call the cropped rows a complete replay tape or infer fills from them.
The extractor rejects unclean chronology, wrong logical hash, oversized/empty
windows or truncation. Three local tests pass. No execution behavior changed.

Next inspect `bounded-active-order-windows`: source/arrival ordering at the first
corroborated MINT overlapping sim-research-4; both current books; pending
cancellation and peer-leg risk; GAP invalidation around sim-research-42. Use
the existing committed receipts for route/price volumes without extra RPCs.

First extraction run 39101087860 failed closed at the 16 MB window retention
bound; it produced no usable evidence. Do not treat it as a market-data failure.
Narrow RAW selection to original target-token last-trade messages (normalized
book frames remain unchanged), increase the explicit memory bound to 64 MB
and include row/byte counts on failure. No truncation, chronology or source-hash
checks are removed. Retry this corrected extraction, not a new capture.

## Causal window result and adverse-selection evidence — 2026-10-18

Corrected extraction run 39101203025 succeeded; artifact 12126507232. Full source
logical hash matched. Windows retained 3333/3851 original rows, 18,253,026 and
25,873,292 original encoded bytes. Pretty-printed extraction is 162,747,208
bytes, so do not commit redundant full-depth snapshots. Persist a deterministic
gzip/base64 top-of-book/own-price diagnostic projection (~693 KB), with source
extract hash, per-row canonical fingerprints and projection hash. It is explicitly
NOT full depth or queue-calibration evidence. The causal analyzer produces
EXACTLY the same result from the full extraction and projected evidence; source
frame event indices and arrival/source order remain intact. Full original rows
remain in the linked artifact. Completed extraction workflow becomes manual-only.

Reuse the ALREADY COMPLETED quote comparison's baseline audit, run 39079812595,
artifact 12119320792: no new replay required. All four investigated order
lifecycles exactly equal the original live report. Persist the relevant ORDER,
RESTING_RISK_CHECK, CANCEL_REQUEST and terminal records plus full source file
hashes in `order-window-20261018/baseline-order-audit.json`.

The first window has 50 complementary BUY observations during sim-research-4's
recorded activity, five covered by the previously frozen actual receipts.
At those five events both books were fresh, trade source was not earlier than
either current book, and source was strictly after observed activation. All
five arrived BEFORE the real cancellation REQUEST at 1792269683929, not merely
before terminal at 1792269684180. First corroborated arrival: 1792269683761.
The initial model queue was zero, quote 0.64; the first corroborated venue MINT
maker portions traded at 0.63. Later receipts show still lower maker prices.
This isolates missing complementary route AND cross-price priority coverage,
not a stale-book or already-effective-cancel explanation for those observations.
It still does not establish private queue allocation or an actual bot fill.

Crucially, these missing executions are NOT evidence of profit. Target best
bid/mid after the first corroborated observation were 0.62/0.645 initially,
0.56/0.615 at +100ms, and 0.53/0.595 at +250ms versus the bot's 0.64 buy quote.
This is adverse quote movement, NOT realized bot PnL or a fabricated fill.
At +500ms mid is 0.495 but a GAP occurred in between, explicitly flagged; do not
report a clean markout across it. The peer 0.34 buy has no demonstrated hedge
fill in this evidence. The existing risk cancellation was justified: reserved
net edge 0.018 fell below dynamic required edge 0.0302947852655060345. Do not
lower that requirement simply to keep adverse quotes alive. Second window has
seven complementary observations, no corroborated receipts in the frozen set,
and the invalid-depth GAP at its actual terminal time; no extra fills inferred.

Next implementation is frozen as CS-MINT-LAB0 in `next-experiment-spec.json`:
default-off, research-only settlement-labelled matching calibration, no strategy
changes. Preserve latency, queues, fees and risk; unique maker identities and
per-price volume conservation; replace labelled aggregate liquidity rather than
double-counting legacy+MINT; no future receipt features or resurrected orders.
Partial label coverage can NEVER qualify independent PAPER profitability.
Implement synthetic causality/conservation tests before a same-development
comparison. No new two-hour capture until a justified candidate exists.

Reproduce causal diagnostics offline with `python -m research.phase6.analyze_order_window`
and `--windows research/experiments/order-window-20261018/evidence.json.gz.b64`,
`--receipts research/experiments/candidate-receipt-audit-20261018/offline-volume-labels.json`,
`--audit research/experiments/order-window-20261018/baseline-order-audit.json`,
and a new `--output` path. Eighty-eight phase6 tests pass, including actual saved
window/receipt/audit reproduction with no RPC. Execution/strategy/acceptance
unchanged. NO_GO; no new PnL. Prior QB0 remains rejected.

## CS-MINT-LAB0 allocation kernel — 2026-10-18

Starting head 539726f97ce2dd91a937b80c13c7f53ee66b0732; PR #9 still draft,
stacked on unchanged #8/#7. Prior extraction/receipt runs completed, so no
overlapping capture or replay was launched. Implement the frozen model spec
as an ISOLATED Python research component, disabled unless `--enabled` is explicit.
No account, strategy, SDK, production executor or network imports are introduced.
This is NOT yet the production Java matcher or a closed-loop strategy replay.

Receipt groups must conserve BOTH integer shares and collateral, with trusted
exchange, binary token identity and unique maker log identities. Bind the exact
recorded public token/side/price/size/source timestamp, original tradeId fields,
sequence and frame event index. Public price is not assumed to be weighted
aggregate price. Process ONLY actual maker components; legacy aggregate+component
credit is explicitly rejected. Global maker IDs cannot be reused across events
or windows. Stale/gapped/pre-activation/discarded components cannot resurrect
orders or become future liquidity. Invalidated orders remain terminal after
book recovery. Original 250ms activation/cancel, 2000ms freshness and measured
baseline queue seeds (multiplier 2) remain unchanged. The diagnostic top-book
projection is NOT used to estimate queue depth.

The allocation kernel models price priority, partial allocations and same-price
own-order queue prefixes with one residual volume budget; it never grants queue
cancellation credit. Retains explicit hidden-liquidity/cross-price queue
uncertainty. Lifecycle/cancel times are the MEASURED baseline ones; after a
counterfactual allocation the strategy's changed decisions are NOT simulated.
Do not promote this bounded calibration into a full strategy performance test.

Same fixed evidence/component comparison, persisted in `settlement-lab0-20261018/`:
disabled yields zero allocations; explicitly enabled binds the five frozen
fresh receipts and conditionally allocates 5 shares to sim-research-4 at its
0.64 quote, arrival 1792269683761. Actual labelled venue component quantity
totals 500 shares: modeled allocation 5, queue absorption 0, unused 495. Each
share is counted once, including mixed DIRECT/MINT groups, not aggregate PLUS
maker volume. This is a COUNTERFACTUAL allocation under measured queue seeds,
not a new actual bot fill. No peer allocation, no account mutation, no computed
cash or net PnL after costs. Cost/risk exits are not evaluated by this component;
`netPnlAfterCosts` is null, not zero. Partial labels remain NO_GO and can never
qualify independent PAPER performance. The earlier adverse quote drift remains
relevant; no strategy/risk threshold was lowered to manufacture activity.

103 phase6 tests pass locally: 15 new kernel/binding tests include mixed routes,
share/collateral conservation, multiple orders/prices, queue prefixes, partial
allocations, duplicate components, cancel/activation ties, stale/future/old-source
prints, GAP recovery, exact source binding and real saved evidence. Seeded
randomized stress covers 100 eight-order scenarios with five component bursts
each and per-component quantity conservation. Source/test/report/frozen spec and
acceptance hashes are recorded in the implementation manifest.

Commands: `python -m research.phase6.settlement_matching_lab --output /tmp/lab-off.json`
and the same command with `--enabled` and a distinct output. A lightweight CI
job runs the tests and reproduces both reports using only committed evidence;
no new market capture, large tape download or RPC is necessary.

Next: inspect CI component reports, then add a research-only CLOSED-LOOP replay
adapter into the existing account/execution engine, preserving reservations,
fees, risk exits, cancellation and GAP semantics. Labels must remain unavailable
to strategy decisions, and labelled aggregate liquidity must be replaced rather
than combined with legacy full-print credit. Full-depth queue assumptions and
counterfactual feedback must not be inferred from this top-book projection.
Only after a same-development closed-loop comparison can a justified strategy
candidate be frozen for new independent PAPER. Acceptance unchanged; LIVE locked.

## Research-only full-account adapter — 2026-10-18

Starting head e40ff8158f8d55701a80a041d76d09b57c4aeec3. Component CI
39104790561 succeeded; no overlapping jobs remain. Its disabled/enabled fixed
lifecycle results are calibration only, not closed-loop PnL. No new capture/RPC.

Implement a separate `SettlementReplayMain` OFFLINE entry point, never a service
property, SDK mode or production endpoint. Existing constructors/default replay
remain on the legacy path. Only the package-private research session constructor
can install offline labels on a fresh account. The adapter matches original
sequence/frame index, source/arrival, token/side/price/size and full tradeId SHA;
validates trusted exchange, unique groups/maker identities, integer share AND
collateral conservation and the complete logical tape hash. Missing frozen
bindings or changed observations fail closed. Other aggregate observations of
covered transactions are suppressed rather than double-counted with components.

Component fills now flow through the EXISTING AccountLedger, markouts, inventory,
unhedged timer, entry stop, cancellation, exit sizing and fee-aware taker exit.
No future receipt fields enter strategy proposals/decision inputs; only the
environmental execution outcome changes. Due cancellation and stale/GAP ordering
remain the existing engine preamble. Full recorded books, not the compact
top-book projection, seed the actual replay order queues. Hidden/cross-price
queue uncertainty remains explicit, and all labelled reports are permanently
development-only/NO_GO with partial coverage and independent qualification false.

Freeze source/config/acceptance/label hashes BEFORE the first complete development
comparison in `research/phase6/settlement-replay-freeze.json`. Compare normalized
baseline (must reproduce 52 submitted/zero fills) and one labelled candidate on
the SAME full fresh recording and configuration. This changes the execution
model, not strategy parameters. No holdout or acceptance changes, no new capture.
New Java tests cover component queue/conservation/dedup, cancel ties, GAP recovery,
book source ordering, loader/tape/binding validation and an actual ledger/risk
exit integration scenario using the same fee-aware sale as existing regressions.
105 phase6 Python tests pass locally, including deterministic label export/freeze
verification. Java 21/Maven are unavailable locally, so Java compilation/full
regression is delegated to the single GitHub workflow before comparison.

Next inspect `PAPER closed-loop settlement calibration` verification job before
its dependent comparison. If compilation/tests fail, fix the exact failure and
retain the failed-run record; no comparison result is valid until verification
passes. Then inspect `closed-loop-settlement-comparison` reports, net realized
PnL AFTER fees, residual inventory, drawdown, exits and risk stop. A positive
partial-label result would still NOT establish profitability or justify live.

## Full regression passed; complete comparison pending — 2026-10-18

Run 39112535160, frozen code b4d6dfccee46459b93342fe6f64f83d0f65d2473:
verification job 117631509526 SUCCEEDED, BUILD SUCCESS. Java module totals
132+11+5+1 = 149; Python phase2..6 totals 8+50+38+49+105 = 250; 399 passed,
zero Java failures/errors/skips. Full ledger integration test confirms the same
fee-aware risk exit and cash/fee accounting as the existing regression fixture;
that fixture is synthetic test evidence, NOT market PnL. Test artifact
12130209319; verified executor artifact 12131260627.

Dependent comparison job 117631806808 is IN_PROGRESS. It reuses the existing
full fresh development recording; no new capture or extra receipt queries.
Wait for its baseline/candidate reports before any overlapping replay or
strategy change. Both completed component and full-account workflows are now
manual-only to avoid duplicate runs on checkpoint updates. Default runtime and
acceptance criteria remain unchanged; experimental engine path is offline-only.
No new net PnL result yet. Next read `closed-loop-settlement-comparison` artifact
from this run, verify 52/0 normalized baseline reproduction and five consumed
frozen bindings, then report actual net costs, holdings, exits and stop state.

## Full-account comparison completed; measurement defect isolated — 2026-10-18

Run 39112535160 completed SUCCESS at 08:58:48 UTC (11:58:48 Amman), using
frozen source b4d6dfccee46459b93342fe6f64f83d0f65d2473. Artifact 12131536794:
ZIP SHA256 aca32600aa8840657616019ce02761caa985155f975bbd6de7ce5736aee276fc.
Exact original reports/comparison, original source freeze, non-alert account
audit, complete audit hashes and the bounded GAP proof are now archived in
`research/experiments/settlement-replay-20261018/`. Reports are NOT rewritten.

| Same full development tape/config | Baseline | Partial-label execution model |
| --- | ---: | ---: |
| Submitted orders | 52 | 61 |
| Execution fills | 0 | 3 |
| Cash | 500.00 | 499.15 |
| Net realized PnL after configured costs | 0.00 | -0.85 |
| Charged fees / settlement costs | 0 | 0 |
| Max drawdown | 0 | 1.20 |
| Completed pairs | 0 | 0 |
| Ending inventory / expiry residual | 0 | 0 |
| Risk breaches / halted | 0 / false | 0 / false |

All five frozen receipt bindings were consumed; 29 unique maker components,
500 venue shares = 5 allocated + 0 queue-absorbed + 495 unused. Candidate bought
5 shares at 0.64, then maker-reduced 3+2 shares at 0.47; -0.85 is the actual
ledger loss, not a markout estimate. These fills incurred zero costs under the
UNCHANGED configuration (maker fills, no merge); no hypothetical rewards or
rebates are credited. Partial offline future receipt labels are environmental
calibration, not causal live input, independent evidence or profitability proof.
Both results remain NO_GO; no independent PAPER capture is justified yet.

NEW correctness issue: old `PaperMetrics` allowed future fresh snapshots to
complete pending horizons even after an intervening GAP. Buy fill arrived at
1792269683761; affected pair GAP at 1792269684239, before its 1s horizon at
1792269684761 (source projection row 140300/frame 69124). Nevertheless original
report recorded 3 samples at each of 1s/5s/30s. At least the buy's three horizons
are contaminated. Exact validity/counts for the two sells have NOT been
recomputed; aggregate audit ALERTs omit token scope, so do not infer them from
those alerts. Do not optimize against the original aggregate markout PnL.

Measurement-only revision: scoped gaps invalidate outstanding affected horizons,
global gaps invalidate all, recovery never resurrects them, already observed
horizons/unrelated tokens remain intact. Invalid books and stale-depth intervals
also invalidate pending observations. Missing horizons retain reason-specific
counts, never fabricated zero returns. Wire both closed-loop ResearchSession
(including paired scope and suspension) and executor action ReplayRunner;
account/order/fee/strategy behavior is unchanged. Seven new Java regressions
cover scope, global recovery, freshness boundary/silence, stale incoming books,
invalid/regressing/future/crossed/empty snapshots, missing-count conservation and
paired session accounting. Java 21/Maven validation is pending on GitHub; local
runtime only supplies Java 17, so no claim of Java test success is made yet.

Preserve the completed experiment's original freeze in the archived directory.
Active `settlement-replay-freeze.json` is an explicitly versioned measurement
revision linked by hash to the old freeze, adding PaperMetrics/ReplayRunner
source hashes; strategy parameters, input, labels, fees, queue, risk and
`research/phase2/acceptance.json` remain identical. This is not holdout tuning.
Only a lightweight full-regression workflow is triggered, NOT another two-hour
capture or a duplicate full-account replay.

Local checks: phase2 8/8, phase4 38/38, phase5 49/49 and phase6 105/105 pass.
A local phase3 run has
46 passes plus two failures/two errors because Maven-generated HTTP execution
fixtures under executor-service/target are absent; it is NOT recorded as a
passing full suite. GitHub runs Maven first to generate these prerequisites.

First regression run 39116530182 on b69fbba: Maven BUILD SUCCESS, all 156 Java
tests pass (including seven new regressions), but phase3 downstream label tests
fail twice: zero markout labels / missing markout key. The synthetic
ExternalPaperHttpTest fixture jumped from a 504ms fill to a 5504ms book without
updates; the new stale censoring correctly rejects those horizons. Fix the
fixture with regular 1s fresh book updates through the existing 5504ms endpoint,
and assert two clean samples at both 1s and 5s. Keep original expected label
returns and production freshness limits unchanged; no market data rewritten.
Retain failed run/test artifact 12133010681 as diagnostic evidence. Re-run only
the small regression workflow after this fixture correction; no replay/capture.

Next: inspect `PAPER markout continuity regression` first and fix any concrete
failure. Once green, reconstruct clean markout coverage from original full
normalized events with explicit gap scopes (or one justified measurement-only
replay under the new frozen sources). Preserve -0.85 accounting as a regression
invariant. Broaden settlement route coverage before evaluating strategy changes;
do not claim that delaying entry improves performance using only five labels,
since shifted orders may merely fall onto unlabelled executions. Freeze one
causal strategy candidate on development before new independent PAPER; fixed
acceptance and LIVE lock remain unchanged.

## Measurement correction verified — 2026-10-18 09:48 UTC

Run 39116669304 on c3ee4bdd56453f2a4ce97e631ba10d3aba55a4c2 SUCCEEDED;
156 Java + 250 Python = 406 tests passed, zero Java failures/errors/skips.
Java module totals 139/11/5/1, Python phase2..6 totals 8/50/38/49/105.
The HTTP fixture now has genuine synthetic observation continuity; unchanged
expected .09/.15 markout label assertions pass. Artifact 12133001132 preserves
the Java test reports. Previous failure 39116530182 remains in history.

This verifies measurement/accounting regressions, NOT profitable market
performance. No full comparison rerun or independent capture occurred after
the fix: the only market-account result remains the archived -0.85 under the
original frozen development execution model, with contaminated original
markouts explicitly excluded from optimization. All jobs completed; no replay
is running. Next action remains the scoped clean markout/coverage investigation
above, not a duplicate two-hour capture or promotion to LIVE. PR #9 remains
draft and stacked on #8 then #7; acceptance unchanged.

## Frozen-fill continuity-only audit prepared — 2026-10-18

Starting head 1a4842af3056ab301c815d30f713a3c404700183, PR #9 still draft on
#8/#7. Fresh check: 39116669304 SUCCESS and no in-progress jobs. Do not repeat
the account comparison or a live capture. Instead scan the existing complete
normalized recording ONCE to audit all nine horizons of the three FROZEN
executions from the archived candidate report. This fills the missing scoped
GAP information without rerunning strategy/queue/account decisions.

New read-only `research.phase6.markout_coverage` validates full logical tape
SHA, sequential journal/run chronology, clean RUN_END, RAW/normalized frame
binding and observed binary pair metadata. It never computes new fills or
account PnL. Track each horizon through own-token fresh, non-crossed books,
paired/global GAPs, stale depth, regressed/future/empty books and missing data.
Each horizon gets an explicit VALID or missing reason and a source row/frame
reference. Missing observations never become zero returns. Report markout
numbers, if any, are labelled NOT account PnL. Original -0.85 cash accounting
and reports stay immutable; no new market performance result exists yet.

Use an explicitly conservative SAME_ARRIVAL_GROUP_CENSORING policy: GAP or
invalid depth anywhere in an arrival group prevents that group's affected
sample, even if a BOOK appears first. Newly injected frozen fills with
same-arrival uncertainty are censored. This is NOT asserted to exactly equal
Java event-by-event telemetry, and cannot improve execution/profit by relaxing
its model. It is a development data-quality audit, never qualification.

Freeze analyzer/test source, original report, labels, config and acceptance
hashes BEFORE the first full scan in `markout-coverage-freeze.json`; the prior
settlement execution freeze is unchanged. Nine new unit tests, 114 phase6 tests
pass locally. One small `PAPER frozen-fill continuity audit` workflow runs the
phase6 checks then downloads the already existing fresh recording, scans it and
uploads `frozen-fill-markout-coverage`. No JVM rebuild, new receipt RPC, account
comparison or capture. Wait for its report before another overlapping scan.

Next inspect per-fill 1s/5s/30s validity/reasons and their exact proof rows.
If clean horizons are absent, report coverage failure, not a zero-loss or
profitable strategy. Then broaden settlement execution labels/causal coverage
before proposing one strategy candidate on development. No holdout tuning,
acceptance/risk/fee/queue change or LIVE path.

Audit source bed655fb4dae8d2ed2fb05afa8f4620f314f312f is running once in
39120483374 (job 117654909499). Its 114 phase6 checks passed, recording download
completed, full scan in progress. Do not start another scan/account replay or
capture while it runs. Bounded buy-only cross-check against the committed
projection reproduces all three buy horizons censored by the paired GAP at row
140300/frame 69124; this does not settle sell coverage or replace full-tape
verification. Next read the `frozen-fill-markout-coverage` artifact from THIS
run and archive exact results/provenance. No new PnL result yet; -0.85 remains
the original development account result. All default trading code unchanged.

## Complete continuity audit: seven censored, two valid — 2026-10-18

Run 39120483374 on bed655fb completed SUCCESS at 10:49:41 UTC / 13:49:41 Amman;
114 phase6 checks passed. Artifact 12134390936 ZIP SHA256
a7b192044612f4fa331e76ad4af017b2741315018777d22e15fd3498412cdd76.
Exact report, frozen sources/inputs and provenance manifest are committed in
`research/experiments/markout-coverage-20261018/`. Complete source verified:
6,163,831 rows, logical SHA cd850df52d7f9994526603130f2942008f8f49ba80495d82b70dea66f0dc6d8b.

| Frozen execution | 1s | 5s | 30s |
| --- | --- | --- | --- |
| Buy 5 at .64 | DATA_GAP | DATA_GAP | DATA_GAP |
| Sell 3 at .47 | VALID | DATA_GAP | DATA_GAP |
| Sell 2 at .47 | VALID | DATA_GAP | DATA_GAP |

Seven of nine horizons are censored. Both valid sell 1s observations have mid
.465 and +.005/share markout, NOT account PnL. There are zero clean buy markout
labels and zero clean 5s/30s labels; this is insufficient entry-quality training
or strategy qualification. Original actual account net remains -0.85, cash
499.15, ending inventory zero. No account or strategy replay was performed.

The two causal GAP anchors both report `invalid_depth: Crossed final batch`:
row 140300/event 0 at 1792269684239 (source 1792269684169), expanded to the pair;
row 155412/event 0 at 1792269696284 (source 1792269696213). The normalized
recording establishes invalidation, but does NOT prove whether the source is
venue message sequencing, an omitted update or a local decoder problem.
Do not "fix" this by accepting crossed books or carrying stale depth forward.

Next collect the original RAW frames for one predeclared 29,045ms interval
from 1792269669239 through 1792269698284, including both exact GAP anchors.
`research.phase6.raw_gap_context` preserves original message text, RAW/normalized
frame IDs/timing and GAP event indices. Its normalized BOOK output is explicitly
a three-level diagnostic projection; original raw full snapshots retain depth.
History before the window is explicitly unreconstructed; require an observed
full snapshot before replaying raw deltas. Cap evidence at 32MB and fail closed
on changed anchors, wrong full-tape SHA, missing frames or truncation.
Source/spec/core decoder/acceptance hashes frozen before extraction in
`raw-gap-context-freeze.json`. Three new targeted extraction tests, 117 phase6
checks pass. Start one bounded evidence extraction only after the preceding
audit completed; reuse the existing recording. No account/capture/RPC run.

Next inspect actual raw snapshot/delta chronology and venue best-price hints at
the two anchors; implement a decoder change only if those messages prove one.
Preserve strict invalidation otherwise and broaden settlement route coverage
before strategy selection. Acceptance/risk/fees/queue and LIVE lock unchanged;
no holdout data used or candidate promoted.

## Original RAW cause reproduced; quarantine candidate rejected — 2026-10-18

Run 39124054704 on 6fda30d9e7f262321d589ab11d95457f9f73c9ec completed SUCCESS
at 11:41:46 UTC / 14:41:46 Amman, 117 phase6 tests. Artifact 12134459459 ZIP
SHA256 31b3186ae2ebe21d38158e157a401d600019ffa70c8471741c9c0cbedaa3dcea.
It contains 12,632 original RAW frames in the fixed interval, 29,231,302 retained
bytes, complete 6,163,831-row recording verified. Provenance/freeze archived in
`research/experiments/raw-gap-context-20261018/`. Preserve the compact 29 original
RAW rows needed for all four token cases, including actual full snapshots and
all causal prefix deltas, in `depth-group-probe-20261018/evidence.json.gz.b64`.

Concrete cause in BOTH anchors: one transaction's level addition and level
deletions arrive across several WS frames with the SAME source timestamp,
per-token hash and announced best bid/ask. The first update crosses the prior
snapshot; the two actual size-zero removal messages arrive 2–3ms later and
restore a non-crossed complete book. Do not describe this as missing deletions
or an atomic-array bug: the deletions are present, in separate real frames.
First anchor RAW 140299 -> deletes 140303/140305; second 155411 -> deletes
155415/155417. Existing source-order checks do not join these separate frames.

Tested one isolated default-off `depth_group_probe` using the same four original
snapshot/prefix cases. It keeps provisional levels quarantined, requires all
updates to share source/hash/top hints, expires after the unchanged 250ms
activation interval and waits for actual deletions. It never publishes a book,
creates fills, retracts historical GAPs or changes account/strategy behavior.
Six targeted tests cover default-off, actual deletions, changed hash/source/top,
timeout, stale/future clocks, hint-only rejection and independent per-mode clocks
on the four real cases. All 123 phase6 checks pass locally. Java code unchanged;
do not call this a new full Maven verification or independent PAPER test.

Important control: after reconstructing each group, compare ALL its price/size
levels with the next ACTUAL full snapshot carrying the same source/hash:

| GAP / token | Conditional group recovery | Actual full snapshot delay | Gain |
| --- | ---: | ---: | ---: |
| 140300 / 125...3268 | 3ms | 3ms (RAW 140312) | 0ms |
| 140300 / 885...4334 | 3ms | 3ms (RAW 140309) | 0ms |
| 155412 / 125...3268 | 2ms | 2ms (RAW 155421) | 0ms |
| 155412 / 885...4334 | 2ms | 2ms (RAW 155419) | 0ms |

Full depth agrees in all four, but the probe has NO observed latency advantage
over the existing full-snapshot recovery. Reject promotion/integration; no new
capture or account replay is justified for this component. These few selected
development cases do not prove a general safe recovery policy. The hash is an
opaque shared identifier, not cryptographically verified; current official
py-clob-client summary hashing also requires four fields absent from these WS
snapshots. No guessed metadata/hash is substituted. Official source checked
2026-10-18: https://github.com/Polymarket/py-clob-client/blob/main/py_clob_client/utilities.py .

Initial probe runner failed a prefix clock check because it reused the baseline
final row arrival for candidate initialization. Corrected the harness to use an
independent original snapshot clock per mode and added a recorded-case regression;
strict validation/TTL unchanged. Preserve initial failure and original freeze.
The active revision explicitly says it was updated after initial development
evaluation for that harness correction and the full-snapshot control; it does
NOT claim independent preregistration. Results are reproducible via
`python3 -m research.phase6.run_depth_group_probe --output NEW_REPORT.json`.

Current state: all jobs complete; 7/9 old markout horizons remain legitimately
censored, no new fills/account result, original net -0.85 and cash 499.15.
The raw investigation closes this proposed recovery detour without changing the
runtime. NEXT prioritize broadening settlement route labels across active-order
intervals, including both public BUY and SELL observations and exact shared
transaction volume, before testing an entry/hedge candidate. Predeclare bounded
selection before additional public reads; reuse recorded transactions. Do not
repeat the same two GAP scans, tune on holdout or relax acceptance/queue/cost/risk.

Prepared the NEXT bounded public-read selection BEFORE any new RPC in
`route-coverage-selection-20261018/selection.json`: first ten unique recorded
transactions (either side/either binary token, observed source after activation)
while original baseline order 4 was active, and first ten while labelled replay
maker exit order 14 was active. Twenty unique transactions, two receipts already
cached, at most eighteen new receipt requests plus read-only chain/block checks.
Reuse cached receipts and block results. Exact source rows, original samples,
activation/terminal diagnostics and context artifact SHA are frozen in the file.
This is explicitly stratified calibration on two known development intervals,
not representative market sampling, a strategy candidate or a holdout. The exit
still uses legacy public-print matching outside the five receipt bindings, so
its routing coverage particularly needs verification before trusting broader
account comparisons. No new public requests executed in this turn. Next fetch
only this selection and validate per-transaction route/volume conservation;
do not rescan the two-hour tape or expand selection after seeing receipts.

## Frozen entry/exit receipt collection prepared — 2026-10-18

Starting head bbd0bbba95ed9b8c0a1a37723510948c815d682f; PR #9 remains draft on
#8/#7, all existing jobs completed. Selection SHA256
e6a2a65813593fe454b6c4ceb85a52012845c668cfec6a8703f0f9e3128fe9c4
is unchanged from the preceding checkpoint. New `route_coverage_audit` reads
only these twenty unique transactions, reuses the two committed receipts and
same-block results, and caps fresh receipt requests at eighteen. Existing
read-only RPC allowlist remains chain ID / receipt / block only, with pacing.

Before public reads, freeze source/test/selection/cache/acceptance hashes in
`route-coverage-freeze.json`. Validate each selected observation lies in its
predeclared order's activation/terminal interval. Decode actual exchange groups,
validate integer share AND collateral conservation for BUY/SELL, DIRECT/MINT/
MERGE, and preserve unrelated-market groups without allocating them to this
binary pair. Identity ambiguity remains explicit; no weighted public-price
assumption, queue/fill claim or account mutation. Raw successes and errors are
checkpointed; same-selection output can be resumed without refetching successful
receipts. Three new conservation/cache/resume/negative-path tests passed;
126 phase6 tests passed locally. Only these Python files change, no JVM rebuild
or new two-hour recording. One small workflow fetches the frozen receipts.

Next wait for `PAPER frozen entry and exit route receipts`, inspect
`frozen-entry-exit-route-receipts/report.json`, archive raw evidence and compare
actual route/volume decomposition across ENTRY_BASELINE_4 and MAKER_EXIT_LABELLED_14.
If public reads fail transiently, retain successes and retry ONLY missing items
with the same selection; do not launch an overlapping full recollection.
Default execution/config/risk/queue/fees/acceptance remain unchanged. Original
partial-model account result -0.85 is not revised by receipt acquisition alone.

## Completed frozen route audit and coverage limitation — 2026-10-18

Run https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39128452814
succeeded at 12:43:29 UTC, source 24a8f439f41670c475bcaa472f2747e0f2a5f404.
All 20 selected receipts corroborate; each has one uniquely identified group
with exact integer share AND collateral conservation; zero errors. Requests:
18 new receipts, two block reads and one chain check, within the frozen budget.
126 phase6 tests passed in that run. No Java, runtime or strategy changes.

| Frozen cohort | Transactions | DIRECT shares | MINT shares | MERGE shares |
| --- | ---: | ---: | ---: | ---: |
| ENTRY_BASELINE_4 | 10 BUY | 78 | 922 | 0 |
| MAKER_EXIT_LABELLED_14 | 9 BUY / 1 SELL | 55.57 | 79.315186 | 0 |

These are volumes of actual public settlement groups, NOT our hypothetical
fills or queue allocations. They do not establish counterfactual priority
between direct and complementary routes. All twenty samples, including all ten
exit-interval samples, are token 885...4334. Consequently the predeclared first-ten
selection DOES NOT cover the own-token BUY prints that triggered the two modelled
SELL fills. Do not treat completed conservation as verification of those exits,
silently expand this completed experiment or rerun the account claiming new PnL.

Exact original artifact 12136753379, including report, selection and all twenty
raw receipts/blocks, is permanently archived as
`route-coverage-20261018/artifact.zip.b64`. Original ZIP SHA256
931df689a6775dd4deb5227f24d0b9205b228ede0501226f382357b1410c4cf1.
The pretty selection hash e6a2a658... and report canonical selection hash
98c7038b07323788effe9aeb54dee83ec382817da687be49cf40057a217dad04
are different JSON encodings of the same selection. Offline reproduction checks
the original ZIP hash, exact membership/size, frozen source/acceptance hashes,
canonical selection, every receipt decode and conserved route against the
original report. Run `python3 -m research.phase6.revalidate_route_coverage`;
zero network requests, no optional Keccak dependency (original topics retained).
Two added archive/tamper tests bring local phase6 suite to 128 passing tests;
this is not a new complete JVM CI result or PAPER qualification.

NEXT is a SEPARATE targeted diagnostic, frozen before further public reads in
`exit-trigger-selection-20261018/selection.json` (SHA256
fb4f4b7970c9e850fdf898f6a232ed2e29fb24fc18ff881d5043559654c141b7).
Retrieved and verified the existing original RAW-context artifact only; no new
market recording or public receipt requests for this next selection yet. Join
the two known exit execution clocks to their original TRADE events and RAW text:

| Normalized seq | Arrival ms | Public BUY shares | Model SELL fill | Original transaction |
| --- | ---: | ---: | ---: | --- |
| 153844 | 1792269694955 | 13 | 3 | 0xc8e07c1f9e610746c394fc146bb3b88eca85b8e76ef6980192330af7c590c5d8 |
| 153978 | 1792269695069 | 5 | 2 | 0xee2a2436ad21f798967970d6d97632706a952430adfc1f3546495b344b9a9ad4 |

Both are own-token 125...3268 BUY at .47, selected by the already frozen model
fill clocks, not receipt outcomes. Preserve the two complete original RAW and
normalized frames in `original-frames.json.gz.b64`; compare source times, token,
side, size, price, transaction ID, frame/sequence and lifecycle before querying.
Reuse the existing conserved-route decoder and allowlist, limit to two receipts
and necessary public chain/block reads; cache successes. Audit maker SELL .47
components, fees, exact shared volume and whether the initial queue of ten is
supported, explicitly distinguishing observed routing from unproven queue.
No account replay/qualification is authorized by this diagnostic selection;
first establish whether the legacy exit matching assumptions need correction.

No jobs remain running, no new fills/account replay and no independent test.
Original partial-model net after its recorded costs remains -0.85, zero pairs,
cash 499.15; that conditional model result is not promoted. Acceptance, risk,
queue, fee and strategy settings remain unchanged. Continue the focused missing
exit-trigger audit next; do not repeat the completed twenty receipts or GAP scans.

## Two original exit-trigger audit prepared — 2026-10-18

Starting bce47c165973449bc55786e633e4e89500f92c0a, PR9 draft on PR8/7;
all existing runs complete. `exit_trigger_audit` verifies the prior unchanged
two-transaction selection against both complete original RAW/normalized frames,
canonical RAW hashes and original account execution records BEFORE public reads.
Freeze code/tests/frames/selection/original account/acceptance hashes. Reuse the
existing receipt decoder, conservation and cache; only two fresh receipt reads
plus necessary chain/block checks. Report actual route shares, exact-price own
SELL-side DIRECT volume and actual maker/taker fees separately. Initial queue
ten is recorded, never inferred to be proven by conservation. Three new binding,
tamper, direct-price selection and ambiguity checks; 131 phase6 tests pass locally.
No JVM changes or new capture/account replay. Next inspect the one small
`PAPER two frozen exit trigger receipts` workflow and archive original evidence;
do not re-fetch the preceding twenty transactions. Account net -0.85 conditional
result, default runtime and acceptance remain unchanged. Not independent data.

## Exit trigger receipts complete; freeze account-model control — 2026-10-18

Run https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39132403617
succeeded, source 891e13c49afa8fb15848d03ba81a96c19deecf59. All 131 phase6
tests passed before two receipt reads. Both uniquely identified groups conserve
integer shares AND collateral. Exact original artifact 12138561972 is archived
under `exit-trigger-audit-20261018/`, ZIP SHA256
72c428ee7a3adbd8881bc86ebe1a52560e3462bbf9371163b78874e2482d36da.

| Recorded exit trigger | Actual route | Own-token SELL .47 DIRECT shares | Actual maker fee | Actual taker fee (raw collateral / 1e6) |
| --- | --- | ---: | ---: | ---: |
| seq153844, public BUY13 | DIRECT13 | 13 | 0 | .226680 |
| seq153978, public BUY5 | MINT5 | 0 | 0 | .087180 |

The legacy second SELL fill of two shares credited an entire public BUY aggregate
that actually matched a complementary BUY, not an own-token SELL. This is
unsupported DIRECT liquidity in that model. Receipt evidence does not prove our
hypothetical order could not redirect the taker, nor does it prove the original
initial queue of ten: leave counterfactual priority uncertainty explicit. Do not
manufacture a new account result by simply deleting the old second fill; remaining
inventory changes future orders, risk, costs and possibly taker liquidation.
Original -0.85 remains an archived conditional PARTIAL-model result, not a newly
validated realizable PnL. Actual taker fees above are not charged to virtual maker
orders; virtual account uses unchanged fee logic by its actual liquidity role.

`export_exit_covered_labels` revalidates original ZIP membership/hash, RAW/frame/
execution joins, selection, decoded receipts, summary and route conservation
entirely offline. It preserves the previous five label bindings exactly, adds
only these two preselected BUY-taker bindings and suppresses their aggregate
fallback through the existing offline research-only engine. No production model
or runtime setting changes; no permission to deploy future receipt labels live.
132 phase6 tests pass locally. Added a Java regression with queue ten: DIRECT13
can allocate three SELL shares, complementary MINT5 cannot fill the remaining two,
and only a subsequent actual DIRECT portion can complete them. That new Java
check is pending CI, not claimed as locally executed (local Java17, no Maven).

Freeze a SEPARATE full-account DEVELOPMENT control in
`research/phase6/exit-covered-replay-freeze.json` before either replay. Baseline
is the existing FIVE-label partial model; candidate is SEVEN labels, same engine,
full original development tape and account/config/queue/fees/risk. This is an
execution-environment calibration control, NOT a strategy candidate. Includes
current markout-continuity measurement code for BOTH variants; preserve original
zero-fill normalized baseline and all previous results. Verify exact compressed
input hash separately from decompressed logical tape hash, same config hash and
complete consumption of 5/7 bindings. Full-account replay captures subsequent
inventory/risk effects, not just the two trigger events. No acceptance edits,
holdout use or new PAPER recording. `PAPER same tape five versus seven receipt
labels` first runs full regressions, then ONLY these two justified account runs.
Wait for that workflow before any overlapping comparison. NEXT archive both
account reports and costs/residuals/exits; assess broader unlabelled settlement
coverage before proposing causal strategy changes or independent tests. Neither
variant can qualify for live or independent profitability from future labels.

Launched ONLY https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39132714883
at source d25c19a13afb55f8413af3d61846f8d4e666bd3c; full regression job
117690973311 is running before either account comparison. Do not overlap or
rerun. Local phase6 132 checks pass; local attempts at the broader Python
contracts require Maven-generated executor target tapes that do not exist in
this Java17/no-Maven environment (phase3 fails those explicit prerequisites).
This is not counted as full regression success and no test fixture is weakened;
the CI sequence correctly runs Maven verify BEFORE all Python phases.

## Five-versus-seven account control complete — 2026-10-18

Run https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39132714883
completed successfully at 13:58 UTC, source d25c19a13afb55f8413af3d61846f8d4e666bd3c.
Full CI passed 157 Java tests plus 277 Python tests = 434 total, including the
new SELL DIRECT/MINT regression. This resolves the local missing Maven fixture
prerequisite; no fixture or assertion was relaxed. Test artifact 12138408392.

| Complete same-tape account result | Five-label control | Seven-label correction |
| --- | ---: | ---: |
| Orders / fills | 61 / 3 | 61 / 3 |
| Final cash | 499.15 | 499.15 |
| Net realized PnL after applied costs | -0.85 | -0.85 |
| Applied maker fees / settlement costs | 0 | 0 |
| Max drawdown | 1.20 | 1.20 |
| Completed pairs / ending inventory | 0 / 0 | 0 / 0 |
| Last SELL2 fill time (arrival ms) | 1792269695069 | 1792269695159 |
| Receipt bindings consumed | 5/5 | 7/7 |

Correction REMOVES the unsupported MINT-based direct fill at 5069, but a LATER
still-unlabelled public BUY at 5159 fills the remaining two via legacy aggregate
matching. Thus same account PnL is not validation of complete settlement coverage:
the replacement is only 90ms later, at the same .47 price. Do not say the blocked
fill itself was reinstated, or that the second virtual fill is receipt-validated.
The seven-label component accounting conserves 518 venue shares = 8 allocated +
10 queue-absorbed + 500 unused across 33 unique maker components; only three of
the SELL shares are from those labelled components. Queue assumptions unchanged.
Markout continuity is now applied in both: 2 valid 1s samples, seven horizons
censored by actual DATA_GAP (1 at 1s, 3 at 5s, 3 at 30s). No clean new entry label,
no completed pair, no profitable/independent strategy result; keep NO_GO.

Exact original ZIP (both reports AND full audit logs AND comparison) is archived
as `exit-covered-replay-20261018/result/artifact.zip.b64`, artifact 12138763339,
SHA256 c3f46b928b6cb150356c44317737975bf8d798c9418af9b1015550889750dbb6.
Original comparison and provenance/test counts are adjacent. New offline
`python3 -m research.phase6.revalidate_exit_account_control` verifies the ZIP hash,
exact bounded membership, frozen source/config/acceptance hashes, both reports
against original comparison, execution records against original account audits,
coverage consumption and integer-decimal volume conservation, without any network
or account rerun. Two archive/tamper checks bring local phase6 to 134 passing.

Do not launch another full replay for just this later print. Instead freeze ONE
bounded completion of the remaining legacy exit-print evidence. Existing RAW
context contains exactly NINE unique own-token public BUY observations from
actual activation 1792269694445 up to (excluding) the FIRST actual invalid-depth
GAP at 1792269696284 / normalized seq155412. This censoring boundary is independent
of which later print would fill: it bounds any continued life of that old order
under unchanged gap cancellation. Nine printed transactions, two receipts already
archived, only SEVEN new receipts needed. No new tape/capture/GAP scan needed.

Selection and all nine unmodified RAW/normalized frame pairs are preserved in
`exit-window-selection-20261018/`. Selection SHA256
52ff778f09e50e73871b0905d69858da668a15864620d7937887009a390468ef.
This window is NOT the observed lifetime of baseline or seven-label order14;
keep their actual terminals recorded separately (5069 and 5159). It is a bounded
counterfactual evidence window censored by the independently observed GAP. Do NOT
change the earlier two-trigger or twenty-transaction selections. Select every
own-token BUY in the window, not just those having favorable receipt outcomes;
no subset dropping, post-receipt expansion or replacement. Reuse the two prior
receipts and decoder, cap fresh reads at seven, retain exact tx/source/price/size
bindings and conserved maker portions. Audit actual 5159 replacement plus all
possible later legacy BUY triggers before the GAP in one batch. Other routes
and coverage outside this window remain explicitly unresolved.

NEXT implement/check that bounded read-window collector (do not misrepresent the
window as an observed order lifecycle), then obtain only those seven missing
public receipts. No new public receipt reads or account replays were started in
this turn; all current workflows completed. Keep acceptance, fees, queue, risk,
default runtime and strategy unchanged. Neither partial future-label model is
eligible for independent PAPER qualification or deployment. Continue coverage
correction before any new strategy candidate, then freeze a causal candidate
before separate independent data and live PAPER testing.

## Frozen nine-observation collector ready — 2026-10-18

Starting ca0dce6cfc2e13a305ae46373b2d3320883d433e; PR9 draft, all current
jobs complete. New `exit_window_audit` validates all nine exact RAW hashes,
frame/sequence/event/source/token/side/price/size bindings against the unchanged
predeclared selection. A dedicated read-window collector deliberately does NOT
adapt the window into a fake orderDiagnostic or alter the observed terminal.
Seeds the two original receipts from their hashed archived ZIP; checkpoint gate
rejects changed resume selections before network. At most seven new receipts,
same public chain/receipt/block allowlist and pacing, per-block cache, raw
success/error checkpointing, unique group and share/collateral conservation.
Three new binding/window/tamper/cache/resume tests; 137 phase6 checks pass locally.
Freeze source/test/evidence/cache/acceptance hashes before reads. One small
workflow reads only this bounded batch. Next wait for its report before any
account replay; no strategy/fee/queue/risk/acceptance change or new PnL claimed.

## All nine pre-gap receipts complete — 2026-10-18

Run https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39141046777
succeeded at 15:34 UTC, source 2f79b49230b51d3a1a8764cf65126b651c0af177.
137 phase6 CI tests passed. All nine receipts and unique group conservation
passed. Exactly seven new receipts, one block and one chain read; prior two
receipts reused. Original ZIP archived in `exit-window-audit-20261018/`, artifact
12140998562, SHA256 0e856ae5da7aa679a06db38a877962125f62a3c1dc61a5492b52dc2eb8338b29.

| Arrival ms | Public BUY shares | Actual route |
| --- | ---: | --- |
| 1792269694955 | 13 | DIRECT13 (SELL .47) |
| 1792269695069 | 5 | MINT5 |
| 1792269695159 | 5 | MINT5 — the replacement fill was also unsupported DIRECT volume |
| 1792269695807 | 47 | MINT47 |
| 1792269695857 | 47 | MINT47 |
| 1792269696116 | 47 | MINT47 |
| 1792269696250 | 55 | MINT55 |
| 1792269696257 | 40 | MINT40 |
| 1792269696270 | 55 | MINT55 |

Total actual group shares: DIRECT13 and MINT301. Under the unchanged queue ten,
the one observed direct portion supports conditional allocation of three SELL
shares, NOT all five. No other selected own-token BUY supplies an actual direct
SELL before the first GAP; all eight are complementary BUY makers at .53. This
does not prove hypothetical redirect priority or hidden queue, which remain
explicitly unknown. Do not claim a new PnL or simply subtract two fills. Other
routes/intervals and any changed strategy decisions after the GAP remain partial.

Offline `export_exit_window_labels` validates original ZIP hash/membership,
selection/frames, decoded receipt matches and every conserved route, preserves
the old five entry labels and the next two exact labels, and adds ALL seven
remaining bindings (14 total), not a favorable subset. Frozen full-account control
is now seven versus fourteen labels on the SAME complete development tape/config.
Generic `compare_frozen_label_variants --freeze ...` verifies full source/input/
logical/config provenance and complete label consumption; no live/qualification
path. Existing seven-label result -0.85 is only the comparison baseline, not
validated realizable PnL. No strategy, fee, queue, risk or acceptance modification.

One justified `PAPER seven versus complete pre-gap exit labels` workflow first
runs all phase6 tests, then checks the exact executor artifact source commit and
ZIP digest and reuses the immutable Java binary from successful full 434-test
run39132714883. Java runtime/test sources remain unchanged, hashes frozen; no
need to rebuild identical Java. Only two account replays, seven-label baseline
and fourteen-label correction, capture leftover inventory, cancellations, exits,
actual liquidity-role costs and risk. All previous freezes/results preserved.
NEXT wait for that workflow's comparison before any overlapping run or candidate.
After export and fail-closed control tests, 139 local phase6 tests pass. No new
financial result yet, no independent data or profitability qualification; PAPER
only. Preserve both reports/full account audits and follow new inventory evidence.

Running control: https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39141370797
source132b9eb55eed83e6bb32d79bb0e3892ccce71f63, job117716324427. Offline
139 phase6 checks and reused executor source-commit/artifact-digest checks have
passed; account comparison is pending/in progress. Do not launch an overlapping
control or new capture. Next read `seven-versus-fourteen-account-control`, retain
baseline/candidate reports and audits, and measure net fees/holdings/drawdown and
the actual exit after the first GAP. Until completed, -0.85 is the OLD partial
model's result, NOT a new fourteen-label account result. No acceptance change.

## Complete pre-gap account correction reveals dust trap — 2026-10-18

Run https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39141370797
completed successfully at 15:51 UTC, source132b9eb55eed83e6bb32d79bb0e3892ccce71f63.
139 phase6 CI tests passed, and the reused executor's tested source commit and
artifact digest passed. Same complete development tape/config, 7/7 and 14/14
bindings consumed. No Java/runtime/fee/queue/risk/acceptance change in this run.

| Account result | Seven-label baseline | Fourteen-label correction |
| --- | ---: | ---: |
| Submitted orders / fills | 61 / 3 | 13 / 2 |
| Net realized PnL after applied costs | -0.85 | -1.80 |
| Ending cash | 499.15 | 498.20 |
| Fees / settlement costs | 0 | 0.01 |
| Max drawdown | 1.20 | 1.80 |
| Unhedged quantity at expiry | 0 | 2 |
| Ending inventory after actual resolution | 0 | 0 |
| Completed pairs | 0 | 0 |
| Entry suspended | false | true |

The corrected model buys five at .64 and sells only three at .47. The old SELL2
is no longer fabricated from the pre-gap public MINT aggregates. The remaining
SELL order is cancelled at the original DATA_GAP1792269696284; the original
recorded META at seq130093 contains minSize5. Residual two is below that current
model minimum: 557 DUST_AWAIT_RESOLUTION decisions and no successful taker exit.
`reduce` silently skips maker replacement below minimum; `executePending`
rejects subminimum quantity, so repeated RISK_SELL decisions cannot liquidate
it. Protective entry suspension starts after unhedged timeout, not because risk
was relaxed or drawdown threshold altered; riskBreaches remains zero. Two shares
survive until the real recorded resolution at1792269956849 paying zero to the
held token. Ending inventory zero is resolution, NOT a successful hedge/exit.
Loss arithmetic: maker sale3*(.64-.47)=.51, residual basis2*.64=1.28 lost at
resolution, existing redemption cost.01 -> TOTAL1.80. Component conservation:
814 venue shares=8 allocated+10 queue-absorbed+796 unused,49 unique components.
Markouts still affected by true gaps; neither model qualifies independently.

Exact original full reports AND full account audits AND comparison are archived
in `exit-window-replay-20261018/result/artifact.zip.b64`, artifact12141699475,
ZIP SHA256 0a7f87d7d0a4922392577cf557a816864c3d626c1ac271475aa73056d67636ad.
Original comparison, exact META/exit/actual-resolution proof and loss arithmetic
are retained beside it. A regression verifies original archive hash, bounded
membership, report/comparison equality, complete label consumption, actual zero
payout and monetary arithmetic. No account rerun or new receipt reads this turn.

Checked official venue documentation on2026-10-18:
https://docs.polymarket.com/trading/place-orders — API describes min_order_size
and rounded share validation; SELL market orders use shares, BUY uses notional.
https://github.com/Polymarket/agent-skills/blob/main/order-patterns.md .
These sources do not justify assuming this particular below-minimum SELL was
accepted; no orders were submitted to test it. Third-party claims of special
FOK exceptions are not validation. Keep the recorded minimum/model constraint
unchanged; no wallet, signed order, top-up purchase or invented dust liquidation.

NEXT strategy candidate is explicitly frozen BEFORE any candidate replay in
`research/phase6/residual-entry-risk-candidate.json`: CS-RESIDUAL-WORST-CASE-1.
Default-off entry veto, using ONLY planned size/prices and EXISTING available
exit-loss budget/redemption cost: q*max(firstBid,secondBid)+redemptionCost must
fit available exit-loss budget. A single leg may fill completely while its peer
never fills and no lawful exit exists. The known pre-entry quote5*(max(.34,.64))
+ .01=3.21 exceeds existing budget2.5; no fitted volatility/price threshold,
parameter grid, increased stake, weaker queue, minimum size, fees or risk cap.
Near-balanced .49/.49 quotes can fit, but whether any fills/pairs/profit remain
requires actual causal full-account replay, not this arithmetic example.

Implemented and tested only the pure research primitive `residual_entry_risk`:
default-off behavior preservation, enabled full-loss bound, exact cost/budget
boundary, finite/invalid fail-closed inputs and immutable original dust account
proof. 143 phase6 tests pass locally. It is NOT wired into ResearchSession,
streaming PAPER or default runtime and has produced NO strategy performance.
Next integrate behind an off-by-default research option with backward-compatibility
tests, preserve historical frozen source provenance (old verifiers currently
compare historical source hashes to worktree files), freeze the full candidate,
then compare fourteen-label control versus candidate on the same development
tape/config. Do not rerun the old partial controls or collect more receipts for
the already-complete pre-gap exit window. No holdout tuning; acceptance unchanged;
zero fills/no loss would still fail qualification. Future receipt labels remain
environment calibration only, never a causal signal or independent PAPER proof.

## CS-RESIDUAL-WORST-CASE-1 integration frozen — 2026-10-18

Starting b47cf9e5f0aa119015cb207c85fb2478f2d10908, draft PR9, all existing
jobs complete. Integrated the EXACT preregistered q*max(pair bids)+redemptionCost
<= existing exitLossAvailable entry veto; no parameter search. New private
constructor option defaults false through every old ResearchSession constructor
and every old replay path. Explicit ResidualRiskReplayMain accepts only control
or candidate, requires receipt-labelled fresh offline account; no service config,
HTTP endpoint, wallet or live/independent activation. Veto occurs only before
new pair reservation; no quantity/exits/queue/minimum/fees/risk-limit changes.
This is a per-entry bound, not a proof of portfolio-wide worst-case coverage
across multiple simultaneously resting pairs. Up to ten causal reject samples
and a decision counter are reported, no unbounded new trace volume.

Four Java regressions cover exact budget+cost boundary, default old constructor
versus explicit off, enabled rejection without cash loss, allowed near-balanced
entries, and rejection of service/malformed CLI activation. They are pending
Java21 CI (local Java17/no Maven), not claimed locally executed. 146 phase6
Python tests pass locally, including three new source-proof fail-closed tests.

Preserve exact pre-change ResearchSession and ClosedLoopReplay source text from
tested commit d25c19a13afb55f8413af3d61846f8d4e666bd3c in a hashed immutable
archive under `residual-entry-risk-20261018/` (compressed SHA256
ee7541f7755c53deaf4c05addce714e57f6e3bb4f29d7e9f089e5e8dd0aa8b81).
Historical offline account verification now verifies THESE original two sources
against UNCHANGED historical freeze hashes, not the later working tree. Only
those two exact archived source paths may use that proof; config/acceptance and
all other historical inputs remain strict current hash checks. Tampered archive,
wrong acceptance or unrelated code cannot fall back. Current replay freeze checks
CURRENT source bytes strictly; this helper is never used to validate current
candidate execution or waive its tests. All prior results/freezes preserved.

Freeze full current source/Java tests/labels/config/acceptance provenance in
`residual-entry-risk-replay-freeze.json` BEFORE first candidate replay. Same full
development recording and fourteen bindings in both modes, control must exactly
reproduce13 orders/2 fills/cash498.20/net-1.80/cost.01/drawdown1.80/expiry2/halt.
If not, stop; do not rebaseline silently. Candidate mode differs only in the
entry veto. Full Maven+all Python regressions precede both account runs. The old
markout-only workflow skips this explicitly `[residual-risk-control]` tagged
push because the dedicated workflow runs the SAME full regressions plus new
candidate checks; no duplicate Maven build. Ordinary/manual markout checks remain
enabled. NEXT inspect this one workflow before overlapping action. No new net
result yet; zero fills or no loss cannot qualify, future-labelled environment is
not independent PAPER proof. No holdout/capture/live action or acceptance edit.

Current run https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39150564740
at9465a301aa3de7e3b97537651869a383b79d46a1, verify job117743176915 is running
the full Maven+Python sequence. Markout-only run39150564712 is intentionally
skipped by the documented dedup tag; the dedicated full check is NOT skipped.
Wait for verification and `residual-entry-risk-account-control` before another
comparison. No new candidate account metrics yet; latest corrected control net
remains-1.80. Next archive default-off baseline reproduction and candidate's
net/costs/pairs/fills/expiry/risk/reject samples; a zero-fill result is NO_GO.

Verification job117743176915 has now SUCCEEDED:161 Java+291 Python=452 tests,
including all four new Java candidate/default-off/allowed-entry checks. Compare
job117743450294 is running on that exact tested binary. Verification provenance
saved in `residual-entry-risk-20261018/verification.json`; do not repeat tests or
start another account comparison while this one runs. No candidate PnL yet.

## Residual entry veto result: loss avoided, zero fills, still NO_GO — 2026-10-18

Run https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39150564740
completed successfully at17:47 UTC, tested source9465a301aa3de7e3b97537651869a383b79d46a1.
The explicit OFF control exactly reproduced corrected baseline13orders/2fills,
cash498.20/net-1.80/cost.01/drawdown1.80/expiry2/halt, as required; no silent
rebaseline. Full regression provenance remains161 Java+291 Python=452 passing.

| Same-tape account result | Guard OFF control | Guard ON candidate |
| --- | ---: | ---: |
| Orders / fills | 13 / 2 | 2 / 0 |
| Net realized PnL after applied costs | -1.80 | 0 |
| Final cash | 498.20 | 500 |
| Applied costs / drawdown | .01 / 1.80 | 0 / 0 |
| Entry risk rejections | 0 | 31 |
| Unhedged shares at expiry | 2 | 0 |
| Quantity pair-completion ratio | 0 | UNDEFINED (no fills) |

The candidate avoided the known toxic entry, but made NO MONEY and provides no
fill/pair/edge evidence. Record NO_GO_ZERO_FILLS, NOT profitability or permission
for independent promotion. Do not retune the budget upward, reduce share minimum,
queue, fees or acceptance to recover activity. Keep default-off research status.
Candidate consumed all14 environment bindings but had no matching own orders at
those observations; future-label coverage does not fabricate executions.

There was exactly ONE submitted candidate pair: BUY5 first token at.46 and BUY5
second at.38, same condition0x678cc...6dba7, submitted1792269711477. Actual
activation1792269711729, terminal1792269711983 DATA_GAP:invalid_depth for BOTH;
254ms active each, queue seed0, eligible direct print volume0. Public observations
were wrong-aggressor or before activation; no price-touch fills. Both orders
were cancelled, no pair fill. The large apparent edge (.46+.38=.84) and short
life warrant ORIGINAL book/source coherence inspection, not an assumption that
this is an executable16% opportunity or a justification to loosen risk. This
is a NEW interval, not a repeat of the two earlier GAP probes rejected for0ms gain.

Exact full reports/audits/comparison retained in
`residual-entry-risk-20261018/result/artifact.zip.b64`, artifact12145347002,
ZIP SHA256680a934c5e0d38d57cbd85a725052e0771f3a1fcfae7a3958a07a37d405d4bf7.
Original comparison, exact only-pair order/terminal diagnostics and bounded risk
samples retained adjacent. Regression verifies original hash/member/size bounds,
report/comparison identity, both14-label consumption, off-control loss, zero fills,
undefined ratio,31 vetoes,254ms lifetimes and explicit NO_GO. No missing ratio is
zero-filled into a success score. No further account replay or public RPC this turn.

Freeze ONE next diagnostic before extracting additional RAW evidence:
`risk-opportunity-context-freeze.json`, fixed window1792269709477..1792269713983
(4.506s:2s before submission,2s after cancellation), same two tokens and original
development tape. Keep complete original RAW frame text, original sequence/frame
joins and source timestamps, with existing bounded normalized-depth projection;
do not treat three levels as queue evidence. GAP sequence/source at this NEW
terminal are not known yet; don't invent anchors. Reused extractor must find the
exact terminal-time invalid_depth GAP or fail, and still verify the complete
original tape digest/chronology/clean end. Wrapper is generic by freeze path;
original raw-gap extractor, old windows and runtime unchanged. Tests cover both
frame/standalone GAP identity and rejection of wrong time/reason.149 phase6
tests pass locally; no new Java changes/build needed. One small workflow extracts
only this bounded context from the existing recording; no new capture or strategy
replay. Next inspect whether paired quotes were coherent and whether legitimate
source BUY/MINT candidates existed in the actual254ms active interval. No receipt
fetch or model change until original messages justify it. All strategies remain
unqualified; acceptance/queue/cost/risk/holdout policy unchanged, PAPER only.

Started only https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39155138746
at a01cb4b9e39c4329b48d30dcc5ba4ffd3df96902. Wait for
`only-admissible-risk-pair-context` before any second scan or strategy adjustment.
The candidate remains NO_GO_ZERO_FILLS, net0/no profit, OFF by default. Current
work did not launch another account comparison, new capture, public receipt reads
or Maven build. All source/results/next window are committed for continuation.

## Only-pair original context — 2026-10-18 19:35 UTC review

Run39155138746 succeeded (149 phase6 tests); original bounded context artifact
12147061686 is retained losslessly under `risk-pair-context-20261018/` with ZIP
SHA256 fddaeffc29f635b643d9e5ac715c33f85935155968bd6951b29b69c8ddfdbb36.
The complete6,163,831-row source hash is unchanged;2,259 original frame pairs
are retained. New offline proof verifies RAW hashes/frame joins, original full
snapshot top-depth projection, public trade identity, and actual order times.

At submission1792269711477 BOTH latest books have source1792269711392 and
arrival1792269711468 (85ms source age,0ms cross-leg source skew). Original full
snapshots at normalized sequences173337/173339 show A .45/.63 and B .37/.55;
own .46/.38 bids improve these bids by one tick. This interval is NOT evidence
of differently timed paired source snapshots, nor proof of executable16% edge.

Actual activation remains1792269711729, NOT activationDue1792269711727. Four
public BUY observations arrive during actual254ms active interval. Sources
1792269711664 and1792269711727 precede observed activation, so exclude both
from causal allocation without querying receipts. The two postactivation public
prints are B5.3@.46 (source1763, normalizedseq173610) and A24.818182@.54
(source1904,seq173728), with the shared179226971 prefix. Their aggregate
complement prices .54/.46 are NOT sufficient to reject/credit individual maker
components: mixed settlement prices must be decoded and volume conserved.

Cancellation is original GAPseq173753, source1792269711911, invalid_depth
`Crossed final batch` for both tokens. Full snapshots recover at1987,4ms AFTER
actual cancellation1983. Do not postpone cancellation, infer a missed fill or
repeat the previously rejected separate-frame recovery probe. No runtime edit.

Freeze exactly TWO new receipts before public reads:
`risk-pair-receipts-freeze.json` and deterministic original-bound `selection.json`.
Transactions410a752f...e2bb7db and1e24b3b6...e24e20a6 are bound to actual opposite
BUY orders and observed source/arrival/terminal intervals. New small workflow
runs153 phase6 tests then public chain/receipt/block reads only, preserves raw
receipts and checks exact integer maker-price eligibility for target BUY bids.
It NEVER grants queue priority/fills, recomputes account PnL, changes acceptance,
or launches Maven, another full-tape replay/capture. Existing collector's legacy
unrelated -.85 field is explicitly removed from this new report. If incomplete,
retain successful receipts/errors and resume only this frozen selection; do not
broaden requests. Next inspect its `only-risk-pair-two-receipts` artifact before
deciding whether any new account replay is warranted.153 tests pass locally.
Known economics unchanged: corrected control net-1.80, candidate net0/zero fills,
undefined pair ratio, NO_GO; default guard OFF, PAPER only, no holdout tuning.

## Two actual risk-pair receipts — 2026-10-18 19:43 UTC

Run https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39160036669
at frozen948f4ac9999da97d355356e778c57a753a67073c succeeded.153 phase6 tests
passed BEFORE public reads; exactly2 receipt requests,1 block request and1
chain identity read. Both receipts yielded one unique conserved matching group.
Artifact12148322208, SHA2565060cec3209b2b3d2f7929a09e349b08075f0b8064d7f942f1ba622201f775f2,
is retained in `risk-pair-context-20261018/receipts/artifact.zip.b64`, including
original receipts/block, selection, topics, full decoded report and summary.

| Actual public transaction | Actual maker BUY components | Own bid | Compatible raw shares |
| --- | --- | ---: | ---: |
| 410a752f...e2bb7db | MINT A5.3 at .54 | .46 | 0 |
| 1e24b3b6...e24e20a6 | MINT B19 at .46 and5.818182 at .450000017187499... | .38 | 0 |

Integer shares AND collateral conserve exactly in both groups. Prices compare
integer collateral to bid*integer shares, not rounded public prices. There were
NO price-compatible actual maker BUY components for our two bids in the two
postactivation observations. The other two public observations predate actual
activation, and both orders terminate at the proven GAP. This closes this
specific interval's observed direct/complement-route diagnostic without another
account replay. It does NOT prove hypothetical venue redirection/queue priority
or that every possible counterfactual strategy could never fill. No fills or
economic changes are inferred from settlement. Both account results remain
control-1.80 and guarded candidate0/zero fills/undefined pair ratio: NO_GO.

Two additional offline regressions re-decode original RAW receipts, reproduce
the conserved component summary without any network calls, and reject changed
receipt identity/ambiguous groups.155 phase6 tests now pass locally. Historical
full suite452 and this run's153 CI tests retain their original scopes/counts;
no claim of155 new full-build CI tests. Frozen audit code/selection unchanged.

Next work must address opportunity availability, NOT this already resolved
interval, API transport, queue loosening or a repeated two-hour run. Reuse the
saved untruncated transaction-linked censuses BEFORE requesting more data:
original84 and fresh590 necessary-condition examples across both quote policies
and route screens. For a FIXED five-share order and unchanged exit budget2.50,
redemption.01, the risk rule requires both bids<=.498 (.49 on a .01 grid).
Do not mistake these example quotes for actual submissions or use public
complement price alone as a maker-route binding. Census sizes can be depth-
clipped and its omitted dynamic risk/latency/queue constraints still apply.
Determine whether an explicitly predeclared market/entry selection candidate
has enough causal, risk-admissible observed activity BEFORE another account
comparison. Record quantity/metadata, actual pre-decision book state, decision
timing, activation and GAP exclusions; missing fields require bounded original
evidence, not optimistic defaults. No new parameters or candidate chosen yet;
do not sweep budgets, tune on independent data, or promote an idle guard as
profitable. Current model remains default-off research, PAPER only. Follow-up
continues because no strategy has met unchanged independent acceptance gates.

## Complete saved-census feasibility — 2026-10-18 20:31 UTC review

PR9 headc0317fe and all prior jobs checked first: none running. No duplicate
capture/replay/RPC/build launched. Added offline `risk_feasible_census.py` with
source/config/acceptance hashes a…26630 tokens truncated…Pure rule parity is not account evidence.

Explicit pre-observation enablement in fresh mixed-label offline ResearchSession
now routes entry through QW0, then canonical reservation/matching/ledger. Exits
use frozen argmax rule; TAKER_SELL no longer falls into maker WAIT branch. Both
POSITIVE_EDGE_COMPLETION and new POSITIVE_EDGE_EXIT recheck actual delayed FOK
NET against unchanged minimumEdge*quantity. Preserve overdue risk behavior,
loss/minimum-size/cash/data/depth checks and original resting/cancel lifecycle.
Original core/default/frozen files remain untouched: second small tracked patch
composes on immutable bridge copy and verifies every94-source hash. Default-off
FULL canonical report still matches earlier untouched-core proof exactly.

Synthetic canonical strategy tests: QW0 orders0.40/0.40,5 shares each; original
2x100=200 entry queues;300 fixture shares=200 queue+5 allocated+95 unused.
No holding injection. Keep books fresh, cancel unfilled peer at6571, ACK6821,
plan fee-positive sell only after ACK, actual execution7071 after250ms. Actual
synthetic fee0.08624, synthetic realized0.11376. THESE ARE TEST EXPECTATIONS,
NOT market/account profits. Adverse actual execution0.42 remains within limit
but net0.01474<original0.05 floor, so TAKER_NET_EDGE rejects, fees0, uncovered5
shares/cash498 persist. No invented exit or inventory erasure.

Five new Python regressions check exact ports, isolated build/default parity,
reject altered queue/fees/risk, missing net guard and market/live scope promotion.
Complete generated94-source Java17 compile succeeds. Native reports, independent
verification and final source provenance retained in frozen-strategy-profile-20261020/.
New Java21 CI repeats parity/synthetic integration, not a market capture/replay.

Next whole-account dependency: fail-closed canonical full-tape runner and coverage
audit.451 recovery labels are only one pair/window; missing full-source routes
must be identified, not counted as zero or combined with aggregate volume.
Establish complete coverage and transition parity before SAME-source full-account
baseline/candidate comparison, then freeze executable/config BEFORE independent
multi-market PAPER. No holdout tuning, acceptance edits or selected-snippet account.

No new market PnL: old selected conditional exit+0.11264 vs-0.03747; original
full control-$1.80 after costs,guard0/0fills,QW0 full market account UNKNOWN.
NO_GO, PAPER only, PR9 unmerged; follow-up continues. Unknown local old activation
archive preserved untouched. No new RPC, full original tape scan or market fill.

## Full-source label-coverage census prepared — 2026-10-20 Amman

Preflight checked cff52ff/PR9 and latest Actions:39330038356 COMPLETE SUCCESS,
278 offline tests350.063s, both native integrated source build/execution steps
successful. Downloaded artifact12223933817,14623bytes, ZIP SHA
a93fed68383898170d9faf05a40575e018880b5f14a5e698979f0780766628d0.
Independently reverified42 quote proposals/18 choices, synthetic queue/ACK/FOK
guards and default-off parity. All3 downloaded report contents equal retained
evidence. No overlapping Action, no repeated conditional exit experiment.

Next dependency implemented: streaming FULL original6,163,831-row tape coverage
census with exact compressed/logical hashes and offline-revalidated451 receipt
bindings/1,038 components. Census is NOT a full account or strategy replay.
Checks ALL journal chronology/tail/frame boundaries and complete consumption of
exact coordinate/arrival/source/token/side/price/quantity/public-hash/tx bindings.
Classifies each public observation once: bound group, known-tx duplicate
suppressed, scoped missing, other-market unbound, unknown-market unbound.
Other markets are explicitly UNBOUND, not silently passed to aggregate matching.

Persists EVERY missing identity in deterministic hashed compressed JSONL with
original coordinates and available tx fingerprint. Per-condition totals and
earliest blocker by reason; missing coverage never means zero volume/fills.
Bounded memory/output; exceeding cap fails, never truncates. No RPC/receipt
requests, orders, model fills or net PnL. Even zero missing cannot qualify the
single-pair partial adapter or authorize whole-account/independent/live replay.
Frozen code/workflow/config/acceptance hashes in full-tape-coverage-freeze.json.
Seven targeted regressions pass: exact identities, scoped/other/unknown missing,
duplicate-volume suppression, full tail/run/terminal integrity, unknown/unbound
frame events, missing tx identity and ambiguous/duplicate binding rejection.

Next: wait for coverage census output; independently verify count/digest/source
evidence, inspect earliest missing routes, reuse already-retained receipts before
new bounded requests. Establish fail-closed multi-market full-source runner and
transition parity BEFORE same-source/config/coverage baseline/candidate account
comparison. Freeze complete executable BEFORE independent PAPER; no holdout tuning.

No new market-account net: original full control-$1.80 after costs; old selected
conditional exit-$0.03747 vs+$0.11264, NOT full-account performance. Frozen QW0
full account UNKNOWN. NO_GO, PAPER only, acceptance/queues/fees/risk unchanged,
PR9 remains draft/unmerged; follow-up continues. Unknown dirty old activation
archive preserved untouched.

This census implementation's complete local regression:285 tests in280.195s, OK;
separate7 targeted cases in0.006s, OK. Frozen dependency hashes verified. Next
push launches ONE full-source coverage-only Action; actual coverage totals must
be read from its completed artifact, not inferred from fixture test success.

## Census protocol correction: preserve original scheduler TICK — 2026-10-20 Amman

Preflight current0f7dd3a / draftPR9, no overlapping Action. Run39336641679
FAILED at coverage parser after285 tests PASSED in322.708s, source download
digest correct. Only201-byte partial artifact12227265901 produced, no complete
coverage.json. Failure is parser contract, NOT new strategy/market performance.

Exact cause: census standalone INPUT_KINDS omitted canonical TICK. Existing
ResearchSession.accept explicitly supports standalone TICK but frame envelope
allows only BOOK/TRADE/TICK_SIZE/GAP. Pre-existing immutable capture-inspection
already lists28,743 RESEARCH_TICK, total6,163,831 journal rows and16,317 trades.
Retained original recovery context has109 timers; first original seq258642 at
1792269759067, data{}. All research kinds in original inspector now supported.
No guessed market/receipt data, new RPC or modified execution semantics.

Corrected census explicitly COUNTS standalone TICK, creates NO volume/fill from
timer, still rejects TICK inside frame, all unknown/unframed observations and
invalid original chronology. Unknown-kind errors now identify kind/sequence.
Added final equality to pinned ORIGINAL independent inspector for every journal
kind/count, total rows, four normalized market-event counts, trade and timer
counts. No full report/renamed missing artifact if source/count validation fails.

Ten targeted tests PASS, including ACTUAL retained timer and original inspector
vocabulary, no timer trade credit, framed-timer/unknown-type rejection and
tampered inspector-count failures. Corrected census-only source/test freeze
also pins original inspector hash. Original tape/451 bindings/1,038 actual
components unchanged; QW0/fee-positive rules, account config, queues/fees/risk
and acceptance unchanged. This is not a strategy retune or independent data use.

Next publish corrected census, run ONE replacement coverage-only Action, wait
for successful complete artifact before making coverage or whole-account net
claims. Reuse existing receipts; no duplicate captures/strategy experiments.
Then inspect missing routes and implement fail-closed multi-market full-source
runner before same-source baseline/candidate account replay, freeze executable
before independent PAPER. No manual holding, no zero-credit unknown liquidity.

No new market-account PnL: original control-$1.80 after costs; selected conditional
exit-$0.03747 vs+$0.11264 remains NOT whole-account performance. Full candidate
UNKNOWN, NO_GO. PAPER only, PR9 unmerged, follow-up continues. Unknown dirty
old activation archive preserved untouched.

Corrected census complete local regression:288 tests in275.584s, OK; final10
targeted cases in0.006s, OK, also check all original inspector research kinds.
Corrected freeze dependencies and unchanged acceptance/account config verified.
No completed source scan or new financial result asserted before replacement CI.

## Complete original coverage result independently reconstructed — 2026-10-20 Amman

Preflight2328229/draftPR9 and run39342821835 COMPLETE SUCCESS:288 GitHub tests
in296.068s, full census succeeded. No active overlapping Action. Downloaded
artifact12228709938,1,594,521bytes, SHA256
882112d70db3b1926e235ebfd0a150fa5a3d6ffc40d0aac657358c9a2ed9a46e.
Retained exact2-member ZIP losslessly under full-tape-coverage-20261020/result/.
No repeated full-source scan, capture, strategy experiment or RPC in this step.

All6,163,831 original journal rows,3,000,583 RAW/frame pairs,20 metadata markets,
18 with trades;16,317 trade observations:BUY15,024/SELL1,293. Existing451
bindings/1,038 conserved components. Missing15,866 observations:4,219 scoped
pair +11,647 other markets. ALL missing tx hashes present and distinct; zero
known-tx aggregate suppression. Earliest missing at original seq97/event0,
arrival1792269588213/source1792269588056,BUY200@0.57. Unknown is NOT zero.

New independent verifier revalidates451 original receipt bindings offline and
every missing identity/coordinate/receive clock/pair-side-price-size/hash;
merges both original-coordinate streams to reproduce digest of ALL16,317 trades:
1f8d1d953f3755b8244c7ac11f7a3f72ccd8d73b1c9807b7cec417b6b710c1c2.
Not just matching counts or producer's coverage flag. Every journal/normalized
count incl28,743 TICKs equals immutable pre-existing original inspector. Actual
missing gzip logical/compressed hashes, first blockers and per-condition counts
reproduced; fails altered rows even if caller updates their local gzip hashes.

Indexed642 receipts from reviewed prior caches.191 MISSING observations have
an existing cached receipt CANDIDATE;15,675 missing tx outside THIS reviewed
cache. Presence is NOT new receipt corroboration, new labels, metadata pair
proof, queue allocation or PnL. No exhaustive all-repository cache claim.
Five new targeted regressions pass; new CI revalidates retained proof only,
without rescanning original20GB source or calling public RPC.

Next: rebind191 retained candidates where original metadata pair is proven;
establish native multi-market full-source runner/exposure coverage contract and
first execution-relevant missing route BEFORE blind bulk receipt collection.
Any no-order-irrelevance shortcut must prove canonical transition equivalence
and fail closed with any active/reserved/due/cancel-pending order, not silently
zero unknown volume; not implemented/authorized here. Preserve source frames,
timers, all cash/reservation/cancel/FOK/risk transitions. SAME-source/config/
coverage baseline/candidate full account comparison still pending; freeze full
executable BEFORE independent PAPER. Old control-$1.80 is prior-label baseline,
not expanded-coverage replay; never force matching it after coverage improves.

No new market-account net: selected conditional-$0.03747 vs+$0.11264 remains
not whole-account performance. Candidate full account UNKNOWN, NO_GO. PAPER
only, acceptance/strategy/queue/fees/risk unchanged, PR9 unmerged, follow-up
continues. Unknown local old activation archive preserved untouched.

Local complete result-verifier regression:293 tests in295.910s, OK; separate
five new targeted tests in7.313s, OK. ZIP SHA/blob identity and unchanged
acceptance/account config verified. Next push runs retained-proof-only CI,
not original source scan or market capture; wait for its proof artifact.

## ALL191 reviewed cached observations rebound offline — 2026-10-20 Amman

Preflight62d2233/draftPR9 and run39349192223 COMPLETE SUCCESS:293 GitHub tests
in336.566s; full retained source/cache proof outputs match. No active overlap.
No source rescan, capture, RPC or strategy/account experiment in this step.

Revalidated static original binary-pair metadata/causal lineage,451 old bindings,
all16,317 original trade identities and reviewed raw receipt cache. ALL191
previous missing/cached candidates re-decoded against exact source coordinate,
receive/source clock, public hash, token/side/price/size/tx facts. Exactly one
matching group per receipt, integer shares AND collateral conservation; no
new market pair guesses, failed-receipt skipping or outcome/price filtering.
Static later metadata identity NEVER substitutes for executable early metadata
freshness/fees/strategy decisions; no account execution performed.

Preserve451 original bindings/raw matches unchanged. Combined642 unique original
coordinates/txs,1,516 unique conserved maker components:1,150MINT+349DIRECT+
17MERGE. Additional191 groups contribute478 components:329MINT+141DIRECT+8MERGE.
BUY prices UP/SELL DOWN28-digit parity digest
3fd8f2d4ce916cd2a70919431e81ec878cb26e94ad7e293ff81e515f6bce092c.
Deterministic compressed pool201,377bytes/logical1,735,935bytes, retained in git
with frozen source/test/metadata/evidence/config hashes. No duplicated raw
receipt archive or new public read.15,675 observations STILL missing (4,028
first pair+11,647 others); earliest missing originalseq97 unchanged.

New pool is explicitly PARTIAL, NOT legacy CONSERVED-MIXED-LAB0 execution
manifest. allOriginalPairObservationsWithinWindow=false, native consumer=false,
fullAccountReplayAuthorized=false. Never forge completeness to reuse old adapter.
Read-only Python identity lookup checks actual original tradeId bytes and exact
coordinate/time/token/side/price/size/tx; unknown/duplicate observations FAIL,
never aggregate/zero volume. Not a consumption/queue allocator. Future native
consumer must enforce one-time observation/component consumption independently.

Six targeted tests PASS:all191/no selection, original451 exact preservation,
raw status/duplicate logs, unproven metadata rejection, saved pool/digest parity,
actual-source byte lookup and unknown/duplicate/scope failures. Default/native
strategy, matching engine, old adapter/451 manifest and acceptance unchanged.

Next strict native PARTIAL-pool consumer; verify ALL642/1,516 component tuples
and duplicate/unknown guards, then complete native original-frame/timer runner
and execution-relevance coverage proof before blind collection. No-order fast
path requires explicit canonical equivalence with no active/reserved/due/cancel-
pending order, not implemented here. SAME-source/config/coverage full baseline/
candidate comparison pending; freeze full executable BEFORE independent PAPER.

No new market/account net or simulated bot fills. Prior control-$1.80 after
costs and conditional-$0.03747 vs+$0.11264 remain prior DEVELOPMENT evidence,
not expanded-label account replay. Candidate full net UNKNOWN, NO_GO. PAPER
only, strategy/queue/fees/risk/acceptance unchanged, PR9 unmerged; follow-up
continues. Unknown dirty old activation archive preserved untouched.

Complete local cached-pool regression:299 tests in314.337s, OK; six targeted
cases in22.729s, OK. Frozen source/test/evidence/config hashes verified. Next
push runs one offline pool-proof CI, not source capture/scan or account replay.

## Strict native PARTIAL pool and isolated session hook — 2026-10-20 Amman

Preflight be81835/draftPR9; run39354913586 COMPLETE SUCCESS:299 GitHub tests
in372.989s, all191 cached candidates re-derived byte-exactly. No active overlap.
This step no original-tape rescan, market capture, receipt read or account replay.

Recovered EXACT original tradeId byte preimages for ALL642 pool observations
from retained source samples, each matching its source SHA256 AND normalized
token/side/price/quantity/source facts. Not tx-only substitution or invented
public print. Exact source-identity input SHA
2c849a88837b0724e71bfc02bcddbbfa28da238a5ee2fe4c7f325236b3501056.

New ConservedReceiptPool independent of frozen legacy adapters validates explicit
PARTIAL envelope, static metadata pair/condition, allowed exchanges, uint256 raw
amounts, unique sorted coords/tx/components, one DIRECT/MINT/MERGE group and BOTH
share+collateral conservation. Reuses unchanged canonical Binding/Portion record
types. Native actual consumption642/642 and ALL1,516 conservative BUY-UP/SELL-DOWN
28-digit tuples match Python digest
3fd8f2d4ce916cd2a70919431e81ec878cb26e94ad7e293ff81e515f6bce092c.
requireConsumed rejects incomplete/failed consumption. Every successful binding
consumes ONCE; ANY resolve failure poisons reader. Unknown ANY-token observation
throws, including covered tx at wrong coordinate; NEVER null/empty/suppressed
aggregate fallback.39 native rejection guards and2 extreme rounding boundaries.

New reader implements EXISTING generic OfflineSessionLabels research protocol;
no interface/window-adapter/core/frozen-policy edits, forged completeness or
service flag. Compiled ALL94 frozen research core sources plus helpers onJava17.
Uses unchanged a57c2fd integrated session variant. Full default-off native report
equals untouched-core oracle. Source-built session hook proven SYNTHETIC ONLY:
fresh500 ledger,QW0 0.4/0.4 q5, original250ms activation,2x100=200 queue;
300 fixture shares =200 queue+5 allocated+95 unused. Cash498,A5/basis2 WITHOUT
holding injection. Next known tx WRONG coordinate: ledger halt, cancel orders,
reader poison, further input rejection, already-booked cash/inventory unchanged.
These are fixture expectations, NOT market fills/profits/account evidence.

Independent verifier checks source+component digests, complete consumption,
partial/synthetic scopes, all original risk/fee/queue settings, synthetic volume
and halt/inventory guards, complete default-off parity and source provenance.
Five new targeted tests pass. New Java21 CI repeats native proof from retained
data, not a source scan/capture/RPC. Original producer artifact (consumer=false)
remains immutable historical claim; new proof separately attests native reader.

Next complete original-frame/timer native runner and exposure-aware coverage
proof, stopping at execution-relevant unknown before bounded receipt requests.
No-order optimization requires explicit canonical equivalence, no active/
reserved/due/cancel-pending orders, and no unknown-as-zero venue claim. Not yet
implemented.15,675 original observations still unbound;642 adapter consumption
is NOT selected-snippet account simulation. SAME-source/config/coverage full
baseline/candidate replay pending; freeze executable BEFORE independent PAPER.

No new market account net. Prior control-$1.80 after costs and conditional
exit-$0.03747 vs+$0.11264 remain prior DEVELOPMENT, not expanded-coverage account
results. Full candidate net UNKNOWN, NO_GO. PAPER only, acceptance/risk/queues/
fees/frozen strategy unchanged, PR9 draft/unmerged, follow-up continues. Unknown
dirty old activation archive preserved untouched.

Complete local native-pool regression:304 tests in310.135s, OK; five targeted
cases in1.432s, OK. Complete94-source Java17 native compile,642 identities/1516
tuples,39 rejection guards,2 conservative rounding boundaries and default-off
oracle pass. Frozen code/source/evidence/config hashes verified. Next push
runs one Java21 native-proof CI; no repeated original scan/capture/account run.

## Strict original-frame native runner and first-blocker diagnosis — 2026-10-20 Amman

Preflight bad4738/draftPR9:run39361402048 COMPLETE SUCCESS,304 GitHub tests
in355.498s;642 native original identities/1516 tuples,39 guards,2 rounding
boundaries, full default-off report parity. Exact4766-byte proof artifact retained
in full-native-runner-20261020/prior-native-proof.zip, SHA
47f99be2086583949100ca001de47ba753512f9b4484f1973edccd03d5109d7d.
Independent offline verifier also accepts the downloaded CI artifact. No active
overlapping run, no new capture/RPC or original coverage-census rescan.

New full_runner_build derives isolated NativeFullTapeReplay from EXACT original
ClosedLoopReplay.java046d30999a763d2735fa114562dae66c9bfd2e1f7bcbfac0953094938b3b466f,
using unique checked source anchors. Preserves the original parser/chronology:
seq/runId, arrival/source clocks, raw/frame envelope and original event indexes,
interleaved standalone timers, metadata, resolutions, gaps, recorded strategy
decision scheduling and original reservation/activation/cancel/FOK/risk paths.
No snippets/manual holdings/timer synthesis or unknown-as-zero/public aggregate
fallback. Adds explicit partial-pool session construction and frozen policy
enablement only. Original core untouched; generated session stays exact a57c2fd
frozen policy source; generated runner SHA
605407cb95ef0550fcc6d4ceac2c20cf31fe2f29cda3b7bb5eaf6d15dd80fde7.

Every parser/label failure suspends/cancels, writes diagnostic full ledger/session,
last attempted original observation+coordinate, cause chain and audit, then
RETHROWS. No completed report or net-PnL/qualification claim on failed prefix.
AuditedLabels delegates every resolve directly to strict pool; no null/empty
binding suppression, post-hoc fill or no-order optimization.

Complete local synthetic differential passes: WHOLE default report AND audit
identical to original ClosedLoopReplay;12-row fixture includes standalone timer
INSIDE raw/frame boundary. That timer correctly delays entry/activation; test
trade timing was corrected to follow canonical activation, NOT altering the
engine/recorded scheduling. Strict valid fixture consumes its label. Unknown
index1 after valid index0 in SAME frame halts/cancels, preserves fixture cash498/
A5; invalid frame ID also halts and writes failure. These are SYNTHETIC ONLY,
not market fills/account results. Nine targeted Python build/diagnosis tests OK.

Frozen full-runner-freeze.json ties code/tests/workflow, exact old compressed
source, immutable642 pool, full census, strategy/config/acceptance. One new CI
will check all regressions, compile source and repeat synthetic differential,
then download SAME unchanged original compressed tape (no new market capture),
verify its COMPRESSED hash and stream ORIGINAL prefix through both baseline and
frozen QW0+exit candidate. Expected first unbound seq97/index0. Verifier requires
EXACT tradeId byte hash/transaction/normalized facts/receive+source clocks from
the retained full census, strict reader failure, ledger halt/open0 and unchanged
configuration. JVM/parser/timeout errors cannot count as coverage evidence.

This is first-blocker diagnosis only, NOT full 6,163,831-row account comparison;
remaining15,675 unknown observations are not skipped or invented. No new market
account net; old control-$1.80 and conditional-$0.03747 vs+$0.11264 remain prior
DEVELOPMENT evidence. Full candidate net UNKNOWN, NO_GO. PAPER only, fee/queue/
risk/acceptance unchanged, PR9 draft/unmerged; hourly follow-up continues.

Next inspect first-blocker actual account/order state, then bound next receipt
request OR prove canonical no-order transition equivalence before optimization.
Blind collection15,675 not justified. Full SAME-source/config/coverage baseline
and candidate replay still pending; freeze executable BEFORE independent PAPER.
Unknown dirty original activation archive preserved untouched.

Complete local native-runner regression:313 tests in450.356s OK;9 targeted
new tests in0.048s OK. Complete Java17 frozen-source build and whole default
report/audit parity plus synthetic frame/timer/halt preservation pass. Frozen
files and generated runner hash verified. Original-source first-blocker
diagnosis PENDING CI; no actual-source account result inferred from fixtures.

## Original first blocker retained and one-receipt bounded follow-up — 2026-10-20 Amman

Preflight latest6e2dc1d/PR9 draft; no active overlap. Run39366694662 COMPLETE
SUCCESS:313 GitHub tests in364.806s, native whole default report/audit parity,
synthetic guards AND same original-source first-blocker diagnosis all pass.
Retained exact12,202-byte original-native-first-blocker artifact12239219391 in
full-native-runner-20261020/original-diagnosis.zip, SHA
5a251717de06ad26c2920180fcc5fa8ec4fad72d725f64f02f85d742833e74a4.
New independent verifier rechecks actual failure identities against frozen
full-census first-missing row, pool/config/freeze lineage, both strict error
chains, halted/open0, original config and SAME source for baseline/candidate.

BOTH policies stop seq97/index0, arrival1792269588213/source1792269588056,
original first-market BUY200@.57, transaction
0x12251c3fc5cc98f770892d16a115904cec18f729ffb7f15d2f8558beeea196fc.
Both retained ledger order histories, holdings, executions AND audit EMPTY;
cash500,fees0,realized0. This proves the first prefix created no orders, NOT
whole-account zero net, general no-order transition equivalence or permission
to skip this/other unknown observations. Full account result still UNKNOWN.

Added first_blocker_receipt: exact one-observation source/pair/condition-bound
selection derived from retained original tradeId BYTES. Frozen budget1 receipt
and1 matching block plus public chain ID. Read-only existing RPC whitelist,
no live/client/wallet paths. Raw receipt saved BEFORE block request/decoding;
resume reuses successful receipt, no silent fallback or fabricated labels.
Same existing corroborate/routes decoder must find a UNIQUE shares+collateral
conserved original group. Missing/failed/ambiguous data remains unresolved and
saved; cannot become model fill/account/qualification evidence. No642-pool,
core, matching, strategy, queue, fee, risk or acceptance edits.

Five new targeted tests PASS;21 relevant original-parser/receipt/route regression
tests in0.371s OK. ABI route fixture explicitly SYNTHETIC ONLY. Changed source/
selection, bad chain/status/duplicate logs, public-write exclusion and block-
failure receipt-resume guards covered. Unchanged full313 suite already passed
on GitHub; no repeated heavy replay/capture/census. New one-receipt CI pending.

Next retain returned raw receipt+block and independently decode/conserve it,
then explicitly freeze any expanded partial pool before advancing native replay.
General no-order equivalence still unproven; do not blindly fetch15,675. No
new financial result: previous control-$1.80 and conditional exit-$0.03747 vs
+$0.11264 remain OLD development evidence, NOT full candidate/independent net.
PAPER only, NO_GO, criteria unchanged, PR9 unmerged; follow-up continues.
Unknown dirty activation archive preserved untouched.

### One-receipt follow-up completed and retained — 2026-10-20 Amman

Run39388172877 SUCCESS on57e227d. Exact artifact12247259858,8160 bytes,
SHA5d8bf1e09bd0a5ed2210a43e256e90b0122c36dc48aeac36427f9ee528c956aa,
retained in first-blocker-receipt-20261020/artifact.zip. Exactly ONE public
chain ID/receipt/block call each, no original-source rerun or capture.

Independent first_blocker_result reads raw.json/report.json/selection.json from
the hash-checked bounded archive, revalidates exact original selection and raw
hash, re-decodes both ABI events and unique group with existing corroborate/
routes, checks EVERY reported integer part, and rejects financial/qualification
promotion or expanded request budget. Actual first missing transaction has16
maker components:200 venue shares and114 USDC taker collateral; DIRECT55 shares,
MINT145 shares. Original first-token SELL makers vs complementary BUY makers,
not doubled public aggregate volume. Counterfactual queue allocation UNPROVEN.

24 targeted local tests in0.589s OK, including3 new actual-artifact checks.
No model bot fills or market/account net created. Native642 pool UNCHANGED;
still15,675 native-unbound observations, now ONE more original raw receipt
available. Next derive explicit643 pool preserving ALL642 prior bindings,
freeze new manifest before native identity/tuple checks and original replay.
Do not relabel this selected receipt as full-source/independent account proof.
Acceptance, risk, fees, queue/frozen strategy unchanged; PAPER/NO_GO, PR9
unmerged, full candidate net UNKNOWN and follow-up continues.

## Expanded643 strict pool / native parity / next original stop — 2026-10-20 Amman

Preflight latestb1acb18/PR9, all prior runs completed; no active overlap. Added
ONLY proven original97 receipt to ALL642 parent bindings; parent artifact and
each prior binding unchanged. New separately frozen PARTIAL pool643/1532 actual
components (DIRECT354/MINT1161/MERGE17), native-unbound15,674. Zero new RPC reads,
no guessed metadata pairs/window completeness or legacy-adapter changes.

New expanded_receipt_pool reconstructs source-bound binding from retained raw
receipt+block and existing corroborate decoder, preserves original sort/identity,
rechecks global component uniqueness/integer tuples, and recovers ALL643 EXACT
original tradeId bytes. Native UNCHANGED strict pool consumes643/643; ALL1532
conservative28-digit BUY-UP/SELL-DOWN tuples match Python. Pool logical SHA
c41eda69ffe03ed06835a9fac403401f0d68aa3fa92b019bf37d410a212ee231,
source identity SHA27ac545988149c87bdfd4caee963100b7d10eb2808e6a74d82ae4b8321c65423,
tuple SHA f9a1bfd580ee26211d7b627407b428846d062967b379b42f253a4d640f198c29.
All39 original strict reader/session guards and2 rounding cases pass (37 pool
guards plus2 separate SYNTHETIC session guards; none omitted). Entire94-source
core plus research runner compileJava17; whole default-off report still EXACT
original oracle. Separate synthetic cash498/A5 fixture is NOT market profit.

29 targeted local tests in0.597s OK, including5 new exact parent preservation,
native643 parity, next-original identity/count/config/volume and no-promotion
checks. Prior full313 GitHub suite already passed; unchanged expensive suite
not repeated. Core/native reader/old manifests/frozen strategy/parser/queues/
fees/risks/config/acceptance untouched. New pool/summary/native proof/default
oracle comparison retained under expanded-receipt-pool-20261020.

Frozen expanded-pool-freeze ties exact new code/artifact/config BEFORE native
same-source replay. One CI rebuilds Java21 proof, then loads SAME unchanged
compressed original source and SAME643 pool/config for both policies. No new
capture/census/RPC. Processes original97 once, expects conserved200 venue shares
across16 components, strict halt at next missing original628/index0, source
1792269588824/arrival1792269588894, tx
0xab04630289f70e9cff07206d4ee31f5d291d73ba79bd4dd0c9281f0427d9ba90.
Original628 source-based identity chosen from existing full census, not tuning
on outcomes. Driver rejects wrong hash/clocks/count/config/volume, unrelated
failure, non-halt or financial/qualification promotion. Actual628 diagnostic
PENDING this CI; not inferred from local synthetic verifier tests.

Next retain actual next-stop account/exposure evidence, then prioritize explicit
canonical no-order transition equivalence rather than blindly/sequentially
requesting thousands of receipts. No such shortcut implemented/authorized yet.
Full SAME-source/config/coverage account comparison still pending; current
candidate full net UNKNOWN. Prior-$1.80 control and selected exit-.03747/+ .11264
remain OLD development evidence only. PAPER/NO_GO, acceptance unchanged, PR9
draft/unmerged, follow-up continues; user dirty activation archive untouched.

### Expanded643 CI completed / actual original628 retained — 2026-10-20 Amman

Run39395096777 SUCCESS on3e66649. Java21 ALL643 original identity/1532 tuple
parity,39 strict pool/session guards,2 rounding cases, full default-off parity
AND actual SAME-source baseline/candidate prefix all PASS. Artifact12251716484
15,048 bytes retained in expanded-receipt-pool-20261020/ci-artifact.zip,
SHA37f62ac28456837a107eb021c7f7716e57fb9662f05902dcab89d253e685513e.

New expanded_pool_result independently checks the retained archive and exact
643 source/native summaries against frozen source digests/default oracle,
recomputes next-original missing identity from full census, runs strict
verify_stop on BOTH native failures and compares saved same-source result.
Original97 consumed ONCE;16 unique components/200 venue shares conserve across
queue/allocated/unused. Both halt at ORIGINAL628/index0 with exact source/
arrival/tradeId bytes/transaction, same643 coverage and unchanged config.
Both prefix order histories/holdings/executions empty. No general no-order
optimization, full account zero net or market profitability inferred.

32 targeted local tests in0.756s OK, including3 new actual-CI retained proof
checks. No duplicate replay/capture/RPC launched for retention. Next explicit
canonical no-order transition equivalence deserves priority over thousands of
blind/sequential receipt requests; still NOT implemented or authorized. Full
account comparison and independent PAPER criteria remain unmet, candidate net
UNKNOWN. PAPER/NO_GO, queues/fees/risk/acceptance unchanged; PR9 unmerged.

## No-order execution differential / required counterexamples — 2026-10-20 Amman

Preflight latest3cc0cdb/PR9 draft;39395096777 and all previous runs completed,
no active overlap. Instead of blind/sequential receipt requests, implemented
BOUNDED PROOF ONLY. No original core/reader/policy/parser/default/runtime edits,
no original-source replay/census/capture/RPC. Strict original628 remains unresolved.

New NoOrderDifferentialProbe resolves ALL643 exact original byte identities with
unchanged strict pool and uses their1532 actual component tuples in4 explicit
SYNTHETIC book contexts each (missing books/fresh pair/stale pair/missing member).
2572 canonical acceptSettlement vs clock-only DIFFERENTIALS PASS with no matcher
orders: exact Update plus ALL private matcher fields compared EXCEPT precisely
settlementComponents/settlementVenue/settlementAllocated/settlementQueue/
settlementUnused. Reflection read-only, bounded test processes only. Full
matching-state equivalence is FALSE: known venue volume remains UNUSED, while
clock-only does not know it; unknown volume must NEVER be claimed zero.

For each case add later SYNTHETIC order with original250ms activation,2x queue
and DISTINCT future component IDs:2572 future continuations PASS, exact updates
and all non-settlement private matching fields. Test future fill-event counts
are SYNTHETIC expected events, NOT bot market fills/performance. Required negative
counterexample also PASS: SAME component reused later diverges because only
original path recorded consumed component ID. Therefore full source identity
index/global transaction uniqueness MUST precede any no-order witness. Legacy
public TRADE vs TICK also demonstrably differs through tradeIds/duplicates;
public aggregate fallback is NOT equivalent.

Read-only prototype predicate rejects12 unsafe contexts (submitted/due/active,
cancel pending/due, other-token order, ledger reservation, holdings, pending FOK,
failed/stopped session, halted ledger). This is not a production guard: future
implementation must be atomic in synchronized session/ledger/matcher execution
and include persistence-health checks and exact original identity validation.

Separate SYNTHETIC no-order session comparison passes3 checkpoints: whole ledger,
whole audit, whole session report except exactly2 explicit label/volume metrics,
all remaining private matcher fields. Later SAME two QW0 entries activate with
same reservation/queue state, and predicate refuses further optimization. No
general session-level equivalence claim or runtime authorization: flags FALSE.

Java17 complete95-source research build+helpers PASS;21 targeted Python tests
in0.282s OK,4 new no-promotion/counterexample/guard/source integrity cases.
New frozen Java21 CI repeats only bounded offline proof. No repeated market
data replay or receipt collection. Strict pool643/1532 and real628 blocker
unchanged; full candidate net UNKNOWN, no new account result.

Next full16,317 original identity index (frozen census+bound observations), raw
byte/coordinate/transaction validation with duplicate rejection on EVERY trade;
then explicit no-order witness (not null/empty label), atomic health/exposure
guard and separate unknown-unallocatable venue counters. Only then freeze and
advance SAME-source original replay to first execution-relevant unknown. No
shortcut currently enabled. PAPER/NO_GO, fee/queue/risk/acceptance unchanged;
PR9 draft/unmerged, follow-up continues; unknown user dirty archive untouched.

### Java21 bounded differential CI retained — 2026-10-20 Amman

39403569864 COMPLETE SUCCESS on613971e. Exact artifact12256497429,1580 bytes,
SHAe67795d44525b07945d51d9c434138845db743d3644f6b4ccfef5fca6bcd5d27,
retained in no-order-differential-20261020/ci-artifact.zip. Independent local
verification of DOWNLOADED Java21 proof equals retained verification.json:
2572 no-order matcher differentials +2572 distinct future continuations,
12 conservative predicate rejections,3 synthetic whole session/ledger/audit
checkpoints AND repeated-component/public-print divergence counterexamples.
No runtime optimization/source replay/RPC/account comparison was introduced;
original628 still unresolved. Next full identity index + atomic healthy-session
witness, never empty labels/zero unknown venue volume or acceptance changes.

### Complete original identity index foundation — 2026-10-20 Amman

Checked current branch f708a94 / draft PR9 and completed Actions39403569864 and
39395096777 before work. No overlapping source replay, capture or receipt job.
Reconstructed ALL16,317 original canonical identities from the retained complete
census missing stream plus451 original conserved bindings. Exact logical digest
1f8d1d953f3755b8244c7ac11f7a3f72ccd8d73b1c9807b7cec417b6b710c1c2
reproduced. Joint global checks find16,317 distinct transaction hashes AND16,317
distinct public identity hashes, including the previously bound451; none absent
or repeated. Historical coverage classification is preserved, not promoted.

New complete_source_index.py provides a fail-closed PYTHON REFERENCE consumer:
immutable owned identities; seq/frame index/arrival/source/token/side/decimal
price/quantity/exact original tradeId UTF8 hash/transaction validation; strictly
ordered single consumption. Unknown/duplicate/reverse/mutated/missing input
poisons the reader. Full mode cannot skip observations. Separate explicit subset
mode validates ALL643 retained actual raw preimages but MUST reject complete
consumption; it does. Other15,674 raw preimages were NOT fabricated or consumed.
Index facts are bound to exact previous full source digest, not a new source scan.

Local29 targeted tests PASS in18.378s (8 new test methods, including12 index
mutation subcases and exact-byte/normalized/clock/coordinate/poisoning guards).
An initial test assumed the earliest retained preimage was later than census
start; actual original97 IS the first row. Corrected the assertion to a later
observation; implementation unchanged, final full targeted run PASS. Frozen
bounded offline GitHub workflow adds no engine dependency/capture/RPC/replay.
Proof retained in complete-source-index-20261020/proof.json and reproducible.

This step is NOT a native Java identity consumer, no-order witness, atomic
session/exposure/persistence-health guard or runtime optimization. Strict real
baseline/candidate remain stopped at628; full account net remains UNKNOWN.
No new economic result, no aggregate fallback, empty bindings or zero unknown
venue volume. No original core/helper/policy/fee/queue/risk/acceptance change.
Next: native complete-index consumer with the same poisoned consumption rules;
then atomic synchronized healthy-empty-account witness plus separate unknown
unallocatable venue counters, with counterexample regressions retained. Freeze
before advancing same original source; stop on first execution-relevant unknown.
PAPER/NO_GO. Independent acceptance not met, follow-up continues; user dirty
activation-result/artifact.zip.b64 untouched. No new market capture or RPC.

### Complete source identity CI retained — 2026-10-20 Amman

39410095950 COMPLETE SUCCESS onfdb3f97:29 targeted offline tests in12.713s;
independently rebuilt proof matches retained local proof byte-for-byte.
Downloaded artifact12259190881,724 bytes, SHA256
68f841a1c2a703a8cdfeb86516f8c153fb4e902182b9a74772d2941d38ca8b6c
retained in complete-source-index-20261020/ci-artifact.zip with provenance.
Exact downloaded proof.json again matches local reconstruction. Original16,317
joint identities unique;643 actual preimages matched only as subset. No source
replay, no execution/no-order skip, no account net or qualification promotion.
Next native index consumer + atomic healthy-session witness; original628 remains
the strict execution coverage stop. No new market/RPC job or changed criteria.

### Native complete source identity consumer — 2026-10-20 Amman

Reviewed latest864a50b/draftPR9 and completed39410095950/39403569864/39395096777
before work; no active overlapping capture/replay. Added standalone research
CompleteSourceIdentityIndex.java, NOT registered as a label adapter/runtime
policy. Requires exact COMPLETE8,364,298-byte original canonical census SHA
1f8d1d953f3755b8244c7ac11f7a3f72ccd8d73b1c9807b7cec417b6b710c1c2.
All16,317 rows/coordinates/clock/schema/global transaction+public-ID uniqueness
checked before use. Immutable identity records/maps, synchronized consumption;
original seq/index/arrival/source/token/side/decimal price/size/exact UTF8 raw
tradeId hash/parsed transaction checked. Every consumption/finalization failure
poisons instance. Constructor rejects changed source before a reader exists.

Explicit diagnostic subset mode matched ALL643 exact retained original raw
preimages, then rejected completion and continuation. Default full mode matched
original97 but rejected jumping to next retained known receipt preimage across
the missing628 observation. It did NOT replay628 or reject it as invalid data.
No other15,674 raw preimages fabricated/consumed; source index is not settlement
coverage.23 rejection guards PASS:21 input/finalization cases plus poisoned
continuation and changed complete source bytes. No synthetic orders/fills.

Standalone two-file Java17 compile+native probe PASS; independent Python proof
verifier PASS;33 targeted Python tests in60.244s OK (4 new no-promotion/source/
subset/guard methods). Added bounded Java21 GitHub workflow with pinned existing
dependency JAR SHA bfc7bef081927f774374f92e5443c197e308e4828983dd9c19ac0ef280c45963,
no complete core compile/capture/source rescan/receipt requests/repeated market
replay. Freeze+local native proof+verification in native-source-index-20261020.

Actual strict baseline/candidate still stop628; full candidate account net
UNKNOWN. No original core/session/parser/helper/receipt pool/frozen policy/fee/
queue/risk/acceptance changes. Native identity reader complete as standalone
research only; runtime skip/atomic guard/session integration all still FALSE.
Next explicit no-order witness and atomic synchronized healthy empty-session
guard INCLUDING persistence health, all orders/pending actions/reservations/
holdings and per-trade identity check before expiry/filter; separate honest
unknown venue volume counters. Never null/empty labels or public fallback.
Keep repeated-component and public-TRADE-vs-TICK counterexamples. Freeze and
validate before SAME original source advances to execution-relevant unknown.
PAPER/NO_GO, independent acceptance unmet; no new net PnL. Unknown user dirty
archive preserved, PR9 draft/unmerged; follow-up continues.

### Java21 native source index CI retained — 2026-10-20 Amman

39417026089 COMPLETE SUCCESS on603f287:33 targeted tests in12.449s, standalone
Java21 compile and643 exact original preimages/23 guard cases PASS. Downloaded
artifact12262047950,1358 bytes, SHA256
d55fe31207cac39b926604fa6c2615cc2392e0db0b5206c7380865869f699daa
retained in native-source-index-20261020/ci-artifact.zip with manifest. Bounded
two-member ZIP verified; independent Python verifier reproduces CI verification,
and parsed Java21 proof equals local Java17 proof (JSON field order may differ).
No capture/RPC/full source replay/account simulation. Current actual original
628 stop remains. Next atomic synchronized healthy-empty-session witness and
integration before expiry/filter, not more early receipt collection; never skip
exposure, null/empty bindings, aggregate fallback or unknown venue volume as0.
PAPER/NO_GO. No new net result/independent qualification or acceptance change.

### Atomic healthy-empty-session witness — 2026-10-20 Amman

Reviewed latest852fea4/draftPR9 and completed Actions39417026089/39410095950/
39403569864 before work. No overlapping market capture/source replay. Added
EXACT copied-source atomic_guard_build.py, changing only FOUR generated classes,
not original core or frozen policy/fees/queue/risk. Guard callback holds locks in
session→ledger→matcher→checkpoint order for eligibility AND callback. Generated
ledger/state close use owner monitors; persistence health rejects closed locks,
channels, failed writes, restored ledger and recovered session checkpoint.

Package-private callback witness cannot survive callback return/exception,
another thread, or lost monitor ownership. Refuses any matcher order (including
submitted/due/cancel pending/due/another token), pending FOK, residual unhedged
timer, ledger reservation, nonzero shares OR basis, external/failed/stopped/
halted state and unhealthy persistence. Due cancellation/activation is NOT
advanced to manufacture eligibility.22 rejection fixtures PASS without changing
matcher/account state; actual temporary-path write failures exercised, not just
mock healthy booleans. Four competing monitor threads blocked then released;
cross-thread and escaped/exception witness reuse rejected. Tests SYNTHETIC only.

Local complete95-source generated Java17 build+helpers PASS.37 targeted Python
tests in20.585s OK (4 new source-integrity/lifetime/scope/health tests). Whole
DEFAULT oracle JSON unchanged. Existing2572 no-order execution differentials +
2572 distinct future continuations,12 prototype unsafe contexts,3 synthetic
whole session checkpoints and required repeated-component/public-print
counterexamples rechecked under new generated guard build: PASS. No fabricated
market fills/net; earlier synthetic expected fill counts remain fixture-only.

Proof/freeze/README retained in atomic-guard-20261020; bounded Java21 workflow
compiles same isolated sources and repeats proof/default/counterexamples, not
market replay/RPC. Callback is NOT a registered execution path or generic runtime
optimization permission. Native identity reader still NOT integrated with this
callback. No unknown observation skipped, no null/empty labels/public aggregate
fallback, no unknown venue volume assumed zero; original628 stop unchanged.

Next bind EVERY original trade identity before expiry/filter, use scoped witness
only for exact clock-only operation, preserve original frame/advance-action
order and honest separate unknown-unallocatable venue counters. Freeze/test
that integrated path before same-source replay advances to execution-relevant
unknown; do not repeat captures or collect each early no-exposure receipt.
Full candidate account net UNKNOWN; no new financial result/independent pass.
PAPER/NO_GO. Acceptance unchanged; PR9 draft/unmerged, follow-up continues;
unknown user dirty archive preserved.

### Java21 atomic guard proof retained — 2026-10-20 Amman

39424638964 COMPLETE SUCCESS oncdcffc6:37 targeted Python tests in22.406s,
Java21 complete isolated core/helper compile,22 actual synthetic guard refusals,
four monitor contention/lifetime checks, whole DEFAULT parity,2572 no-order
differentials/continuations plus required reuse/public-print counterexamples.
Downloaded artifact12264504808,3927 bytes, SHA256
92ea7aab6c79ca8caca73157e1fed917843bd5dd8fa863c4b32783ace066fe20,
retained in atomic-guard-20261020/ci-artifact.zip with provenance. Bounded five
members verified independently: guard proof equals local Java17; guard and
differential verifiers reproduce downloaded verification; DEFAULT JSON equals
original oracle. No original market source replay/RPC/new account economics.

Integration caution confirmed by source inspection: original TRADE becomes
TICK on expiry BEFORE old pool resolve. Future complete identity consumption
must occur before this branch; do not silently bypass identity or relax old
pool.requireConsumed. Specify/prove expired-known binding accounting separately
while preserving original expiry/clock/frame behavior. The atomic callback is
available only in isolated generated sources, NOT yet a clock-only runtime
operation. Original628 still strict stop; full net UNKNOWN. Next frozen exact
identity+witness+separate unknown venue accounting integration, no fake labels,
no independent qualification or changed criteria. PAPER/NO_GO, follow-up continues.

### Frozen indexed atomic execution integration — 2026-10-20 Amman

Reviewed latest5d05875/PR9 and completed39424638964/39417026089/39410095950,
no active source replay/capture. Integrated complete full-sequence source index,
exact643/1532 real pool and scoped atomic witness ONLY in generated research
session plus explicit IndexedReplaySupport CLI. No original core/parser/helper/
policy/fee/queue/risk/acceptance edit. Original frame/advanceActions positions
remain byte-identical outside exact new TRADE branch and explicit opt-in.

Every original TRADE identity now validates BEFORE expiry/filter; execution uses
owned input copies. Known nonexpired observations use REAL conserved bindings.
Known expired observations still consume actual pool binding but use canonical
TICK, with known-expired component quantity reported separately, not as matching
venue volume. Old pool.requireConsumed remains intact; wrapper additionally
requires COMPLETE16,317 original index consumption. No missing/duplicate/frame
identity allowed, and failures halt/cancel/block session continuation.

Unknown observations use explicit Unbound route, never empty/null Binding or
public aggregate TRADE. Exact canonical TICK is permitted only inside healthy
GLOBAL empty-exposure atomic witness. Counts/public observation sizes recorded
separately; unknownVenueQuantity=UNKNOWN_NOT_ZERO. Matching conservation carries
explicit KNOWN_NONEXPIRED_COMPONENTS_ONLY scope, never misleading total volume.
Source-wide transaction uniqueness prevents skipped component reuse; prior
required counterexamples remain mandatory. Failed wrapper cannot continue.

Local generated96-source Java17 compile+helpers PASS;41 targeted Python tests
in32.124s OK,4 new integration/source/scope/expiry methods. Whole DEFAULT oracle
JSON unchanged.9 integration checks PASS over exact original97/628 raw preimages
but SYNTHETIC surrounding session/frame envelopes:97 real binding applied then
628 atomic clock when empty; exposure rejects628 and cancels; expiry validates
both identities and consumes known97 without settlement application; mutation
after expiry, duplicate, missing prefix, wrong actual frame index all halt and
block continuation. All fixture accounts remain500/no executions/holdings.
These are NOT market replay/PnL evidence; original full source frontier not yet
recomputed in this commit. Prefix raw SHA2842d45d1fc041fd7c1af8a6ed44403e9c0914e59eaf9c8e4b0515b504c6de8c.

Frozen indexed-execution-freeze.json pins new generated session/runner and all
runtime helpers/config BEFORE original source testing. New workflow first runs
unit/Java21 integration/22 atomic guards/default parity/2572 no-order differential
counterexamples; ONLY after success downloads existing original DEVELOPMENT
source ONCE and runs baseline then unchanged frozen candidate on SAME bytes.
CLI checks exact source gzip/config; incomplete run retains frontier, causes,
ledger and full queue/cancel audit, without financial result promotion. Complete
run must consume source16,317 and realpool643, with venue scope still explicit.
No independent/holdout/new capture/RPC data or strategy tuning. Next inspect
these actual reports, diagnose first execution-relevant failure before any new
bounded receipt read. Do NOT launch duplicate workflow. Full net UNKNOWN;
PAPER/NO_GO, PR9 draft/unmerged; user dirty archive untouched, follow-up continues.

### ACTUAL original replay advanced beyond628; pending-order frontier — 2026-10-20 Amman

39433713918 COMPLETE SUCCESS on frozen3d5310a:41 targeted tests in22.407s,
Java21 complete96-source/helper compile,9 integration checks,22 atomic guards,
whole DEFAULT parity and2572 no-order differential/counterexamples PASS BEFORE
original source download. Existing DEVELOPMENT recording downloaded ONCE, both
profiles replayed SAME source/config, no capture/RPC/holdout/fresh-paper launch.

Exact artifact12269456647,19375 bytes, SHA256
1eee8b222b52ecc49c21d4deebecc98b16a7530f614ce5978421071df26509d9
retained as ci-artifact.zip with all failure/ledger/queue-cancel audits. Offline
indexed_replay_diagnosis.py independently checks bounded22 members, local/Java21
proof equality, old default/atomic/differential verifiers, ALL original identity
facts at source census position, frozen config, known component volume and exact
submit/cancel chronology. New original-diagnosis.json is current frontier state;
older differential proof flags are historical bounded-proof scope only.

BOTH actual source executions pass628. Baseline consumes828 original identities,
826 unknown atomic clock observations +1 real known97; stops at original82652.
Candidate consumes87 identities,85 unknown clocks +1 known97; stops at8018.
The final observation identity is consumed but its unknown execution NOT applied.
Only known97 settlement volume200/16 components, entirely unused, is counted;
unknown venue volume remains UNKNOWN_NOT_ZERO, not public size or zero.

Important diagnosis: these are conservative PENDING-order stops, NOT evidence
that the frontier print could fill an active order. Baseline submits pair5@.24/
.71 at1792269639335, stops54ms later. Candidate QW0 submits pair5@.47/.48 at
1792269594252, stops20ms later. Activation remains250ms; BOTH recorded trade
source timestamps PRECEDE both order submissions. Actual audit confirms both
orders canceled at halt, no fills/executions/holdings, ledger cash500/fees0.
These stopped-prefix account values are NOT full net results or profitability.

Baseline frontier tx0xabb9930366c096c65dfc936150f834b0232419ce46ef4d2f7fccfe23135bd60f;
candidate tx0x9e0dfd50b48b5638e7ea9ab4ceba42d40e8fb680acdb2801498c1393af9a906d.
Do not blindly collect every early waiting-order receipt. Next prove the narrow
pre-activation/source-before-submit irrelevance case while preserving EXACT
activation/cancel/frame/action/queue semantics and persistence locks; retain all
unsafe active/due/cancel-due cases. Only after frozen differential proof may a
new generated guard accept that case. Otherwise collect bounded exact frontier
receipts. Existing strict atomic guard and frozen strategy remain unchanged.

No complete account comparison/independent acceptance pass/new net PnL. No
strategy retune, no relaxed risk/fee/queue/activation or criteria. PAPER/NO_GO;
follow-up continues; unknown user dirty archive untouched, PR9 draft/unmerged.

### PRE_ACTIVATION0 frozen bounded proof — 2026-10-20

Implemented a NEW generated-only temporal witness for healthy, flat sessions
with strictly pre-activation BUY orders and exact OPEN ledger reservations.
No pending cancellation, active/due order, SELL, inventory/FOK/unhedged exposure,
failed persistence, external mode or recovered checkpoint can use it. Selection
and callback hold session/ledger/matcher/checkpoint monitors; witness expires.
Old empty-order guard and all original core/helper files remain unchanged.

Local Java17 full96-source build,44 Python tests,5144 pending differential cases
and5144 future continuations,23 temporal rejection guards,8 integrated exact
original97/628 preimage checks, old22 atomic guards,2572 old empty differentials
and DEFAULT oracle equality PASS. Synthetic future fills128 are test evidence
ONLY, never market fills or profits. Queue200 from displayed100 times2 is checked
at unchanged250ms activation. Repeated-component divergence stays negative.

Freeze and evidence: research/phase6/preactivation-freeze.json and
research/experiments/preactivation-20261020/. New workflow repeats proofs on
Java21 before ONE reuse of existing original DEVELOPMENT tape for baseline and
unchanged frozen QW0 candidate. No new source capture/RPC/holdout/retuning.
No whole-account net result yet, no independent acceptance claim. Next inspect
that run instead of rerunning; retain actual frontier and queue/cancel audit.
If active/due/cancel-pending blocks, collect exact evidence, not weaker guards.
PAPER/NO_GO, PR9 draft/unmerged, acceptance/config hashes unchanged.

Published PRE_ACTIVATION0 freeze at886ee0ce0f3416ff394c85baca7b41f351f6986a;
new Actions39443362971/job118698743149 is RUNNING. No previous active run was
overlapped. Prior9 indexed integration/expiry/identity rejection tests also pass
on this generated profile. Check/await39443362971 reports before another replay;
no complete result or net claim while running. This status-only commit does not
touch workflow/freeze and must not trigger another comparison.

### PRE_ACTIVATION0 actual original result retained — 2026-10-20

39443362971 COMPLETE SUCCESS:44 targeted tests and all new/old Java21 proofs
pass before ONE reuse of original DEVELOPMENT tape. Both profiles STOPPED again
fail-closed:baseline original82880/836 identities/834 unknown clocks (8 new
pre-activation), candidate8739/94 identities/92 unknown clocks (7 pre-activation).
Previous frontiers82652/8018 passed. No complete account/PnL comparison.

New frontier is ACTIVE at arrival, but source time still precedes activation:
baseline active21ms, source49ms before activation; QW0 active4ms, source66ms
before activation. Baseline actual activation queues0/0; candidate1182.30/180,
unchanged at halt. QW0 decision-time proxies160/240 are NOT actual activation
queues. Both pairs canceled at halt, executions/holdings0; prefixcash500/fees0/
realized0 are NOT net results. Known original97 volume200 whollyunused; unknown
venue volume remains UNKNOWN_NOT_ZERO. No fabricated fills/financial claims.

Retained artifact12275333120,22389 bytes, SHA256
f8dd0c2754b5ee15d6f78240d63dfdaf1aed7617537e5836139f0d029d0a0902
at preactivation-20261020/ci-artifact.zip. preactivation_diagnosis.py reconstructs
exact source identities and checks raw hash/tx, config, queues, activation/cancel
audits, incomplete account scope and Java21/local proof parity. Two new tests
include3 mutations rejecting queue/activation/print changes. original-diagnosis
is the latest actual frontier; historical proof unresolved flags stay scoped.

NEXT: no unchanged replay. Prove narrowly source-time at/before activation
irrelevance even when arrival sees active orders, with canonical activation/
cancel/frame/queue semantics and required unsafe counterexamples, before ANY
new separately frozen guard; otherwise collect bounded exact frontier receipts.
Do not weaken active/cancel/health guards or tune QW0/holdout/acceptance. PAPER/
NO_GO; acceptance/config unchanged, PR9 draft/unmerged, follow-up continues.

### SOURCE-LAG bounded differential proof ONLY — 2026-10-20

Checked remote8f21e30/PR9 still draft and previous39443362971 COMPLETE SUCCESS;
no active workflow, no overlapping experiment. New proof targets source-time
at/before actual activation, not new strategy/queue/fee/risk parameters.

SourceLagDifferentialProof.java compares actual643 conserved component tuples
in8 SYNTHETIC matcher contexts:early66ms/equal source on active order, due-at-
arrival, delayed actual activation, different-age own orders, cancel/activation
tie, pending cancel, stale book.5144 exact Update/non-settlement-private-state
differentials and5144 distinct future continuations PASS locally. Synthetic
futurefill111 is ONLY test coverage, not market/account PnL. All5 settlement
bookkeeping fields remain explicitly different/unknown, not zero venue quantity.

Required unsafe counterexamples PASS:source+1ms after actual activation CAN
fill; using newest/max activation misses an older eligible order; repeated
components change future fills. All orders must satisfy their OWN ACTUAL
activated times, with full-source global component uniqueness still mandatory.
Queue200 from displayed100 times2 and own-second-order205 remain intact;
cancel wins activation tie and stale book cancels canonically.9 reflected
proof-predicate rejection cases; NO atomic session guard implemented/authorized.

The new source-lag-proof workflow repeats proof+unchanged old guards/default/
indexed integration on Java21. It performs NO original-source download/replay,
RPC, market capture or holdout use. Existing runtime remains PRE_ACTIVATION0,
actual frontier82880/8739 unchanged, full net UNKNOWN. New proof is not a fix
installed in execution. Evidence/freeze/verifier under source-lag-20261020 and
research/phase6/source-lag-proof-freeze.json; no original core/helper changes.

NEXT: separately generated atomic source-lag witness with exact OPEN ledger
reservations,4 monitors, flat/healthy state, no cancels/FOK/unhedged/recovery/
external mode; actual-frontier synthetic-envelope integration and unsafe older-
order/source+1ms tests BEFORE one new frozen same-source baseline/QW0 replay.
Do not rerun unchanged PRE_ACTIVATION0. Strategy and fixed acceptance/config
unchanged, PAPER/NO_GO, PR9 draft/unmerged, user dirty archive untouched.

Local checks:50 Python tests PASS in32.735s (new verifier includes13 mutation
subcases), complete96-source generated Java17 build, old5144 preactivation
differentials/22 atomic guards and DEFAULT before oracle parity PASS. Await new
proof-only Java21 run after publication; no original source replay scheduled.

### Source-lag Java21 evidence retained — 2026-10-20

39450218277/job118722737363 COMPLETE SUCCESS on7d88f0655bb9c794937c9c0548f26ff21256930e.
50 targeted Python tests PASS37.346s, native5144 source-lag differential/future
cases and all prior preactivation/atomic/indexed/no-order/default proofs PASS.
No recording replay, capture, RPC, holdout or strategy parameter search.

Artifact12277499794,10611 bytes, SHA256
ca77279140a0d98592ced523556446e71c4ff941012b95e024ca3ed0ce1fb76e
retained source-lag-20261020/ci-artifact.zip. New source_lag_ci_result.py checks
exact13 bounded members, native/local equality and unchanged prior verifiers/
DEFAULT oracle;2 local retention tests. ci-verification.json records scoped
proof, NEVER runtime authorization or financial result. Whole matcher state
still differs in5 settlement bookkeeping fields. Synthetic111 future fills
are test coverage ONLY. Current actual baseline82880/candidate8739 stops remain.

NEXT separately implement+freeze atomic source-lag session witness preserving
exact ledger/monitor/health/cancel/holding constraints, then test original actual
frontier preimages in synthetic envelope plus unsafe older-order/source+1ms.
Only then justify ONE new same-source development comparison. No unchanged
replay/proof repeat; full net UNKNOWN, no independent acceptance, PAPER/NO_GO.
No workflow/freeze changes in evidence-retention commit; PR9 remains draft.

### SOURCE_LAG0 generated atomic guard/integration — 2026-10-20

Remotee7be0ae/PR9 draft checked, previous39450218277 and39443362971 COMPLETE
SUCCESS, no active jobs. Implemented NEW separately generated matcher/session/
helper profile; original/default code and old witness methods unchanged.
Each already-active BUY checks source<=its OWN ACTUAL activated timestamp;
no newest/max/nominal cutoff. No cancel pending, exact OPEN reservations,
zero prior fills, flat holdings/basis, no FOK/unhedged, healthy fresh persistence,
no recovery/external mode, nonnegative available cash;4 monitors hold through
callback with thread/lifetime invalidation. No queue/fee/risk/latency tuning.

Local native proof29 refusals (write failures/restored ledger included),4-monitor
contention/lifetime checks,1929 native predicate/math correspondences,7 original
97/628 indexed wrapper integration checks PASS. Both exact frontier preimages
8739/82880 pass guard in EXPLICIT SYNTHETIC sessions with subset identity check,
NOT full replay. Synthetic books use retained queues1182.30/180 and0/0; not
original book reconstruction evidence. Full indexed runtime mode remains strict
sequential16317 identities; subset mode still cannot attach or certify replay.
Unknown volume remains UNKNOWN_NOT_ZERO and known97 quantity200 unchanged.

Freeze:research/phase6/source-lag-guard-freeze.json; retained proof under
research/experiments/source-lag-guard-20261020. New profile's clock counters
separate nonempty-order and active-order cases; legacy preactivation counter
unused. New workflow repeats proofs on Java21 BEFORE ONE original-development
baseline/QW0 comparison. No market capture/RPC/holdout or strategy retune.

NEXT await that new run, not duplicate it. If source>actual activation blocks,
retain exact identity and queue/cancel audit, then obtain bounded settlement
evidence; never weaken safety to manufacture fills/profit. Full net UNKNOWN,
independent acceptance not passed; PAPER/NO_GO, PR9 draft/unmerged.

Local55 targeted Python tests PASS31.080s; complete96-source Java17 generated
build/new native proof, unchanged5144 source-lag math and DEFAULT before oracle,
old22 atomic guards/prior9 indexed wrapper checks PASS. No source replay locally.

### SOURCE_LAG0 actual original frontier AFTER activation — 2026-10-20

39459692699/job118755614423 COMPLETE SUCCESS, frozen sourceda1211f2eccca29e865994f4090f8df55edb0000.
Java21 preflight55 Python tests PASS20.938s, new29 refusal/1929 correspondence/
7 indexed integration checks and2 exact-frontier SYNTHETIC envelopes PASS;
old source-lag/preactivation/atomic/indexed/no-order/default proofs unchanged.
Then existing ORIGINAL DEVELOPMENT recording downloaded ONCE for baseline and
unchanged QW0 candidate, same config, no capture/RPC/holdout/retuning.

Actual previous82880/8739 passed. Baseline now838 identities/836 unknown clocks,
10 nonempty-order/2 already-active; stops82964. Candidate99 identities/97 unknown
clocks,12 nonempty-order/5 already-active; stops9035. Last identity consumed but
unknown execution not applied. Both fail-closed, no complete account comparison.

This new frontier has source AFTER actual activation:baseline18ms/candidate8ms.
Orders active86ms/79ms at arrival. The proven temporal shortcut no longer
applies; DO NOT weaken it. Actual queues baseline0/0,QW01182.30/180 unchanged
before halt cancellation; executions/holdings0. Known original97 quantity200/
16 components whollyunused; unknown venue volume remains UNKNOWN_NOT_ZERO.
Prefixcash500/fees0/realized0 is not a full net result. Full net remains UNKNOWN.

Exact next receipt targets:baseline82964 transaction
0x6fb0a9218d26394ca3ce7f6874218e38ed8f886ca60e1dd3a6b44f1f43446590;
candidate9035 transaction
0x740e975da87f07493fd104e7a8aecead4727eb365955e732c8bc3ff4f5972a1c.
Obtain/independently verify ONLY these2 actual receipts, parse conserved maker
components and preserve raw original preimages BEFORE separately frozen expanded
pool/new same-source comparison. Public aggregate BUY/price/size is NOT venue
quantity or a bot fill. No unchanged replay; no new strategy/holdout tuning.

Artifact12281674124,24788 bytes,SHA256
74765c9e6b019b029b7dc2297b4087a368b02092aec179ff06db92102fe55b7c
retained source-lag-guard-20261020/ci-artifact.zip. New diagnosis checks27 members,
raw original source identity/tx, unchanged config, known volume, submit/actual-
activation/queue/cancel audits, incomplete financial scope and local/Java21
proof parity;2 local tests include3 mutation subcases. original-diagnosis.json
is authoritative current frontier; older bounded proof flags remain historical.
Retention commit does not touch workflow/freeze. PAPER/NO_GO, no independent
acceptance pass, PR9 draft/unmerged; both pre-existing dirty archives preserved.

### TWO bounded post-activation receipt targets frozen — 2026-10-20

Remoteefe9b09/PR9 draft checked; previous39459692699 COMPLETE SUCCESS and no
active workflow. Only exact candidate9035/baseline82964 post-activation receipts
selected from validated original artifact, never outcome/price-picked or widened.
New postactivation_receipts.py checkpoints every successful public response,
uses chain137 and read-only3-method allowlist, max2 receipt/2 block requests,
deduplicates shared blocks and never refetches successful receipts on resume.

Reviewed ABI/exchange decoder and conserved route checks reused. Unique original
token/side/size group required, rounded public price difference<=.005 and block
timestamp within120s of exact source; ambiguity/failed/duplicate/removed logs
fail closed, never zero. Public RPC corroboration is not cryptographic finality
or bot fills. All new scope flags prohibit simulated fills/PnL/qualification.

Local19 targeted tests PASS14.839s, synthetic2-route/conservation/checkpoint/
resume/budget and bad identity/chain/status/hash/time cases plus prior receipt/
route/source checks. Freeze postactivation-receipts-freeze.json and exact source
selection/evidence folder postactivation-receipts-20261020. New workflow ONLY
reads these2 receipts and matching blocks, NO original replay/capture/holdout.

NEXT inspect/await new read-only run and re-derive real components offline, then
separately freeze expanded pool/native consumer before any new same-source
comparison. Current pool643/1532, SOURCE_LAG0, config/acceptance/fees/queue/risk
and strategy unchanged; net UNKNOWN, PAPER/NO_GO, PR9 draft/unmerged.

### TWO actual post-activation receipts verified — 2026-10-20

39468514569/job118786128207 COMPLETE SUCCESS on1f2c7e9d0f1897ace68c0665b943663fd883f381.
19 targeted tests PASS14.733s, then exactly1 chain-ID/2 receipt/2 block public
read-only calls. No tape replay, market capture, wallet/keys/orders or holdout.

Actual9035:ONE DIRECT maker SELL tokenB,shares3846154 raw,collateral2000000 raw,
price0.5199999792000008319999667200; recorded bot orders BUY. Actual82964:ONE
MINT maker BUY tokenA,shares9000000 raw,maker collateral2610000 raw,price0.29;
taker collateral6390000 raw. Recorded tokenA bid0.24 is below maker0.29; tokenB
order differs in token. Necessary token/side/price/source predicates reject all
recorded orders for BOTH selected real components. This is receipt-specific,
NOT whole native/account replay or queue allocation; model bot fills0.

Artifact12286053123,15018 bytes,SHA256
b18b80b960a5de5273197fc04460f4a70224ead77d0307827c494ba5a4337e79
retained postactivation-receipts-20261020/ci-artifact.zip,4 bounded members.
New postactivation_receipts_result.py re-decodes raw receipt/block, exact original
identities/conservation and original quote necessary eligibility, compares report
and raw hashes, rejects financial/native-pool promotion;3 additional local tests.
verification.json preserves2 real maker parts, NOT bot fills or profit.

NEXT separately freeze645 real bindings/1534 parts preserving643 old bindings,
verify native/source parity before ONE new baseline/QW0 replay. Existing pool
and SOURCE_LAG0 unchanged; no broader reads or unchanged replay. Full net after
costs UNKNOWN, no independent acceptance pass; PAPER/NO_GO, PR9 draft/unmerged.
Retention commit does not alter workflow/freeze or trigger repeated reads.

### Exact645 receipt pool frozen before replay — 2026-10-20 21:34 Asia/Amman

The two exact post-activation receipts were added to a new, separately frozen
pool without changing any of the prior643 bindings. The canonical result has
645 original source bindings and1534 actual maker components: DIRECT355,
MINT1162 and MERGE17. Pool logical SHA256:
16dab5fa70b908ccb5c7aeaaba803f2c5ac4f66b0efa50de6b2d1b82c0d662c7;
exact645 identity SHA256:
221cd9a9e7f6fe1cbc280e964a9db25018ed46f0bf7e81722a74b7049b75c016.

A generated-only SOURCE_LAG0 helper pins that pool hash, and the new replay
orchestrator requires full consumption of645 bindings plus the unchanged16317-
identity source index. Local native parity matched all645 preimages and1534
conservative component tuples and passed39 fail-closed reader guards. This is
identity/reader evidence only: the original tape was not replayed, no queue
allocation/model fill was created, and no account PnL was recomputed.

NEXT retain the independent Java21 native-parity workflow report. Only after it
passes, run one same-original-development-source baseline and unchanged QW0
comparison. Do not repeat completed643/source-lag diagnostics, retune either
profile, or change queue/fees/latency/risk/acceptance/holdout. Complete net after
costs remains UNKNOWN; PAPER/NO_GO, PR9 draft/unmerged.

GitHub run39478398235/job118820264563 COMPLETE SUCCESS on87ab3be. 29 Python
tests PASS62.421s, then Java21 matched all645 identities/all1534 component tuples
and39 fail-closed reader guards. No tape artifact was downloaded by this run.
Artifact12291405729, SHA256
279ef3b0a279c8dfc6ca0b722fcfaffcd8dc0a9c792374d7fd266712a34034bf,
is retained with native-proof/verification. The next workflow is separately
frozen to download the unchanged original development source only after this
retained proof, then run exactly baseline and unchanged QW0 once. Still no new
capture/public reads/parameter tuning; complete net remains UNKNOWN.

### Exact645 one same-source replay stops at next receipts — 2026-10-20

Run39479346181/job118823518285 COMPLETE SUCCESS onf54e88c. The retained native645
gate and18 tests passed, then the unchanged original development source was
downloaded once. Baseline and unchanged QW0 each ran once with SOURCE_LAG0,
fixed config, complete16317 identity index and exact645 pool. No new capture,
RPC, strategy/queue/fee/latency/risk/acceptance/holdout change.

Both profiles consumed the newly added receipt and stopped fail-closed at the
next source-after-activation unknown. Baseline consumed839 source identities/
3 known bindings, then stopped at seq82986, tx
0xc9b48a2f8ed8998a334469807f4fa141b82e7848e10f86f27f2495e0bcf27621,
tokenA BUY .32 size40, source1792269639627,42ms after activation. It had18 known
components/212.846154 shares, all unused; queues0/0 and active112ms. QW0 consumed
100 identities/2 known bindings, then stopped at seq9060, tx
0x1e466a61b791aaf8b510dcf9ebc8a53c24efd67e866ab994a2044da81a02f651,
tokenB BUY .52 size38.461539, source1792269594522,19ms after activation. It had
17 known components/203.846154 shares, all unused; actual queues1182.3/180 and
active88ms.

Both stopped prefixes have executions0,holdings0,allocated0,queueAbsorbed0;
paper orders canceled, halted safely. cash500/realized0/fees0 are INCOMPLETE
PREFIX state, NOT net performance. Artifact12290241861,13708 bytes,SHA256
ae76233de5e1ec7f209508aca9499afa2cf98184f173c4d398f8424d837b40a3.
Complete account comparison false, full net UNKNOWN, acceptance not evaluated.

NEXT obtain and verify ONLY the two exact new receipt targets above, then extend
the separately frozen pool again before any further same-source replay. Do not
rerun exact645 unchanged, widen receipt selection, infer fills from public size,
or alter queue/fees/risk/strategy/holdout. PAPER/NO_GO, PR9 draft/unmerged.

### Exact645 next two receipts verified — 2026-10-20

Run39481141401/job118829716023 COMPLETE SUCCESS on9402131. Frozen source checks
and18 tests passed before exactly1 chain-ID/2 receipt/2 block public read-only
calls. No tape replay, capture, wallet/key/order, holdout or parameter change.

Candidate9060 is ONE DIRECT maker SELL tokenB component:38.461539 shares,
20 collateral, maker price0.5199999927200001019199985731. Baseline82986 is ONE
DIRECT maker SELL tokenA component:40 shares,12.8 collateral, maker price0.32.
Both recorded PAPER orders are BUY, so both actual components fail the necessary
side predicate. They are conserved public venue routes, NOT bot fills; queue
allocation remains unproven and model fills remain0.

Artifact12290764619,14356 bytes,SHA256
bfc9043ca0ca851914b90aa388967d7eba7c7b6db0f906927b16356f04a2dcf1,
retained under next-postactivation-receipts-20261020 with4 bounded members.
The result verifier re-decodes raw receipts/blocks, exact retained source
preimages and conservation, checks recorded-order necessary eligibility, and
rejects report promotion/mutation;3 tests PASS34.288s.

NEXT extend a separately frozen647-binding/1536-component pool while preserving
all645 prior bindings; verify native/source parity before any further original
same-source baseline/QW0 replay. Do not repeat exact645, infer fills, weaken
queue/fees/risk, retune strategy, or inspect holdout. Complete net after costs
remains UNKNOWN; independent acceptance not passed; PAPER/NO_GO, PR9 draft and
unmerged. Retention does not touch the workflow/freeze, so it triggers no read.

### Exact647 native receipt-pool parity — 2026-10-21

Run39518124376/job118955093214 COMPLETE SUCCESS on3434b05 after two compile-only
dependency corrections; the data/regression step passed on every attempt and no
market tape/RPC/replay was used. Java consumed all647 exact original identities
and matched all1536 conservative component tuples with39 reader rejection
guards. All645 prior bindings remain byte-for-byte equal; the two new bindings
are DIRECT, yielding DIRECT357/MINT1162/MERGE17.

Pool SHA256 aa3f42e1cfff24fd5c9f3750136f56a4e23d7cd333a9d949e4224b176c4a4da4;
source identities fa34002142b3a0570217f6bd902f007963f82384d2cbd964a0e4e4151edf6a5b;
component tuples e764d3ece8e79271f242edbfafe862f68aac87407068a0f67b4be3cfa31ee4f5.
Artifact12308562731,1233 bytes,SHA256
6c854c25ea475c9a97e5d62972858ccabf9982e37a218c94a81070c6b26ea975.

NEXT separately freeze ONE exact647 same-source baseline/unchanged-QW0 replay.
No strategy/queue/fee/risk/latency/acceptance/holdout change or parity rerun.
Complete net remains UNKNOWN; independent acceptance not passed; PAPER/NO_GO.

### Exact647 one same-source replay stops at next receipts — 2026-10-21

Run39522503331/job118969423264 COMPLETE SUCCESS onf1d1183. All frozen exact647
gates passed, then the unchanged original development source was downloaded
once and exactly baseline plus unchanged QW0 were run. No new capture/RPC,
retuning, or queue/fee/latency/risk/acceptance/holdout change.

Baseline consumed840 source identities/5 known bindings and stopped fail-closed
at seq83030, tx
0x19350e0b8694d7991fef1197e6b3e3b6468a1320e74211306d1e8f4398ebebfe,
tokenB BUY .72 size28.76, source1792269639664. It conserved20 known maker
components/291.307693 shares, all unused; actual queues0/0 and active150ms.
QW0 consumed101 identities/3 known bindings and stopped at seq9082, tx
0xd05470e16ac0da2c3d0badf195be6478febfadc5510407223dea456a7cc16875,
tokenB BUY .52 size38.461539, source1792269594528. It conserved18 known maker
components/242.307693 shares, all unused; actual queues1182.3/180 and active97ms.

Both stopped prefixes have executions0,fills0,holdings0,allocated0 and
queueAbsorbed0; all four PAPER orders were canceled and both sessions halted
safely. cash500/realized0/fees0 are incomplete prefix state, NOT net
performance. Artifact12311956727,13728 bytes,SHA256
a099ab48097b06477009e27a55ddaa95ec6808b95c239c7bff97a412bc453a8e.
Complete comparison false, full net UNKNOWN, acceptance not evaluated.

NEXT obtain and verify ONLY the two exact new receipt targets above, then extend
a separately frozen pool before any further replay. Do not repeat exact647,
infer fills, weaken queue/fees/risk, retune strategy, or inspect holdout.
PAPER/NO_GO, PR9 draft/unmerged.

### Exact647 next two receipts verified — 2026-10-21

Run39528071948/job118987298870 COMPLETE SUCCESS on1a2d054. Exactly1 chain-ID,
2 receipt and2 matching-block public read-only calls followed13 offline tests.
No tape replay, wallet/key/order, parameter, acceptance or holdout change.

Candidate seq9082 conserves two DIRECT maker SELL tokenB components totaling
38.461539 shares; its recorded PAPER tokenB order is BUY, so neither passes the
necessary side condition. Baseline seq83030 conserves two MINT maker BUY tokenA
components totaling28.76 shares at maker prices.29 and.27; its recorded tokenA
PAPER bid was.24, so neither passes the necessary price condition.

These are four public venue maker components, NOT bot fills. Queue allocation
is unproven; model fills remain0 and account PnL was not recomputed. Artifact
12312859584,15415 bytes,SHA256
126a6379abcfcebdee895aaedf387a6e1323f89114878aeccee6984c9d43d4c6.

NEXT extend a separately frozen649-binding/1540-component pool while preserving
all647 prior bindings; prove native/source parity before another replay. Do not
repeat exact647, infer fills, weaken queue/fees/risk, retune, or inspect holdout.
Complete net remains UNKNOWN; PAPER/NO_GO, PR9 draft/unmerged.

### Exact649 native receipt-pool parity — 2026-10-21

Run39534147635/job119006749423 COMPLETE SUCCESS on84bddb8. Java consumed all649
exact original identities and all1540 conservative maker-component tuples, and
passed39 fail-closed reader guards. All647 prior bindings are unchanged. The
four added components yield DIRECT359/MINT1164/MERGE17.

Pool SHA256 377a4394ec3542dfa085f33771a238e030142303b327ef8a14caf3b93de6481a;
source identities 3b6f19acbead128c23258057cf42feac6221d3489812bf1ef4480b38f9a630bf;
component tuples 9187611be4eb2ad8d536d8b6176e609e551600c090cd26a33dff9854855fe20d.
Artifact12317191472,1235 bytes,SHA256
178d32559cbfff83689f85fbba608e491155a034b3f60b0270fc1c89292a03a7.

No tape, RPC, replay, fill or PnL computation occurred. NEXT separately freeze
ONE exact649 same-source baseline/unchanged-QW0 replay. Do not repeat parity,
retune, weaken queue/fees/risk, or inspect holdout. Complete net remains
UNKNOWN; independent acceptance not passed; PAPER/NO_GO, PR9 draft/unmerged.

### Exact649 one same-source replay stops at next receipts — 2026-10-21

Run39558018680/job119082298879 COMPLETE SUCCESS on138daeaa. The retained native649
gate and5 targeted tests passed, then the unchanged original development source
was downloaded once. Baseline and unchanged QW0 each ran once with SOURCE_LAG0,
the complete16317-identity index and exact649 pool. No capture/RPC, retuning, or
queue/fee/latency/risk/acceptance/holdout change occurred.

Baseline consumed841 source identities/7 known bindings and stopped fail-closed
at seq83130, tx
0x172abaae63ece7822e54e3f6c2366f3dfd592fc2ed30e704ed5920e8849b0c0a,
tokenB BUY .69 size31.37, source1792269639704. It conserved24 known maker
components/358.529232 shares, all unused; actual queues0/0 and active189ms.
QW0 consumed102 identities/4 known bindings and stopped at seq9227, tx
0x94a8d9be925c766f49a620ee72ce3ba072c15ed87653d868dd9c3616ea6d2226,
tokenB BUY .52 size66.79, source1792269594594. It conserved20 known maker
components/280.769232 shares, all unused; actual queues1182.30/180 and active166ms.

Both stopped prefixes have executions0,fills0,holdings0,allocated0 and
queueAbsorbed0; all four PAPER orders were canceled and both sessions halted
safely. cash500/realized0/fees0 are incomplete prefix state, NOT net
performance. Artifact12327320316,13739 bytes,SHA256
ad53ff83b0015613368875b46fff651c37b646c439ad35e4f769e2138f95e4e1.
Complete comparison false, full net UNKNOWN, acceptance not evaluated.

NEXT obtain and verify ONLY the two exact receipt targets above, then extend a
separately frozen pool before any further replay. Do not repeat exact649, infer
fills, weaken queue/fees/risk, retune strategy, or inspect holdout. PAPER/NO_GO,
PR9 draft/unmerged.

### Exact649 next two receipts verified — 2026-10-21

Run39562983382/job119098396467 COMPLETE SUCCESS on91e0b30c. Thirteen offline
tests passed before exactly1 chain-ID,2 receipt and2 matching-block public
read-only calls. No tape replay, market capture, wallet/key/order, native pool
extension, parameter, acceptance or holdout change.

Candidate seq9227 is one conserved MINT group with8 maker BUY tokenA components,
all at price.48 and totaling66.79 shares. Its recorded tokenA PAPER bid was.47,
so none passes the necessary price condition. Baseline seq83130 is one conserved
MINT group with2 maker BUY tokenA components at prices.32 and.30, totaling31.37
shares. Its recorded tokenA PAPER bid was.24, so neither passes the necessary
price condition.

These10 public venue maker components are NOT bot fills. Queue allocation is
unproven; model fills remain0 and account PnL was not recomputed. Artifact
12328971016,16658 bytes,SHA256
19634d571efb8ab38b34518a7371a781990c5082343b91d82bb1eb8f8786cbfc.

NEXT extend a separately frozen651-binding/1550-component pool while preserving
all649 prior bindings; prove native/source parity before any further replay. Do
not repeat exact649, infer fills, weaken queue/fees/risk, retune, or inspect
holdout. Complete net remains UNKNOWN; PAPER/NO_GO, PR9 draft/unmerged.

### Exact651 native/source parity — 2026-10-21

Run39572013713/job119128270610 COMPLETE SUCCESS on frozen commit987e4de. The
separate pool preserves all649 prior bindings byte-for-byte and adds only the
two already verified post649 receipts:10 MINT components. Totals are651
bindings/1550 components: DIRECT359, MINT1174, MERGE17.

The Java reader consumed651/651 original identities and reproduced all1550
component tuples while passing39 rejection guards. Frozen pool/source/portion
SHA256 values are respectively a6b28410c97ccd40a44e012aad3b9b647e77d00897ededc286ed884fc3ab7b9e,
ec3b3a9cf3efb60a006e6a51de6253df26e2e64d110f35608912c076e8f264a1,
and ae86d0977b02aca7aeb3c8af5ca5aa52ff4c612e69c112646a7c7144adb4f659.
Artifact12331629082,1230 bytes,SHA256
b50b77dcd5de6c23f6050a46104b54adebb7e4fc333bf49b7701eb9bc186e3e7.

This was offline native parity only: no tape replay, RPC, market capture,
wallet/key/order, account PnL, acceptance evaluation, parameter or holdout
change. No new fills or profitability are claimed; complete net remains UNKNOWN.

NEXT freeze exactly one same-source baseline/QW0 replay against exact651. Do not
repeat parity, retune, inspect holdout, infer fills, or weaken queue/fees/latency/
risk. PAPER/NO_GO, PR9 draft/unmerged.

### Exact651 same-source baseline/QW0 replay — 2026-10-21

Run39594036894/job119201809874 COMPLETE SUCCESS on frozen commit eb3d6fc. The
retained native651 gate and exact tests passed, then the unchanged original
development source was used once per profile. No public read, capture, wallet,
key, real order, retuning, or queue/fee/latency/risk/acceptance/holdout change.

Baseline consumed842 source identities/9 known bindings and stopped fail-closed
at seq83144, tx
0xc6a3d73eb66fd4b9b62a30438accf18bfc15b38486487548028a61ea7d7e89ad,
tokenA BUY .29 size23.517242, source1792269639708. It conserved34 known maker
components/456.689232 shares, all unused; actual queues0/0 and active192ms.
QW0 consumed103 identities/5 known bindings and stopped at seq9305, tx
0xd7b63a2975559d4970aa55276e5ad74bd5b71c8c9c8b2d40fcb06fb97ba99c07,
tokenB BUY .52 size5.865385, source1792269594616. It conserved28 known maker
components/347.559232 shares, all unused; actual queues1182.30/180 and active187ms.

Both stopped prefixes have executions0,fills0,holdings0,allocated0 and
queueAbsorbed0; all four PAPER orders were canceled and both sessions halted
safely. cash500/realized0/fees0 are incomplete prefix state, NOT net
performance. Artifact12344375720,13784 bytes,SHA256
29393f1aaba3d6e461835bf759aacca8cf580a9bc2cb0233b9ed4711d23b2014.
Complete comparison false, full net UNKNOWN, acceptance not evaluated.

NEXT obtain and verify ONLY the two exact receipt targets above, then extend a
separately frozen pool before any further replay. Do not repeat exact651, infer
fills, weaken queue/fees/risk, retune strategy, or inspect holdout. PAPER/NO_GO,
PR9 draft/unmerged.

### Exact651 next two receipts verified — 2026-10-21

Run39601135971/job119225630940 COMPLETE SUCCESS on53a88f7b. Thirteen offline
tests passed before exactly1 chain-ID,2 receipt and2 matching-block public
read-only calls. No tape replay, market capture, wallet/key/order, native pool
extension, parameter, acceptance or holdout change.

Candidate seq9305 is one conserved MINT group with1 maker BUY complement
component at about price.48 totaling5.865385 shares. Baseline seq83144 is one
conserved MINT group with2 maker BUY complement components at about price.71
totaling23.517242 shares. None of the three components passes the necessary
source-time, side, token and price conditions for the corresponding recorded
PAPER orders.

These3 public venue maker components are NOT bot fills. Queue allocation is
unproven; model fills remain0 and account PnL was not recomputed. Artifact
12346192183,15916 bytes,SHA256
3cb5b02414a81e5fca39f81d56ab536c4e4d44cd8f8c3aa62a28274cdaad1eb9.

NEXT extend a separately frozen653-binding/1553-component pool while preserving
all651 prior bindings; prove native/source parity before any further replay. Do
not repeat exact651, infer fills, weaken queue/fees/risk, retune, or inspect
holdout. Complete net remains UNKNOWN; PAPER/NO_GO, PR9 draft/unmerged.

### Exact653 multi-market native/source parity — 2026-10-21

Run39645215982/job119378862118 COMPLETE SUCCESS on frozen commit394ceaf. The
separate pool preserves all651 prior bindings byte-for-byte and adds only the
two already verified post651 receipts:3 MINT components. Totals are653
bindings/1553 components: DIRECT359, MINT1177, MERGE17.

The Java reader consumed653/653 original identities and reproduced all1553
component tuples while passing39 rejection guards. Frozen pool/source/portion
SHA256 values are respectively a6faa2118ba0fdc721a6eb83876886169f0c68980c0c88e04c1cb82ce6835f3c,
46b89213753fb0aa770aafac5899ba6bac170c647d177722571742a5981067d3,
and 7d51c46cd5059d906bbd9cdd95d2311896112a3ef18bb1ee0f1451a31c913d94.
Artifact12366354781,1234 bytes,SHA256
b5fa03262248f0115006c776f798f4f590c7dc0bb1e50e8f98ee3c02fd39a338.

The source bridge was generated separately from pinned exact651 commit2f47b71;
no historical freeze was rewritten. This was offline native parity only: no tape
replay, market RPC/capture, wallet/key/order, account PnL, acceptance evaluation,
parameter or holdout change. No fills or profitability are claimed; complete net
remains UNKNOWN.

NEXT freeze exactly one same-source baseline/QW0 replay against exact653. Do not
repeat parity, retune, inspect holdout, infer fills, or weaken queue/fees/latency/
risk. PAPER/NO_GO, PR9 draft/unmerged.

### Exact653 same-source baseline/QW0 replay — 2026-10-21

Run39654814359/job119412159026 COMPLETE SUCCESS on frozen commit84ff7ae. The
retained native653 gate and exact tests passed, then the unchanged original
development source was used once per profile. No public read, capture, wallet,
key, real order, retuning, or queue/fee/latency/risk/acceptance/holdout change.

Baseline consumed843 source identities/11 known bindings and stopped at
seq83158, tx
0xbb752799ecb1eb8c8ca56909384fafb61ed8db5bbfee91e15e775311087d0307,
tokenB BUY .70 size28.52857, source1792269639717. It conserved37 known maker
components/486.071859 shares, all unused; actual queues0/0 and active201ms.
QW0 consumed104 identities/6 known bindings and stopped at seq9379, tx
0xc37adc86b7c52b5c6a910c1e3e37b089988c5c262060ce6bfe73efed55827629,
tokenB BUY .52 size10.773585, source1792269594644. It conserved29 known maker
components/353.424617 shares, all unused; actual queues1182.30/180 and active210ms.

Both stopped prefixes have executions0,fills0,holdings0,allocated0 and
queueAbsorbed0; all four PAPER orders were canceled and both sessions halted
safely. cash500/realized0/fees0 are incomplete prefix state, NOT net
performance. Artifact12371311452,13703 bytes,SHA256
46eb57490c0b64e2f21ed89d3ee04fcf827100a679972e28ca5a8f91b754e142.
Complete comparison false, full net UNKNOWN, acceptance not evaluated.

NEXT obtain and verify ONLY the two exact receipt targets above, then extend a
separately frozen pool before any further replay. Do not repeat exact653, infer
fills, weaken queue/fees/risk, retune strategy, or inspect holdout. PAPER/NO_GO,
PR9 draft/unmerged.

### Exact653 next two receipts verified — 2026-10-22

Run39823548337/job119980758578 COMPLETE SUCCESS on frozen commit7bbdb67.
Thirteen offline tests and frozen dependency hashes passed before exactly1
chain-ID,2 receipt and2 matching-block public read-only calls. No replay,
capture, wallet/key/order, native pool extension, parameter, acceptance or
holdout change occurred.

Candidate seq9379 is one conserved MINT group with3 maker BUY complement
components:5 shares at.48,5 at.48 and.773585 at about.470000065. Its recorded
complement PAPER bid was.47, so none passes the necessary price condition.
Baseline seq83158 is one conserved MINT group with1 maker BUY complement
component:28.52857 shares at.30. Its recorded complement PAPER bid was.24, so
it does not pass the necessary price condition.

These4 public venue maker components are NOT bot fills. Queue allocation is
unproven; model fills remain0 and account PnL was not recomputed. Artifact
12444908879,15899 bytes,SHA256
3f9febab2dbc952e6ea6d8c072b417d8df6bc80b9b07f608814da940130b1bdd.

NEXT extend a separately frozen655-binding/1557-component pool while preserving
all653 prior bindings; prove native/source parity before any further replay. Do
not repeat exact653, infer fills, weaken queue/fees/risk, retune, or inspect
holdout. Complete net remains UNKNOWN; PAPER/NO_GO, PR9 draft/unmerged.

### Exact655 multi-market native/source parity — 2026-10-22

The initial run39834162733 failed after all exact655 tests/build checks because
the pinned three-day executor artifact from run39168798844 had expired. No Java
parity or market experiment ran in that attempt. Commit8b144dc rebuilt the same
dependency container from frozen source6dc5f25 and kept the original executor
JAR SHA256 gate; no strategy, data, queue, fee, latency, risk, acceptance or
holdout setting changed.

Run39835654997/job120023157665 then COMPLETED SUCCESS. The separate pool
preserves all653 prior bindings byte-for-byte and adds only the two already
verified post653 receipts:4 MINT components. Totals are655 bindings/1557
components: DIRECT359, MINT1181, MERGE17.

The Java reader consumed655/655 original identities and reproduced all1557
component tuples while passing39 rejection guards. Frozen pool/source/portion
SHA256 values are respectively 6dcf2f28956569965373d60ff040c2737d4c8412d812ac50def2b5608fb2881f,
949af3a6b94b8396644fdc450c09e613229b1962c3b97d201062fe0169d8899e,
and 67a2c1868b53ddf62387bc23c2394d176e6bc9f8aa38c1c5b81b2a19d3f08ae6.
Artifact12451735626,1237 bytes,SHA256
9de488b2932dba7e8e631ad37e43dd70f47c43caa32112ffa57208440bed3640.

This was offline native parity only: no tape replay, market RPC/capture,
wallet/key/order, account PnL, acceptance evaluation, parameter or holdout
change. No fills or profitability are claimed; complete net remains UNKNOWN.

NEXT freeze exactly one same-source baseline/QW0 replay against exact655. Do not
repeat parity, retune, inspect holdout, infer fills, or weaken queue/fees/
latency/risk. PAPER/NO_GO, PR9 draft/unmerged.

### Exact655 same-source baseline/QW0 replay — 2026-10-22

Run39838068117/job120031524797 COMPLETED SUCCESS on frozen commit aa5fde7. The
retained native655 gate and exact tests passed, the frozen executor JAR was
rebuilt from pinned source and matched its original SHA256, then the unchanged
original development source was used once per profile. No public read, capture,
wallet, key, real order, retuning, or queue/fee/latency/risk/acceptance/holdout
change occurred.

Baseline consumed844 source identities/13 known bindings and stopped at
seq83182, tx
0xe602b827ff89f9212d4fb2ee389c60120ff532c54b042c45bc37075c9a466b5c,
tokenB BUY .70 size10.25, source1792269639723. It conserved41 known maker
components/525.374014 shares, all unused; actual queues0/0 and active211ms.
QW0 consumed105 identities/7 known bindings and stopped at seq9496, tx
0xa96ec2960d29c18be3f6081d1f1e05cc5bea37c5a47cb1e64561f7a54e914762,
tokenA BUY .49 size30, source1792269594687. It conserved32 known maker
components/364.198202 shares, all unused; actual queues1182.30/180 and
active253ms.

Both stopped prefixes have executions0,fills0,holdings0,allocated0 and
queueAbsorbed0; all four PAPER orders were canceled and both sessions halted
safely. cash500/realized0/fees0 are incomplete prefix state, NOT net
performance. Artifact12452921077,13732 bytes,SHA256
3cbcae2290504df78c99efe7771bb9183f4c7ea0dfb63f231493ddd7e2ab6c90.
Complete comparison false, full net UNKNOWN, acceptance not evaluated.

NEXT obtain and verify ONLY the two exact receipt targets above, then extend a
separately frozen pool before any further replay. Do not repeat exact655, infer
fills, weaken queue/fees/risk, retune strategy, or inspect holdout. PAPER/NO_GO,
PR9 draft/unmerged.

### Exact655 next two receipts verified — 2026-10-23

Run39866806342/job120130927083 COMPLETED SUCCESS on frozen commitedddb83.
Thirteen offline tests and frozen dependency hashes passed before exactly1
chain-ID,2 receipt and2 matching-block public read-only calls. No replay,
capture, wallet/key/order, native pool extension, parameter, acceptance or
holdout change occurred.

Candidate seq9496 is one conserved MINT group with1 maker BUY complement
component:30 shares at.51. Its recorded complement PAPER bid was.48, so it does
not pass the necessary price condition. Baseline seq83182 is one conserved MINT
group with1 maker BUY complement component:10.25 shares at.30. Its recorded
complement PAPER bid was.24, so it does not pass the necessary price condition.

These2 public venue maker components are NOT bot fills. Queue allocation is
unproven; model fills remain0 and account PnL was not recomputed. Artifact
12463877969,15610 bytes,SHA256
74879c410a4826b3284c2dae5574001e869c25b996ac08d528b6c4175ffb42fc.

NEXT extend a separately frozen657-binding/1559-component pool while preserving
all655 prior bindings; prove native/source parity before any further replay. Do
not repeat exact655, infer fills, weaken queue/fees/risk, retune, or inspect
holdout. Complete net remains UNKNOWN; PAPER/NO_GO, PR9 draft/unmerged.

### Exact657 multi-market native/source parity — 2026-10-23

Run39874579658/job120156941028 COMPLETED SUCCESS on frozen commitaeade99. The
separate pool preserves all655 prior bindings byte-for-byte and adds only the
two already verified post655 receipts:2 MINT components. Totals are657
bindings/1559 components: DIRECT359, MINT1183, MERGE17.

The Java reader consumed657/657 original identities and reproduced all1559
component tuples while passing39 rejection guards. Frozen pool/source/portion
SHA256 values are respectively bb479f14c58ead5e1b7dc7234dc98f5e9abb06cd586b138bd351a66b9d864f93,
76f14452765d76f0ff102c1675b2ff167158e301a3fbd68138cac7be0f43166b,
and 9919463edb62c473666c4ea6f9ee238c801ddbb777cb9928b647e8c81ead9bcc.
Artifact12467179513,1236 bytes,SHA256
6c07967f7b302dfed43f8faf36a75955b318e1536b1daf2318e559033be38495.

This was offline native parity only: no tape replay, market RPC/capture,
wallet/key/order, account PnL, acceptance evaluation, parameter or holdout
change. No fills or profitability are claimed; complete net remains UNKNOWN.

NEXT freeze exactly one same-source baseline/QW0 replay against exact657. Do
not repeat parity, retune, inspect holdout, infer fills, or weaken queue/fees/
latency/risk. PAPER/NO_GO, PR9 draft/unmerged.
