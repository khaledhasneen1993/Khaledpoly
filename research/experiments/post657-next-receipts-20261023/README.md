# exact657 next-two receipt evidence

[Run 39880064108](https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39880064108), job `120175016072`, completed successfully from frozen commit
`2c9e3cae0e4d4060493b040fadd89e99d8c4c21c`. Eight offline tests and all
frozen hashes passed before exactly one chain-ID read, two receipt reads, and
two matching-block reads. The retained artifact SHA-256 is
`8558b5feca3d6e7d544ccee9031e2e6d41665e981e043f7d23c0421812635508`.

Candidate sequence 9662 is one conserved MINT group with two maker BUY
components on the complementary token, totaling 9.55 shares at 0.47. This
matches the candidate's recorded 0.47 price but is far below its unchanged
1182.3-share queue ahead. It cannot fill the order; exact allocation must first
reduce the queue, never bypass it.

Baseline sequence 83208 is one conserved MINT group with one maker BUY
component: 10.344828 shares at 0.7100000115999995360000185600 on the complement
of a different market from the active PAPER orders. It cannot fill either
recorded order.

These three components are venue evidence, not bot fills. Model fills remain
zero, account PnL was not recomputed, and queue priority remains unproven. The
next bounded step is a separate frozen 659-binding/1562-component pool that
preserves exact657 byte-for-byte, followed by native/source parity before any
additional replay. Decision: PAPER/NO_GO; full net performance remains UNKNOWN.
