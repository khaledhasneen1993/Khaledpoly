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
source/config/acceptance hashes and4 regression tests. All original84 and
fresh590 necessary examples are complete; route/policy counts reconcile.
The old export omitted quantity: exact Decimal expression replay on the lawful
.01 grid yields ONE5-share census size for every example, not an optimistic
default. This recovers census size only, NOT actual metadata/decision state.

The unchanged worst-case guard, assuming the FULL still-unused2.50 budget and
.01 redemption, admits only1/12 original and4/43 fresh improve1 observations.
For already rejected join0 policy it admits1/72 original and13/547 fresh.
These are route/policy observations and UPPER bounds, not unique feasible fills.
All four fresh improve1 survivors lack a matching actual guarded active order:
first source precedes submission; other three are after actual cancellation.
Even historical UNGUARDED QB0 had NO matching outstanding BUY at the required
price at its1 original/13 fresh surviving observations. Historical QB0 order
lives are compared separately; the combined QB0+guard was NOT replayed or chosen
as a new candidate. Both original QB0 rejection and guard NO_GO remain in force.

This rules out a rationale for another receipt batch or pretending modeled
route-credit alone will make these nonexistent own orders fill. It does NOT
prove all hypothetical strategies impossible, nor identify the precise cause
of each missed entry. Need actual PRE-DECISION metadata, top depth/source clocks,
volatility/dynamic threshold, decision timer and GAP witnesses to distinguish
causal entry gating from a quote window shorter than activation. Never zero-fill
missing volatility or treat contemporaneous census quotes as earlier placements.
The surviving timestamps are all retained in `risk-feasible-census-20261018/`.
Reuse the prior4.506s original context where possible; inspect the last fresh
improve1 pair at1792269724135/1792269724142 together and remaining QB0 clusters
before predeclaring a change. No further full account replay, parameter sweep,
current-market capture or independent promotion justified by this screen.

159 phase6 tests pass locally, with report reproduced byte-content-equivalently
from the frozen inputs. Existing CI153 and historical full suite452 retain their
original scope; no redundant CI/Maven run requested. Acceptance SHA remains
7ac9a726348ecb5848591d4326963b8a5b129acc7a741a61d41305afdd5e8503.
Known economics unchanged: corrected control net-1.80, guard0/zero fills/no pair
ratio: NO_GO. Follow-up continues, PAPER only, guard default-off, no real funds.

## Causal entry witnesses prepared — 2026-10-18 21:34 UTC review

Checked latest PR9 head73da036 and prior jobs: completed, no overlap. The saved
census and order lives cannot identify the actual pre-decision volatility/risk
threshold. Add a strictly observational offline trace, not a new strategy:
six frozen condition/time windows, total8,714ms, covering ALL17 fresh risk-
admissible route/policy observations +/-500ms (nearby windows merged up to3s).
Retain the FULL replay history so volatility is never initialized from a slice.

Package-private fresh settlement-replay-only observer is absent by default, has
no service config or public activation flag, and cannot be enabled after input.
It records pre-decision market metadata/minimum, book source/receive clocks and
top depth (not queue reconstruction), actual observed and effective policy
volatility (missing observed values stay null), proposed bid/quantity, actual
PairPolicy threshold, edge/cash/risk/open orders, next-decision clock and original
input sequence. A finally block records the REAL per-market metrics reason
delta, including continue/return paths; no replacement decision logic or timing.
Bounds1..20 windows/max3s each/max30s total/max500 records fail closed, not truncate.
No pricing, activation, queue, fee, minimum, risk or acceptance changes.

New Java tests require observer-on/off reports to be identical after removing
ONLY the added witness list, for both risk-rejected and admissible entry fixtures;
they also check null missing volatility, actual branch reasons and activation/
window/cap restrictions.161 phase6 Python tests pass locally, including new tests
requiring ALL original account fields (fees, orders, fills, decisions, queue and
settlement labels included) to reproduce and rejecting missing/outside witnesses.
Full Java verification is pending CI, not claimed successful yet.

