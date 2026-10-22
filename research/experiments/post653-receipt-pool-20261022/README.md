# Exact655 native receipt-pool parity

PAPER development evidence only. The first workflow attempt failed only because
the three-day `entry-witness-executor` artifact had expired. Commit
`8b144dce428b39c5e8081f3648f5338b496ac28e` replaced that download with a build
from the same pinned source commit, retaining the original executor JAR SHA-256
gate. GitHub Actions run `39835654997`, job `120023157665`, artifact
`12451735626` then completed successfully.

The extension preserves all 653 previous bindings byte-for-byte and adds only
the two previously retained and independently decoded receipts: four `MINT`
components. The resulting multi-market pool has 655 bindings and 1,557
conserved components: 359 `DIRECT`, 1,181 `MINT`, and 17 `MERGE`.

The Java reader consumed all 655 original identities and reproduced all 1,557
component tuples. It passed 39 rejection guards. Pool, source-identity, and
portion hashes all match the frozen values. The unchanged exact653-compatible
source bridge was generated from pinned commit
`2f47b7110908bd9311d410be75dd0173b14f04d7`; the dependency container was built
from pinned commit `6dc5f25aec764ae55ecf0610a617baba77b7a6f7` and accepted only after matching
the previously frozen executor JAR SHA-256.

`ci-artifact.zip` is the exact retained two-member workflow artifact; SHA-256
`9de488b2932dba7e8e631ad37e43dd70f47c43caa32112ffa57208440bed3640`.
`post653_pool_result.py` verifies its size, digest, members, native report, and
non-promotion guards.

This run did not replay the tape, access market RPC, capture a market, use a
wallet or key, submit an order, compute account PnL, or evaluate acceptance. It
is not profitability evidence. Decision remains `NO_GO`; complete net after
costs is unknown.

Next: freeze exactly one same-source baseline/QW0 replay against this exact655
pool, without retuning, inspecting holdout, or weakening queue, fee, latency, or
risk assumptions.
