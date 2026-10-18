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