Freeze `entry-decision-witness-freeze.json` before its FIRST diagnostic replay.
Workflow runs full Maven/all Python regressions FIRST, then ONE existing full
development-tape guarded replay with14 unchanged environment labels. Reuse the
archived zero-fill candidate as golden; compare EVERY original report field
except code revision. Abort if observation changes any field. No new control/
candidate parameter search, current-market capture or public receipt requests.
Dedicated workflow supplies full regressions; narrowly tagged entry-witness
commit skips only duplicate markout CI, leaving ordinary/manual checks intact.
Read `causal-entry-decision-witnesses` before proposing any strategy adjustment.
Known corrected control net-1.80 and guarded0/0fills remain NO_GO; independent
acceptance unchanged, no holdout retuning, no profitability/promotion claim.

Started ONLY https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39168798844
at6dc5f25aec764ae55ecf0610a617baba77b7a6f7. Full verification job117797342104
succeeded:163 Java (146 core+11 executor+5 strategy+1 analytics) and306 Python
(8+50+38+49+161)=469 tests. Both new Java observer-equivalence/bounds tests pass.
The narrowly deduplicated markout job39168798819 was skipped as intended, not
another failed build. Witness job117797675258 is processing the original tape;
wait for its artifact rather than rerunning. No diagnostic reason/result from
that pending job is asserted yet. Default behavior/acceptance remain unchanged.

## Actual entry decision result — 2026-10-18 22:37 UTC review

Run39168798844 completed successfully at21:47 UTC. Source6dc5f25, artifact
12152096415, ZIP SHA934abe8054ebbc30c3c9625d65176843f63a0bfbe39676f9b50ce2c3e6ffc6e6,
retained losslessly in `entry-decision-witness-20261018/result/artifact.zip.b64`.
All69 original report fields reproduced, and a separate offline comparison
also reproduces EVERY original audit action in order, not only final cash.
All6 frozen windows contain decisions:34 actual causal snapshots. Actual reasons:
16 MIN_SIZE_AND_NET_EDGE,3 MIN_SIZE,12 NET_EDGE,1 PAIR_SUBMITTED,2 RESTING.
Thus31 rejections,19 size-limited and28 edge-limited with16 overlapping; these
counts are bounded selected decision observations, not whole-run rates.

Market minimum is5. Original size is min(5,10% of smaller best-bid depth), rounded
down .01. The19 rejected small sizes are real outcomes of the current rule, not
missing balances or a need to disable minimum size. Example decision1792269724247:
quantity3.5 vs minimum5, net total.025 vs required.040255698...
per share; the census print112ms earlier had DIFFERENT prior quotes/depth.
Do not backdate a quote or count the print as executable at the later decision.
Many full-size decisions have net.04 TOTAL on5shares (.008/share), below actual
required approximately.023..037/share. Actual volatility/expiry/thin-depth
premiums account for the thresholds; never replace them with a fixed1% floor.
Metadata/book freshness, cash500 and entryStopped=false were observed, not
guessed, in these windows. No additional fill/economic improvement is shown.
Corrected control net-1.80; guarded account0/zero fills/undefined pair ratio:NO_GO.

Verified all34 quantities and original risk-premium/net-edge arithmetic with
exact Decimal exports, original branch predicates, complete window coverage and
raw archive hash. Negative tests reject changed threshold/size/edge or missing
window.166 phase6 tests pass locally (469 full CI tests remain the earlier
runtime verification scope; no second Maven/CI run needed for offline additions).

