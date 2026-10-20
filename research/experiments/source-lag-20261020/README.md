# Source-lag mathematical proof ONLY — 2026-10-20

This is a new bounded investigation, NOT a new execution profile. PRE_ACTIVATION0
still stops the actual original tape at baseline82880 and candidate8739. No new
runtime shortcut, session guard, original replay, RPC, capture or holdout run.

SourceLagDifferentialProof compares canonical acceptSettlement with canonical
TICK for643 REAL conserved component tuples inside8 SYNTHETIC timing/order
contexts:active source66ms early, source exactly at actual activation, due-at-
arrival equality, delayed actual activation,2 orders with different activation
times, cancel due at activation tie, pending cancel, stale active book. All5144
updates and all non-settlement private matching fields match;5144 distinct
future component continuations also match.111 synthetic future fill events are
coverage evidence ONLY, never fills/profit on original market data.

The proof checks queue100 times2=200, second own order ahead205, cancellation
winning activation ties and canonical stale-book cancellation. It deliberately
EXCLUDES exactly5 settlement bookkeeping fields, so whole matcher state is NOT
equivalent. Omitting an unknown transaction does not mean zero venue volume.

Three required counterexamples PASS:
- Source1ms AFTER activation can produce a synthetic fill; never skip that case.
- A NEWEST-order cutoff is unsafe:the older order can consume the component.
  ALL existing orders must satisfy their OWN actual activated timestamps.
- Repeated components change future fills; exact full-source global component/
  transaction uniqueness remains essential, not optional.

9 reflected MATH-predicate refusals cover source-after-activation, future/
negative source, clock regression, older eligible order, pending/due cancel,
SELL and empty exposure. Cancel/stale differential contexts establish canonical
ordering only; the proposed predicate STILL refuses cancel exposure. It is NOT
an atomic guard and does NOT inspect or authorize ledger/session/persistence.

The previous original frontier verifier is reused offline:baseline source49ms
before actual activation; candidate66ms. Actual candidate queues1182.30/180
are retained without replacing them by decision proxies160/240 or testqueue200.
Previous full net remains UNKNOWN, no new market/account comparison or costs.

Next:ONLY after this frozen Java21 proof is reviewed, add a SEPARATE generated
source-lag session witness, preserving all4 monitors, exact OPEN reservations,
flat holdings, no FOK/unhedged/cancel/failed persistence/recovery/external mode,
and all-order actual-activation cutoff. Test both real frontier preimages in a
clearly synthetic session envelope and unsafe older-order/source+1 countercases.
Then one separately frozen original-development baseline/QW0 comparison may be
justified. Do not launch unchanged PRE_ACTIVATION0 replay. No strategy tuning.
No independent qualification, acceptance/config unchanged, PAPER/NO_GO.

Local verification:50 targeted Python tests PASS (32.735s), including13 evidence
mutation cases. Java17 complete96 generated source/helper compile PASS; prior
5144 PRE_ACTIVATION0 differentials and22 atomic guard cases PASS unchanged;
DEFAULT report equals frozen before oracle. New workflow repeats on Java21.
