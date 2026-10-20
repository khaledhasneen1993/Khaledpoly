# Rebound reviewed cached receipts: partial pool, NOT execution

Preflight62d2233 / draftPR9 and retained-proof run39349192223 SUCCESS:
293 GitHub tests in336.566s; retained full-source identity/cache-index outputs
match exactly. No overlapping Action, source rescan, new capture or public RPC.

Revalidate the original metadata/causal source lineage, full16317-identity census
and ALL reviewed cache candidates. The191 missing observations with retained
receipts ALL map to the proven first original binary market; no new market pair
is inferred from tokens, rounded prices or receipt outcomes. Static metadata
identity is NOT an executable/freshness observation for earlier strategy times.

Every191 receipt is decoded again against original sequence/event/receive/source,
token/side/price/quantity/transaction/public-identity hash from the verified full
census. Require exactly one integer-conserved route group; match source taker
token/side/size, conserve shares AND collateral, reject failed receipts/duplicate
log identities/ambiguous groups. No outcome/price selection or dropped failure.
The existing451 bindings and their raw matches are preserved unchanged.

Original displayed price identifies the recorded public observation; it is NOT
treated as the actual maker execution price. Component prices come only from
conserved integer receipt amounts, never aggregate price or a touched quote.

Combined642 unique source coordinates/transactions,1,516 distinct maker
components:1,150 MINT,349 DIRECT,17 MERGE. Newly rebound191 groups contribute
478 actual components:329 MINT,141 DIRECT,8 MERGE. Maker BUY prices round UP
to28 decimals and SELL round DOWN in the parity digest, same existing rule:
`3fd8f2d4ce916cd2a70919431e81ec878cb26e94ad7e293ff81e515f6bce092c`.

Deterministic gzip pool201,377bytes (logical1,735,935bytes), both SHA256 in
report.json and cached-receipt-pool-freeze.json. Underlying raw receipts were
already retained in git; no duplicate RPC/download/evidence collection.

## Boundaries / tests

The pool format is deliberately DISTINCT from CONSERVED-MIXED-LAB0. It explicitly
says allOriginalPairObservationsWithinWindow=false, nativePoolConsumerImplemented
=false, fullAccountReplayAuthorized=false. Never forge a complete-window flag
to fit the older451 adapter. The read-only Python identity lookup rejects
unknown/duplicate coordinates, semantic-equal but byte-different tradeId,
changed source/arrival/price/size/token/side and promoted live/full-account scope.
It is not a consumption/queue allocator. A native consumer must revalidate raw
original tradeId bytes and enforce one-time observation/component consumption.

Six new regressions check ALL191 selection, preserve451 exact bindings, raw
receipt status/duplicate-log failures, no guessed market metadata, deterministic
saved source/component digest and fail-closed ORIGINAL source identity lookup.
Neither default/native strategy nor matching engine has been changed.

## Next

15,675 of16,317 total observations remain unbound:4,028 in this first pair,
11,647 elsewhere. Earliest missing originalseq97 remains unbound. Do not treat
them as zero or route them to public aggregate matching. No account result yet.

Implement strict native PARTIAL-pool consumer independently from legacy window
adapter; verify all642 identities/1,516 conservative component tuples and
duplicate/unknown rejection. Then implement complete original-frame/timer native
runner and exposure-aware coverage proof. Any no-order irrelevance optimization
must prove canonical transition equivalence and fail closed with any active,
reserved, activation-due or cancel-pending order. Never blindly fetch15,675
receipts, inject inventory, drop source inputs, or call missing volume zero.

Compare baseline/frozen QW0+exit on SAME source/config/coverage, then freeze the
complete executable BEFORE independent PAPER. Original control-$1.80 after
costs is an earlier DEVELOPMENT result, not a new expanded-label baseline.
Old conditional-$0.03747 vs+$0.11264 is not whole-account performance.
No new market/account net, model fill or independent qualification; NO_GO.
PAPER only, acceptance/strategy/queue/fee/risk unchanged, PR9 unmerged.

Complete local regression:299 tests in314.337s, OK. Separate six targeted
cases in22.729s, OK. All frozen code/test/source/evidence hashes verified.
Next CI repeats offline pool derivation byte-for-byte, not a market experiment.
