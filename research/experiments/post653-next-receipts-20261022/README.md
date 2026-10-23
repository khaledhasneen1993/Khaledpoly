# exact653 next-two receipt evidence

Run `39823548337`, job `119980758578`, completed successfully from frozen
commit `7bbdb677202906abface96f43b53c37c335ae95b`. Thirteen offline tests and all
frozen dependency hashes passed before exactly one chain-ID read, two receipt
reads, and two matching-block reads. The retained archive SHA-256 is
`3f9febab2dbc952e6ea6d8c072b417d8df6bc80b9b07f608814da940130b1bdd`.

The candidate `seq 9379` receipt contains one conserved MINT group with three
maker BUY components on the complementary token: 5 shares at 0.48, 5 shares at
0.48, and 0.773585 shares at about 0.470000065. The recorded candidate bid on
that token was 0.47, so none passes the necessary price condition.

The baseline `seq 83158` receipt contains one conserved MINT group with one
maker BUY component on the complementary token: 28.52857 shares at 0.30. The
recorded baseline bid on that token was 0.24, so it does not pass the necessary
price condition.

These four public venue maker components are not bot fills. Queue allocation
remains unproven; model fills remain zero, account PnL was not recomputed, and
the decision remains PAPER/NO_GO. The next evidence-bounded step is a separate
frozen 655-binding/1557-component pool preserving all 653 prior bindings,
followed by native/source parity before any additional replay.
