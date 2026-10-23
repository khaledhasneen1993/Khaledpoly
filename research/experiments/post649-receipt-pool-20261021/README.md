# Exact651 native receipt-pool parity

PAPER development evidence only. GitHub Actions run `39572013713`, job
`119128270610`, artifact `12331629082` completed successfully from frozen commit
`987e4de98e5ea8ec12ab7f16ea63575e33f32768`.

The extension preserves all 649 previous bindings byte-for-byte and adds only
the two previously retained and independently decoded receipts: ten `MINT`
components. The resulting pool has 651 bindings and 1,550 conserved components:
359 `DIRECT`, 1,174 `MINT`, and 17 `MERGE`.

The Java reader consumed all 651 original identities and reproduced all 1,550
component tuples. It passed 39 rejection guards. Pool, source-identity, and
portion hashes all match the frozen values.

`ci-artifact.zip` is the exact retained two-member workflow artifact; SHA-256
`b50b77dcd5de6c23f6050a46104b54adebb7e4fc333bf49b7701eb9bc186e3e7`.
`post649_pool_result.py` verifies its size, digest, members, native report, and
non-promotion guards.

This run did not replay the tape, access RPC, capture a market, use a wallet or
key, submit an order, compute account PnL, or evaluate acceptance. It is not
profitability evidence. Decision remains `NO_GO`; complete net after costs is
unknown.

Next: freeze exactly one same-source baseline/QW0 replay against this exact651
pool, without retuning, inspecting holdout, or weakening queue, fee, latency, or
risk assumptions.
