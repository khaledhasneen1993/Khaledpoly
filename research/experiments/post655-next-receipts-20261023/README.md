# exact655 next-two receipt evidence

Run `39866806342`, job `120130927083`, completed successfully from frozen
commit `edddb83d9ac780a00e0d72b2036bd13d15a386de`. Thirteen offline tests and all
frozen dependency hashes passed before exactly one chain-ID read, two receipt
reads, and two matching-block reads. The retained archive SHA-256 is
`74879c410a4826b3284c2dae5574001e869c25b996ac08d528b6c4175ffb42fc`.

Candidate `seq 9496` is one conserved MINT group with one maker BUY component
on the complementary token: 30 shares at 0.51. The recorded candidate bid on
that token was 0.48, so it does not pass the necessary price condition.

Baseline `seq 83182` is one conserved MINT group with one maker BUY component
on the complementary token: 10.25 shares at 0.30. The recorded baseline bid on
that token was 0.24, so it does not pass the necessary price condition.

These two public venue maker components are not bot fills. Queue allocation
remains unproven; model fills remain zero, account PnL was not recomputed, and
the decision remains PAPER/NO_GO. The next evidence-bounded step is a separate
frozen 657-binding/1559-component pool preserving all 655 prior bindings,
followed by native/source parity before any additional replay.