Freeze ONE new PURE research price candidate BEFORE computing its screen: DQ3-0,
`depth-quote-candidate-freeze.json`. Choose from the first3 original displayed
bid levels of each leg, join only. Keep EXACT ORIGINAL top-depth quantity (do
not raise a .5-share request to5), actual minimum, dynamic threshold calculated
from ORIGINAL top depth/volatility/expiry, remaining loss cap, cash and portfolio
limits, active-market/freshness/taker-source/flat-account/no-open-order guards.
Each chosen price must separately show at least10x own requested quantity.
Maximize combined bid, then prefer shallower level indices deterministically.
Do not lower premiums using a thicker deep level. No queue/fee/latency/model or
service changes, no execution wiring or independent promotion. Lower prices
could increase visible queue and REDUCE fill probability; price feasibility is
not edge capture. The19 actual size-limited observations must remain blocked.

Predeclared gate: if there are NO additional legal priced entries on these34
states vs actual PAIR_SUBMITTED, reject DQ3 without a full-tape scan/replay.
Otherwise only consider a frozen necessary-TRAFFIC census on development data;
never jump from price arithmetic to full-account profitability/holdout/capture.
One variant, no fitted parameters/price-level sweep. Existing QB0 and guarded
zero-fill rejection remain intact. Preserve this preregistration in git before
evaluating DQ3 on the downloaded witnesses. PAPER-only, defaults unchanged.

## DQ3-0 frozen selected-state screen — 2026-10-18

Committed preregistration0cc9cc16633ef20eea1129f2793322b683acb29d BEFORE computing
DQ3 on the34 actual witnesses. Result `depth-quote-20261018/state-screen.json`:
11 states have a lawful priced pair vs1 actual legacy PAIR_SUBMITTED state,
10 additional price-feasible states. This is NOT11 submissions/fills or a
candidate account trajectory. All19 actual minimum-size failures remain blocked,
as do2 already-resting states. Every proposed quantity and required threshold
equals its original snapshot; every selected quote retains10% participation at
its own displayed level and fits the unchanged remaining worst-case loss cap.
No future print or achieved return was used in price selection. No policy tuning.

This passes ONLY the preregistered gate for necessary-TRAFFIC measurement.
170 phase6 tests pass locally, including immutable result/arithmetic/action
reproduction, DQ3 safety/tie rules and source/activation/GAP/aggregate-price
negative cases. Full runtime verification remains469 CI tests at6dc5f25; these
new Python-only helpers did not trigger another Maven build. No runtime wiring.

Freeze `depth-quote-traffic-freeze.json` BEFORE a SINGLE original full tape scan.
11 independently priced legacy decision anchors, actual original row/time/token
identity, due cutoff+250ms, at most unchanged unhedgedMs30s, first original GAP,
unavailable or resolution censors earlier. This deliberately RELAXED due-time
UPPER BOUND does NOT claim actual observed activation, queue, book-source trade
eligibility, actual resting-risk cancellation or candidate state evolution.
All those omissions can only overstate usefulness; no fills/PnL are inferred.
If no necessary traffic, reject these selected starts; do not infer global
strategy impossibility from selected states. Positive traffic still requires
actual receipt component prices AND causal queue/account replay before adoption.

Record all same-token SELL and opposite-token BUY observations at ANY public
price (mixed maker components make last/aggregate price filtering unsafe),
bound to original RAW text/normalized frame/event/source and full logical tape
hash/clean end. These are possible route observations, NOT actual DIRECT/MINT
labels or volume available to our order. Deduplicate transaction hashes for later
evidence handling; do not sum independent overlapping states as venue volume.
Public RPC/account replay/current capture forbidden in this small workflow.
Phase6 tests precede source reading, no Java rebuild. Inspect `dq3-necessary-traffic`
before choosing another step; never count price-feasibility improvement as profit.
Known account net remains control-1.80, guarded0/0fills, NO_GO. Acceptance/fees/
queue/latency/risk/minimum/default behavior unchanged, PAPER only.

Started only https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39173960311
at605b6ab1d9c6746451afa5841305565a799a95c2, screen job117812666986. Offline
regressions passed before the original tape scan, which was still processing
at22:52 UTC. Subsequently completed successfully; see the result below.

