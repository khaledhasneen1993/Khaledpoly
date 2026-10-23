# Exact647 one same-source baseline/QW0 replay

GitHub Actions run `39522503331`, job `118969423264`, completed successfully.
The workflow passed retained exact647 native-parity and frozen-input gates, then
downloaded the unchanged original development recording once and ran exactly
baseline followed by unchanged QW0. This is development evidence, not
independent qualification.

Both profiles stopped fail-closed at their next unknown source-after-activation
receipt. Baseline stopped at seq 83030 after 840 source identities and 5 known
bindings; QW0 stopped at seq 9082 after 101 identities and 3 known bindings.
Both had zero executions/fills/holdings, all four paper orders were canceled,
and no market net PnL was recomputed. The unchanged prefix cash/realized/fees
values (500/0/0) are not performance evidence.

Artifact `12311956727` is retained as `ci-artifact.zip`, 13,728 bytes, SHA-256
`a099ab48097b06477009e27a55ddaa95ec6808b95c239c7bff97a412bc453a8e`.
The verifier checks exact next targets, conserved known component volume,
actual queues, fail-closed cancellation, zero fills, and non-promotion.

Next: obtain and verify only the two exact new receipts, then extend a separately
frozen pool before any further replay. Do not repeat exact647, infer fills,
retune strategy, change holdout, or weaken queue/fees/risk.
