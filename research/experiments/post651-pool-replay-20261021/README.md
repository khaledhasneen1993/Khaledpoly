# Exact653 one same-source baseline/QW0 replay

PAPER development evidence only. GitHub Actions run `39654814359`, job
`119412159026`, artifact `12371311452` completed successfully from frozen commit
`84ff7ae2967a133b630499ad7ccbbffb0c5d1e2e`.

The unchanged original development recording was replayed once for baseline and
once for the already frozen QW0 candidate through the exact653 pool. Both paths
stopped fail-closed at the next unknown receipt rather than treating incomplete
coverage as zero venue volume or a fill.

Baseline consumed 843 source identities and 11 known bindings, then stopped at
seq 83158. QW0 consumed 104 source identities and 6 known bindings, then stopped
at seq 9379. Both prefixes have zero executions, fills, allocated quantity,
queue-absorbed quantity, holdings, and fees. All four PAPER orders were canceled.
QW0's actual remaining queues stayed 1182.30 and 180; baseline queues stayed 0
and 0. Prefix cash 500 and realized PnL 0 are not complete account performance.

`ci-artifact.zip` is the exact retained 15-member workflow artifact; SHA-256
`46eb57490c0b64e2f21ed89d3ee04fcf827100a679972e28ca5a8f91b754e142`.
`post651_pool_replay_result.py` verifies identities, counters, conserved volume,
queues, cancellations, frozen configuration, and non-promotion guards.

No public read, market capture, wallet, key, real order, retuning, holdout access,
or queue/fee/latency/risk weakening occurred. The comparison is incomplete;
complete net after costs remains unknown and the decision is `NO_GO`.

Next: fetch and verify only the two fixed receipt/block targets at seq 9379 and
83158, then extend a separately frozen pool before any further replay.
