# Frozen QW0 + fee-positive exit integrated — no market profitability result

2026-10-20 Asia/Amman (2026-10-19 UTC). Parent `faa6407d4787af5c5d1fd2e15dc094b5f4c391b9`.
Prior bridge CI39322057044 completed SUCCESS:273 tests and canonical session
guards/default parity. No active experiment overlapped this work.

## Implemented

The exact causal QW0 quote admission/queue objective and frozen fee-positive
COMPLETE-versus-TAKER_SELL choice now run inside the actual `ResearchSession` in
an explicitly enabled offline source profile. No normal service flag was added.
The second tracked source patch composes on the immutable label-bridge patch;
all94 original core sources remain untouched. Both generated stage hashes and
every unchanged core file are verified. The earlier build provenance is the
label-bridge PREFIX; `strategy-build-provenance.json` is the final profile's
authoritative provenance, including that prefix.

`enableFrozenResearchPolicies` requires the explicit mixed-label offline session,
empty fresh ledger, pre-first-observation state and no prior enablement. It cannot
enable on default/null labels, external mode, existing inventory/orders or after
observations. Default-off complete report parity still holds.

QW0 uses only contemporaneous displayed top3 levels and the original top-depth
quantity, metadata/book freshness, threshold, thin-depth reserve, cash/portfolio
and residual loss budgets. Its objective and deterministic ties are unchanged.
No original sequence/time/condition is hardcoded to force the selected quote.
The Java port omits a redundant DQ3 existence call: QW0's reserve is nonnegative,
so every otherwise-identical admitted QW0 pair already passes the DQ3 floor.
Original resting maintenance, cancellation, ledger reservation and shared risk
checks remain in the canonical session, not an observer's abbreviated lifecycle.

The exit port chooses the unchanged argmax rule only without open orders and
before overdue risk handling. TAKER_SELL is not routed back to maker reduction.
Actual delayed full-depth FOK execution now recognizes POSITIVE_EDGE_EXIT and
rechecks unchanged minimumEdge*quantity AFTER fees. Original overdue choices,
exit-loss cap, minimum size, cash, source-data and depth checks remain intact.

## Evidence

- All42 FULL quote proposals/admissions match the immutable Python reference:
  the SAME34 previously selected DEVELOPMENT witnesses plus8 synthetic cases.
- All18 fee-positive/overdue choice cases match the fixed reference exactly.
- Default-off entire canonical report remains equal to the untouched-core proof.
- Explicit synthetic account run creates its own QW0 entry orders. Both entry
  queues are200 (100 displayed*original2x); a300-share SYNTHETIC conserved
  component consumes200 queue, allocates5 and leaves95 unused. No holdings are
  injected and no queue/size/fee parameter is relaxed.
- Strategy waits for the unfilled counterpart cancellation ACK, plans sell at
 6821ms, executes at7071ms after unchanged250ms latency. With5 shares at0.44,
  actual fee0.08624 and basis2, the synthetic account's realized net is0.11376.
  **This number is a unit-test expectation, NOT market PnL or candidate return.**
- A separate adverse-price fixture keeps execution inside the FOK limit at0.42,
  but net0.01474 is below the unchanged0.05 total edge floor. Native session
  rejects TAKER_NET_EDGE, charges no fee and leaves5 shares/cash498 intact.
  It does not manufacture a profitable exit or erase the uncovered inventory.

Five new Python tests reject quote/choice drift, queue/fee/risk changes, a disabled
execution-net guard, default behavior changes and market/live scope escalation.
Java17 compiles the complete94-source generated core plus research helpers.
The Java21 CI workflow repeats all regressions, parity and synthetic session
tests. No fresh tape, RPC requests or selected-development strategy rerun occurs.

## Reproduce / next work

```sh
python3 -m research.phase6.strategy_profile_build --output /tmp/new-frozen-policy-source
python3 -m research.phase6.frozen_policy_result
python3 -m unittest research.phase6.tests.test_frozen_strategy_profile -v
```

This completes rule wiring in the explicit research profile, not whole-account
market evaluation. Next implement a fail-closed canonical whole-tape runner and
coverage audit before comparing baseline/candidate on the SAME complete source.
The451-observation recovery labels cover one pair/window, not all tape/portfolio
observations. Unknown observations must block/identify missing coverage, never
be silently treated as zero volume or added on top of aggregate prints. Preserve
all account cash/inventory, re-entry, resolution/merge costs and original frames.
Only after coverage/transition proof, compare full-account development outcomes;
then freeze integrated executable/config before independent multi-market PAPER.
Do not retune on that evaluation or alter acceptance.

No new MARKET net PnL. Old selected conditional exit remains+$0.11264 versus
-$0.03747; separate original full-account control-$1.80 after costs. Full QW0
market account UNKNOWN. NO_GO; PAPER only; PR9 unmerged and follow-up continues.