## DQ3 necessary traffic result and bounded receipt preregistration — 2026-10-18

Run39173960311 SUCCESS, original artifact12153622815 `dq3-necessary-traffic`,
ZIP SHA256 c0750f3db849972f1d4cd01f5428944c1b55b179fbe66c0dd1e7f236b2817490.
Exact original ZIP is retained as `depth-quote-20261018/traffic-result/artifact.zip.b64`.
It contains only depth-quote-traffic.json (794108 bytes). Full original source:
6163831 rows, logical SHA256 cd850df52d7f9994526603130f2942008f8f49ba80495d82b70dea66f0dc6d8b.
823 overlapping observations,416 unique transactions across11 independent
hypothetical states; every interval ends at its first original invalid_depth GAP.
These are relaxed necessary-traffic upper bounds, NOT fills, queue allocations,
observed activation/cancellation or a candidate account trajectory. No PnL change.

Freeze ONE bounded next diagnostic before public receipt reads: first additional
priced state by original sequence197690, complete least-observed target leg A,
8 observations/8 transactions, own bid0.47. Other leg47 observations and all
other states remain unaudited. Selection keeps ALL prices; mixed settlement
components make aggregate 1-price filtering unsafe. No parameter fitting.
`bottleneck-selection.json` retains exact original samples and relaxed window;
`dq3-bottleneck-receipts-freeze.json` hashes source, tests, selection, evidence,
and unchanged acceptance. Collector allows only public Polygon read methods,
<=8 new receipts, cached blocks, exact conserved maker components and integer
price comparisons. No fabricated actual order lifecycle is passed to validators.
174 phase6 tests pass locally before reads. One small receipt workflow only;
no full-tape rescan, Maven rebuild, account replay or independent PAPER capture.
Inspect complete receipt output before deciding next action. Even positive
actual component volume needs causal activation, queue/cancels and frozen
same-development baseline/candidate account comparison before promotion.
Control net remains-$1.80, guarded0/0fills, NO_GO. Defaults/fees/queue/risk and
fixed independent acceptance remain unchanged. PAPER only, no live permissions.

## DQ3 first additional state's bottleneck result — 2026-10-18 23:41 UTC

Frozen source ce78cbaf96ceaf34055d1d939983e9ae0ae5b34e, run39177547282:
https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39177547282
174 phase6 CI tests passed before exactly8 public receipts. All8 uniquely
conserved against original public observations. Artifact12155300727 ZIP SHA256
7b937464f275b0b562e12d3f203517a9c138448930761bb72178eb9fffe961dd is
retained in `depth-quote-20261018/bottleneck-result/artifact.zip.b64` with every
original receipt/block, topics, selection and reports. Separate offline test
re-decodes all8 receipts, reproduces exact routes and summary without public RPC.

Result: ZERO actual target BUY component shares at or below own0.47 bid across
the complete selected leg window. Actual target MINT components start at0.48;
two transactions are entirely DIRECT in the opposite token. Thus no recorded
actual price-compatible component supports this selected leg, even in its
relaxed due-time window. Do NOT turn actual venue components into hypothetical
taker redirection claims, fake queue fills, or global DQ3 impossibility. Other47
leg observations and all other states remain unaudited. Fills/PnL not recomputed.

Next justified gate: use already-archived receipts for any exact overlapping
state leg before requesting more; preserve distinct window/price and never
count duplicates. For remaining states, preregister bounded complete-leg audits
before reads, or reject cost/benefit of further investigation. No new PAPER
capture until a frozen candidate passes same-development causal full-account
comparison. Do not tune prices against this result. Known net after costs stays
control-$1.80 vs guarded0 with0fills (not profitable); independent acceptance
unmet. No defaults/queue/fees/minimum/risk changes and no live actions.

