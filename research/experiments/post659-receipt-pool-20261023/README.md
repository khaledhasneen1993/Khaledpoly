# exact661 native/source parity evidence

[Run 39933500222](https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39933500222), job `120347296378`, completed successfully from frozen commit
`9fe55e84fb77ef24a3ac50a29b9d4a64c33d5d00`. The retained artifact SHA-256 is
`121b954d37d05191f7b7d2efa4c03bc1f7920d8e563e4189504fdd222b6e0b2c`.

The separate exact661 pool preserves all 659 parent bindings byte-for-byte and
adds only the two verified exact659 blockers: two MINT components. Totals are
661 bindings and 1564 components: `DIRECT 359 / MINT 1188 / MERGE 17`.

The Java reader consumed all 661 original identities, reproduced all 1564
component tuples, and passed 39 rejection guards. Pool, source-identity, and
portion hashes matched their frozen values. This run performed no tape replay,
market RPC, capture, wallet/key/order operation, account PnL calculation,
acceptance evaluation, parameter change, or holdout access.

This is structural evidence only. It proves neither fills nor profitability.
Complete net performance remains UNKNOWN and the decision remains PAPER/NO_GO.
The next bounded step is exactly one frozen same-source baseline/QW0 replay
against exact661 without retuning or weakening queue, fees, latency, or risk.
