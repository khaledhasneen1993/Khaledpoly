# Selected DEVELOPMENT exit: independently reproduced, not account profitability

Frozen candidate source: `1b1ae2bfcd7d8981d5e9c70cbc0a1a7170925102`.
Native run: https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39296060855
Native artifact: https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39296060855/artifacts/12208620560

The manifest preserves exact ZIP, member, input and report hashes. The original
700843-byte input is reconstructed from retained source/receipts, not duplicated.
The Python verifier independently reads original source frames and conserved
receipt components; it derives decisions, due times, actual execution callback,
full-depth price/size and fees, rather than trusting the native result.

| Conditional first exit | Baseline | Frozen candidate |
| --- | ---: | ---: |
| Original entry basis (5 A) | $2.40 | $2.40 |
| Submitted post-GAP maker reductions | 14 | 0 |
| Post-GAP maker fills | 0 | 0 |
| Atomic SELL price | $0.49 | $0.52 |
| Proceeds before fee | $2.45 | $2.60 |
| Taker fee | $0.08747 | $0.08736 |
| Conditional round-trip net after costs | **−$0.03747** | **+$0.11264** |
| Uncovered shares after SELL | 0 | 0 |

Conditional improvement: **+$0.15011**, on the SAME previously selected
development position and source. No maker fill was added. Six original groups /
11 actual components precede candidate stop: 103.29 venue shares, all unused,
zero queue absorption or allocation. Candidate pending SELL is decided at
1792269761068 (original sequence 260911), due 1792269761318, actually executes
at 1792269761319 (261117). First FOK stops before re-entry or further strategy.
Fees, 250ms latency, 2x queues, minimum size, edge threshold and risk unchanged.

Reproduce from repository root:

```sh
python3 -m research.phase6.queue_aware_fee_positive_result
python3 -m research.phase6.queue_aware_exit_comparison
python3 -m unittest research.phase6.tests.test_queue_aware_fee_positive_result -v
```

`comparison.json` is NOT a full-account or unbiased strategy comparison. It
assumes the previously modeled 5 A position and available account risk. Other
markets/cash contention, all initial quotes, counter-leg lifecycle, subsequent
decisions, re-entry, and complete portfolio return are not simulated here.
The candidate is a research probe; canonical runtime has not been switched.
No holdout was inspected, no independent PAPER qualification is granted.
Acceptance remains unchanged; **NO_GO**. Full QW0 account return is UNKNOWN.
The known separate original full-account development control remains −$1.80.

## Next implementation, in dependency order

1. Keep original `CS-MINT-LAB0` adapter/frozen baseline unchanged. Add a separate
   bounded mixed-side research label adapter, revalidate retained actual receipt
   routes and all integer collateral/share conservation. Support DIRECT/MINT/BURN,
   BUY-UP/SELL-DOWN price boundaries, unique component identities, covered-tx
   duplicate suppression and fail-closed missing/ambiguous labels. Existing
   `SettlementReplayLabels` permits <=100 BUY-only public observations and uses
   HALF_EVEN component rounding: it cannot safely consume this 451-group context
   by merely raising its cap or renaming its experiment.
2. Integrate fixed QW0 entry plus frozen fee-positive exit into an explicitly
   opt-in research-only `ResearchSession` path. Preserve production/default
   behavior, canonical ledger, shared account risk, cancel ACK precedence,
   pre-event activation queues, GAP handling, cash, fees and actual merge costs.
   `reduce()` currently treats every non-COMPLETE choice as maker; an added SELL
   branch also needs the net-positive check in `executePending()`, not just a
   policy action-string change. No injected conditional holding in account runs.
3. Validate each canonical ledger transition against existing independently
   reproduced prefix/exit evidence. Replay baseline and frozen candidate from
   the SAME complete development tape, starting cash and same coverage. Do not
   concatenate selected snippets into an account or assume unobserved trades
   fill. If complete validated coverage is absent, report that bound explicitly;
   a conservative partial-label no-fill result cannot establish profitability.
4. Freeze the integrated executable/config and predeclare independent evaluation
   before collecting fresh multi-market PAPER. Use the unchanged acceptance
   evaluator, all fees/gas/stress, drawdown and residual inventory. Do not tune on
   that evaluation or relabel it development after observing outcomes.

Do not rerun this same conditional native experiment, request the same receipts,
or scan the original full tape again solely to reproduce these retained proofs.