## Exact overlapping receipt reuse and next complete-leg freeze — 2026-10-19

Remote PR9 head909e912 and both relevant traffic/receipt jobs verified complete
SUCCESS before work; no duplicate capture/scan/replay. Re-decoded10 already
archived receipts from the two earlier bounded cohorts. Across all22 DQ3 state
legs, three have complete receipt coverage:173342/A (1 observation),197690/A (8),
198832/A (4). All three have ZERO actual target BUY component volume at/below
their OWN frozen bids0.45/0.47/0.48. The latter4 are reused transactions from
the earlier8, NOT new venue volume. This is exact-window/price reuse, not a new
policy or new fills. All incomplete legs report null rather than inferred zero.
`depth-quote-20261018/cached-overlap-coverage.json` retains this22-leg coverage.

Next selection frozen before public reads: earliest additional state whose
least-observed leg remains uncovered,243583/A, unchanged own bid0.49, complete39
observations/39 unique transactions before the first invalid_depth GAP. Rule:
source chronology, minimum leg observation count, lexical token tie, no prices/
profits optimized. Later overlapping windows may reuse this evidence only with
their exact source/price bindings; do not infer their results in advance.
`overlap-selection.json` and `dq3-overlap-receipts-freeze.json` bind exact samples,
source/tests, original DQ3 price policy, cached evidence and fixed acceptance.
178 phase6 tests pass locally, including offline re-decode, complete-vs-unknown,
quote-binding,39-read budget/block cache/resume and selection immutability.
The single small workflow will run offline tests BEFORE public reads. No Maven,
full-tape scan, account replay or independent capture; no keys/wallet/live orders.
Preserve raw successes and errors if incomplete, do not expand scope or count
partial missing coverage as zero. Next: inspect its full coverage/receipt report,
archive and re-decode before any strategy adoption. Known economics unchanged:
control-$1.80, guard0/0fills, undefined pair ratio, NO_GO; no profitability proof.

## DQ3 overlapping complete-leg result — 2026-10-19 00:36 UTC

Frozen preregistration9b80a8e4514c7a1c6d237db0a043360b3715358b preceded reads.
https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39181463387 SUCCESS:
178 phase6 CI regressions then exactly39 public receipt reads and8 block reads.
All39 receipts conserved against exact original samples, no errors. Artifact
12156695443 ZIP SHA256 baade0bae80c97677a4a4109da1bbf153e8445631e936e47aa6fc563d6caa621
retained as `depth-quote-20261018/overlap-result/artifact.zip.b64` (42 members:
39 original receipt/block files, selection, report, coverage). Full coverage
also retained as JSON. No fresh market capture, full tape replay or Java build.

Offline re-decode of all cached+new evidence gives10 completely covered A legs:
173342,197690,198832,243583,245065,246180,258161,258635,259283,259597.
Actual compatible target BUY component volume is960720922 raw (=960.720922
shares) in EACH of243583/245065/246180 at their unchanged own bid0.49; all
three share overlapping evidence, NEVER sum them as2882.162766 venue shares.
The other7 complete legs have zero compatible actual components. Remaining
12 legs are incomplete/unknown, not zero.49 unique cached receipts includes
one original context receipt not fully closing the opposite leg's coverage.

This passes only an actual-price necessary condition in three selected starts.
It establishes neither observed activation, current book-source eligibility,
queue depletion, actual resting-risk cancellation nor any candidate trajectory.
Legacy proposal243583 displayed840 shares at its chosen A level; the unchanged
2x queue model would imply1680 if seeded from THAT snapshot, exceeding960.720922.
Do NOT use the decision snapshot instead of actual delayed activation book to
claim either no-fill or fill: source-time and cancellation are still unproven.
The volume is also actual route components, not a hypothetical new taker route.

180 phase6 tests now pass locally. New immutable result regression re-decodes
all39 RAW receipts and every covered observation, exact sums/overlap semantics;
missing-receipt regression preserves39 errors/incomplete unknown coverage rather
than fabricated zero. Original frozen source/tests/policy remain unchanged.

