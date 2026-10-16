# Synthetic accounting fixture

`synthetic.jsonl` is hand-constructed test data, not a Polymarket recording.
Five complete sets cost 4.50 and redeem 5.00, less an assumed 0.01 merge cost.
Expected cash: 500.49, net realized PnL: 0.49, three maker partial/full fills.
With stress activation of 1000ms, no orders are active before the fixture ends: zero fills.
These are arithmetic assertions, not evidence of an obtainable trading edge or profitability.

`closed-loop-synthetic.jsonl` contains public observations only (no recorded actions).
The shared strategy should generate two entry orders and merge five sets: expected cash 500.89,
net realized PnL 0.89. Stress activation occurs after the fixture ends, so cash stays 500.
This also is synthetic arithmetic, not historical profitability.
