# Exact647 next two receipts

Run `39528071948`, job `118987298870`, fetched only the two frozen Polygon
receipts and their two blocks after offline provenance tests. The artifact has
four bounded members, 15,415 bytes, SHA-256
`126a6379abcfcebdee895aaedf387a6e1323f89114878aeccee6984c9d43d4c6`.

Candidate seq 9082 conserves two DIRECT maker SELL components totaling
38.461539 token-B shares. Its recorded PAPER token-B order is BUY, so neither
component passes the necessary side condition. Baseline seq 83030 conserves two
MINT maker BUY token-A components totaling 28.76 shares at maker prices 0.29
and 0.27. Its recorded token-A PAPER bid was 0.24, so neither component passes
the necessary price condition.

These are public venue routes, not bot fills. Queue allocation remains unproven,
model fills remain zero, and no account PnL was recomputed. Next: extend a
separately frozen exact649 pool (649 bindings, 1540 components), preserving all
647 prior bindings, then prove native/source parity before another replay.
