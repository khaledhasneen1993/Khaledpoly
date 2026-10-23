# Proof-only no-order execution differential — NO runtime optimization

No original core/reader/policy/parser or runtime registration changed. Strict
actual replay still stops at original628. No new capture/tape scan/RPC/account
performance run. This experiment tests a necessary building block before any
unknown observation can receive a distinct no-order witness. It does NOT enable
TICK substitution, empty bindings, unknown-as-zero or public-print fallback.

ALL643 original byte-verified identities /1532 actual component tuples are used
in SYNTHETIC book contexts: no books, fresh pair, stale pair, and missing pair
member. For each context compare canonical acceptSettlement against clock-only
transition with NO matcher orders. Exact updates and ALL private matcher fields
are compared, EXCEPT precisely five settlement component-ID/volume bookkeeping
fields. 2572 cases PASS. Full matching-state equivalence is explicitly FALSE:
known receipt volume is unused venue volume, while clock-only records none.
Unknown venue volume must be reported separately, NEVER asserted zero.

Then introduce a synthetic future order, preserve original250ms activation and
2x displayed queue, and process DISTINCT future component identities. All2572
future updates and all non-settlement private fields match. Synthetic future
fill-event counts in the raw proof are test expectations, NOT market fills,
trades, PnL or evidence that the bot is profitable.

Counterexamples REQUIRED and observed:

- Reusing the SAME component after a clock-only prefix changes future fills:
  canonical path already consumed its ID, clock-only did not. Thus a complete
  source identity index and globally unique transaction enforcement are mandatory.
- Legacy public TRADE differs from TICK even with no orders because it updates
  tradeIds/duplicates. Public aggregate fallback is not an equivalence solution.

Conservative prototype predicate rejects12 contexts: submitted, due/active,
cancel-pending/due, other-token orders, ledger reservation, holdings, pending FOK,
failed/stopped session and halted ledger. Reflection is READ-ONLY, in a bounded
test process, never wired into runtime. A real guard must be atomic under the
synchronized session/matcher/ledger path and include persistence health.

Separate SYNTHETIC fresh-ledger session differential compares complete ledger,
complete audit, full session report except exactly the two named label/volume
diagnostics, and all remaining private matching fields at3 checkpoints. Both
sessions subsequently submit and activate the SAME two QW0 orders; predicate
then correctly rejects optimization. This does not prove general session-level
equivalence; that flag remains FALSE.

Complete95-source research build + helpers Java17 PASS. 21 targeted Python
checks in0.282s OK, including4 new scope/counterexample/guard integrity cases.
One frozen Java21 CI repeats this bounded proof only (no original source replay).

Next: construct full16,317 original identity index from frozen census+bound
identities; prove raw-byte/coordinate/transaction uniqueness on every observation.
Then design explicit no-order witness (NOT null/empty binding), atomic guard,
and separate unallocatable unknown-volume counters. Guard must fail closed on
ANY active/reserved/due/cancel-pending order, pending taker, inventory, persistence
failure or unhealthy session. Only after exact source/continuation testing and
freeze may original SAME-source replay advance to execution-relevant unknowns.
No shortcut is authorized by this commit. Candidate net UNKNOWN, PAPER/NO_GO;
fees/queues/risk/acceptance unchanged, PR9 draft/unmerged.

## Java21 CI independently completed

Run39403569864 SUCCESS on613971e. Artifact12256497429 retained losslessly as
ci-artifact.zip,1580 bytes, SHA256
e67795d44525b07945d51d9c434138845db743d3644f6b4ccfef5fca6bcd5d27.
Downloaded proof is independently passed through no_order_result.verify; exact
output equals the producer verification.json. All2572 matcher/continuation
cases,12 guards, three synthetic session checkpoints AND required divergence
counterexamples reproduced. No runtime/source replay/receipt/account-PnL claim
is promoted by CI success. Next step remains full identity index + atomic,
healthy-session witness design with honest unknown-volume accounting.
