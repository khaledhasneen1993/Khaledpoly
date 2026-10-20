# Atomic no-exposure witness — isolated research safety only

The generated-only build adds a package-private callback in ResearchSession.
Session → ledger → matcher → checkpoint monitors stay held during eligibility
and callback. Ledger close now uses its monitor; state close uses its monitor.
A witness cannot remain valid after callback return/exception, on another
thread, or outside these locks. It returns no labels and creates no fills.

Rejects ANY matcher order (submitted/active/cancel pending, any token), pending
FOK, residual unhedged timer, nonzero holdings/basis, nonterminal or remaining
ledger reservation, stopped/failed/halted state, external/recovered session,
restored ledger, failed writes and closed persistence. All due orders/cancels
are rejected BEFORE any clock advance. Actual filesystem write failures are
injected with temporary-directory conflicts inside new synthetic fixtures only.

22 guard rejection fixtures plus four competing monitor threads blocked until
callback completion, escaped/cross-thread/exception witness invalidation, and
exact matcher/account nonmutation on refusal. All tests SYNTHETIC, not market
profit/fills. New helper fields/methods exist only in copied generated sources;
original core and frozen policies/fees/queue/risk/acceptance remain untouched.

Run `python3 -m research.phase6.atomic_guard_build --output /tmp/new-guard-build`.
Exact prefix/generated SHA256 checks restrict edits to four generated classes.
Java build command and independent guard/default/no-order proof checks are in
`.github/workflows/atomic-no-order-guard.yml`. Full prior no-order differentials
and required reused-component/public-print counterexamples remain mandatory.

This is NOT identity-reader integration or a runtime no-order execution path.
The callback is not a blanket optimization permission or default service API.
Next: bind every ORIGINAL trade identity before expiry/filter, use the witness
only for the specific clock-only operation, preserve frame/advance-action order,
and record unknown unallocatable venue volume separately (never zero/aggregate).
Freeze and prove that exact integrated path before advancing original replay.
Actual source still stops628. Full candidate net UNKNOWN; PAPER/NO_GO.
