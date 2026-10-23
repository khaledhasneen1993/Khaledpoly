# Complete DEVELOPMENT source coverage: independently verified, still NO_GO

Source commit2328229 / run39342821835 / job118368228365 completed SUCCESS.
288 GitHub tests in296.068s, then full source census. No overlapping Action or
repeated source scan in this verification step. Artifact12228709938 is retained
losslessly here,1,594,521bytes, SHA256
`882112d70db3b1926e235ebfd0a150fa5a3d6ffc40d0aac657358c9a2ed9a46e`.
The two exact member hashes are in artifact-manifest.json; no partial files.

## Measured source coverage

- All6,163,831 journal rows, original compressed/logical hashes, receive clock,
  clean terminal and3,000,583 RAW/frame boundaries checked by complete census.
- 20 markets have metadata;18 have observed trades.16,317 normalized trade
  observations:15,024 BUY /1,293 SELL, no missing transaction fingerprints.
- 451 existing conserved receipt-bound observations /1,038 validated components.
- 15,866 observations MISSING receipt bindings:4,219 in the scoped original pair,
  11,647 in other markets. Missing observations are not zero fills/volume.
- 15,866 DISTINCT missing transactions; no repeated missing tx observations and
  no known-transaction aggregate suppression in this exact source artifact.
- Earliest missing/uncached observation is original seq97,eventIndex0, arrival
  1792269588213, source1792269588056, BUY200@0.57 in the first original market.

Independent verifier revalidates original451 bindings offline, validates every
one of the15,866 retained missing rows (exact canonical bytes, chronology,
coordinates, pair/condition, side, quantity, identity and compressed/logical
hashes), then merges BOTH streams in original sequence/event order. Reproduces
the digest of ALL16,317 identities, not merely a matching count:
`1f8d1d953f3755b8244c7ac11f7a3f72ccd8d73b1c9807b7cec417b6b710c1c2`.
Every source journal/normalized event count matches the immutable pre-existing
inspector, including28,743 standalone scheduler TICKs. Unknown research types
still fail; timer is not trade liquidity. Partial/no-order scope remains explicit.

## Reuse before new public reads

Indexed642 existing receipts from REVIEWED earlier experiment caches (451
recovery plus191 previous cached receipts).191 missing observations have an
existing receipt candidate,15,675 missing transactions are outside THIS reviewed
cache. This is cache PRESENCE, not newly corroborated route labels or exhaustive
proof that no other repository evidence exists. No original cache overwritten.
Observed token sets per condition are candidates, NOT binary metadata-pair proof.

No new RPC request, label, maker fill, account replay, net PnL, independent
qualification or live authority. Do not request15,675 receipts blindly. First
rebind the191 retained candidates against source coordinates/raw identity and
integer route conservation where metadata is proven. Establish the multi-market
native full-source runner / exposure-aware coverage contract, and identify the
first execution-relevant missing route. Any proposed no-order-irrelevance fast
path needs explicit canonical transition equivalence and must fail closed when
any active/reserved/activation-due/cancel-pending order exists; not implemented
or authorized by this result. Never pass unbound prints to aggregate matching.

Then compare original baseline and frozen QW0+exit candidate on SAME complete
source/config/coverage. Old control-$1.80 is a prior DEVELOPMENT baseline, not a
new replay on expanded labels; do not force a new baseline to reproduce it.
Freeze full executable/config BEFORE independent multi-market PAPER. No selected
snippet account, manual holding injection, holdout tuning, queue/fee/risk or
acceptance relaxation. Old conditional-$0.03747 vs+$0.11264 is NOT account PnL.
Full candidate account net remains UNKNOWN, NO_GO, draftPR9 unmerged.

Five new regressions reject changed source/count/first blocker, altered missing
price even with updated local gzip hashes, duplicate coordinates, and falsely
promoted scope. New CI rechecks RETAINED evidence offline only; it does not
rescan20GB original source, recapture a market or request another receipt.

Complete local regression:293 tests in295.910s, OK. Separate five new targeted
tests in7.313s, OK. Complete original artifact ZIP SHA and unchanged acceptance/
account configuration verified. No new scan/RPC/account PnL in this step.
