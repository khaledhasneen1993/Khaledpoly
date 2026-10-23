# exact657 same-source baseline/QW0 replay

[Run 39879083129](https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39879083129), job `120171811779`, completed successfully from frozen commit
`2107cc15e421077cd95759d0c11aaf8c96a0e9f5`. The retained artifact SHA-256 is
`5612085b6dd82f6922100a83adf6b6e60f35b7aac85a0decd4041261fa3ca5d5`.

The unchanged original development tape and configuration were used once for
baseline and once for frozen QW0. Baseline stopped fail-closed at sequence
83208 after consuming 845 source identities and 15 exact657 bindings. QW0
stopped fail-closed at sequence 9662 after consuming 106 source identities and
8 bindings. Both encountered an execution-relevant unknown observation while
orders were active; the SOURCE_LAG0 witness correctly refused to assume zero
venue quantity.

Both stopped prefixes have zero executions, zero fills, zero allocated or
queue-absorbed known component quantity, and no holdings. Cash 500 and costs 0
are incomplete prefix state, not PnL. A complete account comparison was not
performed and full net performance remains UNKNOWN. Decision: PAPER/NO_GO.

The next bounded step is to verify only the two exact blocking receipts at
candidate sequence 9662 and baseline sequence 83208, then extend a separately
frozen pool before another replay. Do not alter the source-lag witness, infer
fills, retune QW0, weaken queue/fees/latency/risk, or inspect holdout.
