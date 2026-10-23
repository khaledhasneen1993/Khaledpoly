# exact657 native/source parity evidence

Run `39874579658`, job `120156941028`, completed successfully from frozen
commit `aeade9975aa847894f93a09a6585b62dae065350`. The retained artifact SHA-256
is `6c07967f7b302dfed43f8faf36a75955b318e1536b1daf2318e559033be38495`.

The separate pool preserves all 655 parent bindings byte-for-byte and adds only
the two previously verified exact655 blocker receipts. The resulting 657
bindings contain 1559 conserved components: 359 DIRECT, 1183 MINT, and 17
MERGE. The Java reader consumed all 657 original identities, reproduced all
1559 tuples, and passed 39 rejection guards.

This was offline native/source parity only. No tape replay, market RPC,
capture, wallet, key, order, fill, account PnL, acceptance evaluation, strategy
parameter, or holdout change occurred. Complete net performance remains
UNKNOWN and the decision remains PAPER/NO_GO. The next bounded step is exactly
one same-source baseline/QW0 replay against frozen exact657.
