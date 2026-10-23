# Canonical session label bridge — synthetic accounting proof only

2026-10-19, parent `e1f0fd3782e901a9605b9804354ff8b091ab8ee4`, PR9 unmerged.
Prior adapter CI39314342475 completed SUCCESS:265 tests, four queue bridges,
22 rejection cases and two conservative price-rounding boundaries. No active
market or strategy experiment overlapped this implementation.

The mixed-side adapter is now wired into the **actual `ResearchSession`** in an
explicit, isolated research build. Existing constructors and LEGACY delegation
remain compatible. The shared account ledger, matching engine, fees, queues,
strategy choices and risk thresholds are unchanged. Only label resolution,
fresh-account gates and fail-stop handling are added to the generated session.

## Why an isolated source build

Old baseline/conditional evidence is pinned to exact original core sources and
binaries. The normal service and those files must remain reproducible. A tracked,
small patch is applied to a separate temporary copy of the core, not to the
checkout. No reflection, private-field injection, monkey-patching, fake ledger or
copied custom account engine is used. `session_bridge_build` verifies the exact
94-source inventory and every input hash, checks the patch before applying it,
then verifies that ONLY generated `ResearchSession.java` changed to its declared
hash. Existing/in-repository output paths are rejected, never overwritten.
The profile is not a public service flag or a live execution path.

## Tests and preserved evidence

The SAME deterministic synthetic feed runs through the untouched/default session
and the isolated build's default constructors. Parsed complete reports are equal:
`default-before.json` and `default-after.json`. This is behavior parity on a test
fixture, not universal equivalence proof or independent strategy evaluation.

The explicit mixed-label fixture uses orders created by the canonical strategy;
no preexisting5-share holding is injected. After normal250ms activation, one
synthetic conserved DIRECT component flows through the canonical matcher and
ledger: cash497.95,5 A shares, basis2.05. An alternate aggregate from the same
covered transaction leaves the ENTIRE ledger state unchanged. Actual fixture
component conservation is30 venue=5 allocated+0 queue+25 unused. These are
SYNTHETIC units, not market fills, revenues or strategy profits.

Seven session safety guards pass:

- Unknown scoped trade halts the account, cancels all outstanding orders and
  preserves already-booked cash/inventory.
- Subsequent input is rejected after that failure.
- External mode, existing session state, nonempty ledger, mismatched profile,
  and missing mixed labels are rejected before the experiment starts.

The first DEFAULT fixture expected a crossing public print to fill. The untouched
legacy matcher correctly rejected it because its public-print model requires an
EXACT price. The fixture was corrected to print at the actual order price0.41;
the model was not relaxed. The separate mixed fixture retains actual-component
matching at0.40 under the already-existing conserved-component engine rules.
Both DEFAULT reports then matched with the same source fixture in both builds.

Local Java17 compiles both full94-source core builds against libraries from the
verified retained executor artifact; this is not a Maven/JUnit/full-product build
claim. Four new build tests and four result/tamper tests pass. The new Java21 CI
workflow repeats both source builds, full offline regressions, default parity,
canonical synthetic ledger flow and failure guards. It requests no receipts,
captures no market data and runs no strategy on the selected development tape.

## Scope and next step

This completes the **session label-wiring dependency**, not integration of the
QW0 entry/frozen fee-positive exit policies. Those choices are still unchanged.
Next extend the same explicit research profile with the frozen causal entry/exit
rules; preserve cancel ACK ordering, execution-net recheck and shared cash/risk.
Establish complete source-bound replay coverage before full-account baseline /
candidate comparison. The existing451-observation recovery window alone is not
complete tape/portfolio coverage. Do not inject positions or concatenate selected
snippets to claim an account result. Then freeze integrated code/config before
independent multi-market PAPER under unchanged acceptance, without holdout tuning.

No new market PnL: the previously selected conditional exit remains+$0.11264
versus-$0.03747; separate original full-account development control-$1.80 after
costs. Full QW0 account UNKNOWN; NO_GO. PAPER only, no independent qualification.