Next justified gate is causal activation/book queue and resting-cancel lifetime
for the THREE already price-supported starts, using original source data and
unchanged250ms latency/2x queue/edge/risk. No further receipts for the opposite
leg or last unexamined state until this cheaper-to-reject first-leg gate passes.
If implementing a replay probe, keep research-only and defaultOFF, preregister
source/context anchors and require original source SHA/chronology, then compare
full-account baseline/candidate on same development data before independent
PAPER. Do not tune prices/queue/risk to this result. Net after costs unchanged:
control-$1.80; guarded0 with0fills, not profitable. DQ3 PnL not recomputed and
independent acceptance unmet. No wallet, keys, live orders or default changes.

## Three-start activation-seed probe preregistration — 2026-10-19

PR9 headb87d944 and preceding receipt jobs checked complete SUCCESS before work.
Freeze182 phase6 regressions and one5504ms original full-depth input window for
states243583/245065/246180 BEFORE extraction. Warmup begins2000ms before earliest
submit, covering every potentially fresh source book at activation (source<=arrival
and unchanged max age2000ms). Preserve full normalized BOOK arrays, every original
RESEARCH input and associated unchanged RAW frames, exact three source anchors;
validate full6163831-row source SHA/clean end, frame binding and chronology.
Unlike earlier GAP projection, this evidence is NOT truncated to top3 depth.

Isolated Java observer uses the actual already-verified PaperMatchingEngine from
artifact12151627900/run39168798844/source6dc5f25, not a Python queue approximation.
Current matching source hash12e89574023e0457d2066f8e50d660491a3ef182ae066bab4725cd40324fa84f
equals that compiled source. No Maven rebuild; compile ONLY a research observer
against those existing nested dependency jars. Run actual-engine assertions first:
activation uses the PRE-event book (840*2=1680 despite incoming size1), paired GAP
wins activation. Extractor182 offline tests pass locally; Java assertions pending CI.

At each independent original anchor inject one hypothetical BUY in an isolated
matcher;250ms activation/cancel,2000ms max age,2x queue unchanged. Suppress EVERY
TRADE allocation using its identical pre-event TICK path: no prints/fills/PnL
are simulated. Stop at initial activation/rejection; retain original input/event
index and whether activation occurred on FIRST input at/after due. Tick changes
or ambiguous first-input timing must remain inconclusive, not treated as proof.
This is a NO-CANCEL isolated seed probe, NOT actual candidate account activation,
resting-risk lifetime, portfolio behavior or a same-data account comparison.

Predeclared next interpretation: compare supported initial queue to the COMPLETE
actual-price volume upper bound already frozen960.720922 per selected window.
If initial queue is >= all that volume, it cannot clear in this isolated model
even before source-time filtering/resting cancellation; never turn the converse
into a fill claim. Unknown/ambiguous seeds require actual lifecycle integration,
not decision-book substitution. No additional receipt expansion/new capture.
Run only the new dedicated workflow; inspect its context and activation report
before changing policy. Hashes/spec in `dq3-activation-freeze.json`. Net unchanged
control-$1.80, guard0/0fills, DQ3 unknown; no acceptance/defaults/risk/fee changes.

Started ONE dedicated run39186480474 at frozen sourcec5660984bb6079547a24402aa21a01c19e505899:
https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39186480474
182 Python regressions passed on CI. Observer compiled against existing verified
engine and BOTH actual-engine pre-event-book/paired-GAP assertions passed before
original source download/extraction. Source download was in progress at this
checkpoint; context/activation report not yet available, no queue result claimed.
Await `dq3-activation-seed-context`; do not rerun/download another capture, launch
another account replay, or infer final economic results while this job runs.

## Actual-engine isolated activation results — 2026-10-19

