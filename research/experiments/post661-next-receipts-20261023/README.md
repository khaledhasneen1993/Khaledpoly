# exact661 next-two receipt audit

[Run 39947597650](https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39947597650), job `120393955041`, completed successfully from frozen commit
`8f344683943fc6eb36e8496929906e54e668c0c7`. Thirteen frozen/offline tests
passed before exactly one chain-ID, two receipt, and two matching-block public
read-only calls. Artifact `12498488616` is 16887 bytes with GitHub-recorded
SHA-256 `73f345474c5282c24c5d617dc6a151c2d840ee0cf2cf1b7712dcb689ce932330`.

Candidate `seq 9982` is one conserved 30-share group: DIRECT SELL 5 on the
candidate token at 0.52, plus complementary MINT BUY components totaling 25 at
0.48. Neither route is price-compatible with the active PAPER bids (candidate
token 0.48; complement 0.47). Therefore this receipt provides no necessary
queue debit or fill evidence for QW0.

Baseline `seq 83262` is one conserved 50.882353-share group: DIRECT SELL 15 on
the original token at 0.33, plus complementary MINT BUY components totaling
35.882353 at 0.67, 0.67, 0.66, and 0.6600000226666651555556562963. The DIRECT
component is not compatible with the 0.24 bid. The complementary MINT
components are price-compatible with the other 0.71 PAPER bid, but this audit
does not prove queue priority, allocation, or a bot fill.

The workflow created zero model fills, did not simulate an account, did not
extend the native pool, and did not recompute PnL. Full after-cost net remains
UNKNOWN and the decision remains PAPER/NO_GO. The next bounded step is a
separate exact663 pool preserving exact661 byte-for-byte and adding only these
two audited bindings (10 components), followed by native/source parity before
any replay.
