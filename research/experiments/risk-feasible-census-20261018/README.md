# Complete saved-census risk feasibility — 2026-10-18

Development analysis only. No new trading variant, tape scan, RPC, capture,
account replay, execution inference or acceptance change.

`report.json` reuses ALL saved necessary-condition examples: original84 and
fresh590, with no truncation. Source counts equal exported route/policy counts.
Recover the missing census quantity by enumerating the lawful .01 share grid
and exactly reproducing its exported Decimal edge expression. Require one
solution; all674 recover5 shares. This does NOT recover original market
metadata or prove actual order quantity/state at a decision.

Apply existing `residual_entry_risk.assess(enabled=True)` with the UNCHANGED
maximum unused exit-loss budget2.50 and redemption cost.01. Actual remaining
account budget could be smaller, so this is an upper-bound feasibility screen.
No quote policy, size, risk allowance, queue or latency is optimized.

| Recording / previously tested quote policy | All necessary observations | Pass risk upper bound |
| --- | ---: | ---: |
| Original / improve1 | 12 | 1 |
| Fresh / improve1 | 43 | 4 |
| Original / join0 QB0 | 72 | 1 |
| Fresh / join0 QB0 | 547 | 13 |

Counts mix route screens and policies, not unique executions, feasible fills or
entry opportunities. Passing MINT candidates still require actual receipt
route confirmation; public complement arithmetic alone does not supply it.

All four surviving fresh improve1 observations are outside the actual guarded
orders' matching active lifecycle: the first source precedes submission; the
other three arrive after actual cancellation. The two last sources are7ms
apart. No fresh guarded execution was overlooked by these examples.

Join0's thirteen fresh and one original survivors had NO matching outstanding
BUY order at that price even in the historical UNGUARDED QB0 run. Compare actual
submitted/terminal intervals first, and source>=actual activation separately;
do not substitute activationDueMs. These are historical QB0 diagnostics, NOT a
new combined QB0+guard account replay or proof of its counterfactual behavior.
No reason to fetch these receipts simply to make nonexistent own orders fill.

Conclusion: the remaining bottleneck is causal entry availability/readiness,
not evidence for missing route-credit at already active own quotes. We cannot
separate decision timing, dynamic risk, metadata/depth and short validity windows
from the saved census alone. Do NOT disable those constraints or declare a
combined pricing+risk candidate promising from these counts.

Next diagnostic: obtain bounded PRE-DECISION witnesses for the surviving
timestamps (all listed in report), including original metadata/minimum size,
bid/ask depth and sources, actual decision clock, observed volatility and
dynamic threshold, pending/active orders and intervening GAPs. Reuse original
context where available; never initialize missing volatility to zero. Inspect
the two improve1 fresh observations at1792269724135/1792269724142 together and
the remaining QB0 clusters, not another repeat of the completed254ms interval.
Only then predeclare ONE change if a causal blocker supports it; no blind
combined replay, receipt batch, new current-market capture or holdout tuning.

Known corrected account economics remain control-$1.80 and guarded0/zero fills,
undefined pair completion: NO_GO. Historical QB0 remains rejected. No independent
qualification evidence or updated economic calculation is produced here.

Reproduce from the repository root:

```sh
python -m research.phase6.risk_feasible_census --output /tmp/risk-feasible-census.json
python -m unittest research.phase6.tests.test_risk_feasible_census -q
python -m unittest discover -s research/phase6/tests -q
```

`risk-feasible-census-freeze.json` binds all analysis/input/report-source files,
unchanged configuration and acceptance.159 phase6 tests passed locally; this
is not a new full Java build or a claim that these159 tests ran in CI.
