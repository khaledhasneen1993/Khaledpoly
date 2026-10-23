# Indexed original execution — frozen DEVELOPMENT only

Complete source index + exact real643 receipt pool + atomic empty-session witness
are integrated ONLY in a generated research session and explicit CLI. No default
core, strategy, queue/fee/risk/acceptance or live/service registration changes.

EVERY original trade identity is consumed BEFORE expiry/filter, using owned raw
input snapshots. Known observations consume the real pool once; expired known
bindings are consumed but NOT applied as settlement, and their known component
quantity is reported separately. Neither full index nor real pool completeness
checks are weakened. Unknown observations have an explicit Unbound route, NEVER
an empty/null Binding or public TRADE fallback. Only the atomic healthy-global-
empty-exposure callback may apply their exact canonical TICK. No strategy action
is moved into a frame; original advanceActions placement/parser remain intact.

Unknown observation counts and public observed size are diagnostics only:
`unknownVenueQuantity=UNKNOWN_NOT_ZERO`. Matching conservation is explicitly
scoped to known nonexpired components. Public size is NOT maker venue volume.
Missing/duplicate/wrong-frame/mutated identity or unknown-with-exposure poisons
execution, halts/cancels and blocks continuation. No synthetic fill is fabricated.

Local integration proof uses TWO exact original preimages97/628 recovered from
retained evidence, but surrounding session/frame/book setup is SYNTHETIC. It is
NOT the full source replay.9 integration checks cover expiry, unknown volume,
missing/duplicate/frame/mutation, exposure halt and incomplete finalization.
Default parity and prior atomic/differential/reuse counterexamples remain gates.

`indexed-execution-freeze.json` freezes source/helper/config hashes BEFORE the
original replay. Workflow tests/compiles/proves first, then downloads the existing
DEVELOPMENT recording once and runs baseline and frozen candidate on SAME bytes.
On failure, retain exact original frontier, errors, ledger, queue/cancel audit;
do not claim PnL from a stopped prefix. Completion still requires16,317 source
identities and643 real bindings consumed. No independent/holdout/live data used.
No research parameter is tuned by this integration. PAPER/NO_GO until unchanged
independent acceptance passes. Full candidate net still UNKNOWN before results.