Run39186480474 completed SUCCESS before this work. Artifact12158691088 ZIP
SHA256 bb9a933dd12035eb1c46a08f60662e3c19150ad5ad137e54dc0df93f6124d1ae,
original sourcec566098, retained exactly as `depth-quote-20261018/activation-result/artifact.zip.b64`.
Contains activation.json5391 bytes and context.json.gz1028320 bytes. Full original
source hash/6163831 rows verified by extraction;5051 unmodified normalized inputs,
full depth and original RAW, retained34163132 bytes for the frozen5504ms window.

Actual unchanged matcher seeded1292.48 queue at first eligible input for starts
243583 and245065, not1680 from the decision snapshot. Original pre-event books
seq244225/event0 and245661/event0 each display646.24 at own0.49 bid;2x gives
1292.48. Activation at1792269750554 and1792269751306 respectively, on the first
original input at/after due, no intervening tick changes. Whole actual-priced
volume bound960.720922 cannot clear either queue, with331.759078 left even if
ALL bound volume were eligible and NO resting-risk cancellation occurred.
Third start246180 rejected at1792269751806: POST_ONLY_WOULD_CROSS; pre-event
book seq246893/event1 has ask0.49 against own0.49 bid. It never activated.

`dq3_activation_result.py` independently selects exact PRE-event source snapshots,
validates warmup/frame/timestamps/freshness/price, compares actual-engine output
to conserved full-window receipt bounds, and reproduces verification.json.
No incoming/decision book substitution or inferred activation between callbacks.
This rejects ONLY these three isolated no-cancel starts. Trades were suppressed
in the probe, not simulated as fills. Resting cancellations/account trajectory
remain unmodeled; no global-policy or live-profit claim. No further opposite-leg
receipts/replay for these rejected starts. Seven other completely audited A legs
already had zero actual compatible components. One distinct selected start299650
still lacks its complete necessary leg; do not silently treat it as rejected.

Freeze remaining state299650/A, unchanged0.49 bid, full19 unique observations,
by continuing original chronological least-observed-leg rule after reusing all
49 cached receipts. No fit/sweep/price change. `last-selected-leg.json` and
`dq3-last-selected-leg-freeze.json` precede public reads;19-read hard budget,
retained RAW/blocks, conserved components, unknown partial coverage on failure.
This closes selected-state necessary evidence only, not an account/holdout test.
185 phase6 tests pass locally, including immutable activation/source proof,
queue/timing tamper failures, earlier49 receipts and exact remaining19 selection.
One small dedicated receipt job; no additional tape scan/Maven/capture. Inspect
its full report before deciding whether the LAST start needs a causal probe.
Net economics unchanged: corrected control-$1.80, guard0/0fills, DQ3 not measured
as an account, NO_GO. Fixed acceptance/fees/queue/risk/defaults remain unchanged.

## Final selected leg result and last isolated activation freeze — 2026-10-19

Run39191105555/sourcee24279d5a146cb9c54024e3f0d0bd51c46876553 completed its
full19 public receipts after185 phase6 regressions. All receipts conserved, no
errors;19 receipt and10 block reads. Artifact12160440418 ZIP SHA256
3da8eced1b9824d1b2e86641fad7754c2a1fad817d6a45a4d4094bd534c9fabd
retained as `depth-quote-20261018/last-leg-result/artifact.zip.b64` (23 members).
Coverage re-decoded offline from all68 cached receipts; all11 selected A legs
now completely audited, opposite legs still unknown. Last start299650 has
639910619 raw (=639.910619 shares) actual target BUY components at/below its
unchanged0.49 bid in the relaxed complete window. This is not available queue
volume, no fill or candidate profit. Earlier7 zero legs and3 isolated activation
rejections remain unchanged; do not sum overlapping state volumes.

