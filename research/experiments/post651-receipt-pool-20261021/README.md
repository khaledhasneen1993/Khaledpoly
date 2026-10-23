# Exact653 native receipt-pool parity

PAPER development evidence only. GitHub Actions run `39645215982`, job
`119378862118`, artifact `12366354781` completed successfully from frozen commit
`394ceafc926f9f4ac8dd94cfe44270472115ff68`.

The extension preserves all 651 previous bindings byte-for-byte and adds only
the two previously retained and independently decoded receipts: three `MINT`
components. The resulting multi-market pool has 653 bindings and 1,553
conserved components: 359 `DIRECT`, 1,177 `MINT`, and 17 `MERGE`.

The Java reader consumed all 653 original identities and reproduced all 1,553
component tuples. It passed 39 rejection guards. Pool, source-identity, and
portion hashes all match the frozen values. The unchanged exact651 source bridge
was generated from pinned commit `2f47b7110908bd9311d410be75dd0173b14f04d7`
so its historical freeze was neither weakened nor rewritten.

`ci-artifact.zip` is the exact retained two-member workflow artifact; SHA-256
`b5fa03262248f0115006c776f798f4f590c7dc0bb1e50e8f98ee3c02fd39a338`.
`post651_pool_result.py` verifies its size, digest, members, native report, and
non-promotion guards.

This run did not replay the tape, access market RPC, capture a market, use a
wallet or key, submit an order, compute account PnL, or evaluate acceptance. It
is not profitability evidence. Decision remains `NO_GO`; complete net after
costs is unknown.

Next: freeze exactly one same-source baseline/QW0 replay against this exact653
pool, without retuning, inspecting holdout, or weakening queue, fee, latency, or
risk assumptions.
