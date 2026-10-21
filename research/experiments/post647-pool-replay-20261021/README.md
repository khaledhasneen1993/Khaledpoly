# Exact649 one same-source baseline/QW0 replay

PAPER development evidence only. GitHub Actions run `39558018680`, job
`119082298879`, artifact `12327320316` completed successfully from frozen
commit `138daeaa74929c4673247272d60b4e50d318bc53`.

The retained exact649 native-parity gate passed before the unchanged original
development recording was downloaded. Baseline and unchanged QW0 each ran
once. Both stopped fail-closed at the next unbound source-after-activation
observation:

- baseline: seq `83130`, transaction `0x172abaae63ece7822e54e3f6c2366f3dfd592fc2ed30e704ed5920e8849b0c0a`;
- QW0: seq `9227`, transaction `0x94a8d9be925c766f49a620ee72ce3ba072c15ed87653d868dd9c3616ea6d2226`.

The stopped prefixes contain zero fills, zero executions, no holdings and zero
fees. All four PAPER orders were canceled and both sessions halted. The shown
cash/realized values are incomplete prefix state, not a full account result or
evidence of profitability. Actual QW0 queues remained `1182.30 / 180`.

`ci-artifact.zip` is the exact retained workflow artifact. Its SHA-256 is
`ad53ff83b0015613368875b46fff651c37b646c439ad35e4f769e2138f95e4e1`.
`post647_pool_replay_result.py` revalidates its bounded contents and rejects
promotion to a completed comparison, PnL result, qualification or LIVE use.

Next: fetch and verify only the two identified public receipts and their
matching block headers. Do not repeat exact649, infer fills from public print
size, weaken queue/fees/risk, retune the strategy, or inspect holdout data.