Freeze ONE final selected-start activation probe,299650,4250ms original window
including2000ms fresh-book warmup. Same already-built production matcher and
unchanged observer/queue250ms/2x/post-only, all trade allocation suppressed.
No full account replay or policy change. New extractor parses the causal prefix
and full original window, then hashes/counts EVERY remaining original byte/row
and checks RUN_END. Exact complete logical SHA is the already-validated source
identity; tail parsing is not repeated, NOT permission to truncate/alter tape.
This reduces redundant JSON decoding without weakening identity/anchor proof.
188 phase6 tests pass locally including exact19 RAW re-decode, full-depth window,
tail change detection, missing anchor/terminal/warmup/frame/cap fail-closed tests.

`dq3-last-activation-freeze.json` binds source/tests, original matcher, same
observer, receipt evidence and unchanged acceptance before source extraction.
Next inspect `dq3-last-activation-seed-context`: verify pre-event book and first
due input. Reject only isolated start if initial queue>=639.910619 or post-only
rejects; if queue lower/ambiguous, require actual source-time/resting-cancel and
same-data account replay before any qualification. Do not infer fills or lower
queue/fees/risk from either outcome. No fresh capture or extra receipt sweep.
Net after costs unchanged control-$1.80, guard0/0fills; DQ3 economics unknown.

## Last activation result and cached resting-check probe — 2026-10-19

PR9 head5a8eb22 and run39191408588 verified complete SUCCESS before this work.
Artifact12160042036 ZIP SHA256
9c16e42982477344f1c7e62fa3beda92c0533b4184dc3edb585b2a42a4489808
retained exactly in `depth-quote-20261018/last-activation-result/artifact.zip.b64`.
Actual engine activates299650 at1792269786096 on original input299997/event0,
queue200. Therefore639.910619 complete priced volume is NOT excluded by queue
alone; do not report this start as rejected by the previous1292.48 queue result.

Reused immutable actual entry witnesses299650 and299997 plus full original context,
no public reads or tape rescan. Source pre-event depth100*2 reproduces queue200;
post-frame full books match BOTH witness snapshots/top3/source timestamps exactly.
Entry's actual nextDecisionMs equals witness at1792269786096. Unchanged resting
pair quantity is5, NOT the legacy new-entry size0.5 at that later decision.
With reserved0.49/0.47 prices and merge0.01, net total0.19 (0.038/share).
Original measured volatility/thin top depth5/expiry require exact
0.0400009719998870480/share (0.200004859999435240000 total), so the unchanged
maintainResting RESTING_NET_EDGE predicate requires cancellation at that callback.
250ms cancel due=1792269786346; first possible target-leg observation in COMPLETE
upper-bound census arrives1792269786398,52ms later. All18 other observations later.
No target-leg evidence can fill before cancel due; potential opposite-leg fills
and a candidate account trajectory are NOT simulated or asserted.

Freeze `dq3-last-cancel-freeze.json` before a small CONDITIONAL isolated pair
probe. Actual production PairPolicy recomputes the witness threshold; actual
PaperMatchingEngine replays cached source inputs and executes both CANCELs after
the first scheduled post-frame risk check. All trade allocations remain suppressed.
This is NOT invocation of a full candidate ResearchSession/account or an observed
historical cancellation; report precise counterfactual/isolated scope. Require
actual engine cancellation acknowledgement before first possible target print,
not just the arithmetic due-time claim, before rejecting this selected A leg.
190 phase6 tests pass locally, including immutable source/witness/queue/timing and
resting-vs-entry quantity checks. Reuse existing verified engine artifact, compile
only observer, no Maven build. No new capture, source scan, public RPC or fee/
queue/risk/acceptance changes. Next inspect `dq3-last-cancel-cached-proof`, archive
and validate actual acknowledgement, then close the eleven-selected-start gate.
Do NOT infer global DQ3 impossibility or profitability from selected snapshots.
Net economics remain control-$1.80, guarded0/0fills; DQ3 account unknown, NO_GO.
