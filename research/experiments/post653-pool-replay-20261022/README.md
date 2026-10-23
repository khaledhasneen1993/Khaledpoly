# Exact655 one same-source baseline/QW0 replay

PAPER development evidence only. GitHub Actions run `39838068117`, job
`120031524797`, artifact `12452921077` completed from frozen commit
`aa5fde77810f87f35c51891215c377e1bd310f30`.

Both profiles used the same unchanged original development recording and the
same 655-binding/1,557-component native pool. The candidate is the previously
frozen unchanged QW0 profile. No parameter, queue, fee, latency, risk,
acceptance, or holdout setting changed.

The baseline consumed 844 source identities and 13 known bindings before
failing closed at sequence 83182. The candidate consumed 105 identities and 7
known bindings before failing closed at sequence 9496. Both PAPER sessions had
zero fills, executions, holdings, allocated quantity, and queue absorption. All
four orders were cancelled and both sessions halted with no open order.

Candidate queues remained 1,182.3 and 180 shares; baseline queues remained zero.
The stopped-prefix ledgers show cash 500, realized 0, and fees 0. Those are
incomplete prefix states and are not complete net performance or profitability
evidence.

`ci-artifact.zip` is the exact retained 15-member workflow artifact; SHA-256
`3cbcae2290504df78c99efe7771bb9183f4c7ea0dfb63f231493ddd7e2ab6c90`.
`post653_pool_replay_result.py` verifies its size, digest, next blockers, native
consumption, conserved volume, actual queues, cancellations, and non-promotion
guards.

Complete account comparison remains false; complete net after costs is unknown
and the decision is `NO_GO`. Next: obtain and verify only the two exact receipt
targets at sequences 9496 and 83182, then extend a separately frozen pool before
any further replay. Do not infer fills or weaken queue, fee, latency, or risk
assumptions.
