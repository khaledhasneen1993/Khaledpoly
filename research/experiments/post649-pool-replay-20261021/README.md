# Exact651 same-source baseline/QW0 replay

PAPER development evidence only. GitHub Actions run `39594036894`, job
`119201809874`, artifact `12344375720` completed from frozen commit
`eb3d6fc49653f90dbda15a309a8b3f3e0ae6201b`.

The unchanged original development recording was used once for baseline and
once for unchanged QW0 after the retained exact651 native gate passed. There
were no public reads, new capture, wallet, key, or real order.

- Baseline consumed 842 source identities and 9 known receipt bindings, then
  stopped fail-closed at seq `83144`. The next source observation is a tokenA
  `BUY 0.29`, size `23.517242`, transaction `0xc6a3d7…e89ad`.
- QW0 consumed 103 source identities and 5 known receipt bindings, then stopped
  fail-closed at seq `9305`. The next source observation is a tokenB `BUY 0.52`,
  size `5.865385`, transaction `0xd7b63a…99c07`.

Both stopped prefixes have zero executions, fills, allocated quantity, and
queue-absorbed quantity. All four PAPER orders were canceled safely. QW0's
actual queues remained `1182.3 / 180`; baseline's remained `0 / 0`.

The displayed cash 500, realized 0, and fees 0 are incomplete stopped-prefix
state, not a complete net result and not profitability evidence. Full net after
costs remains unknown. Decision is `NO_GO`; acceptance was not evaluated.

`ci-artifact.zip` is the retained 15-member report archive; SHA-256
`29393f1aaba3d6e461835bf759aacca8cf580a9bc2cb0233b9ed4711d23b2014`.
Next: obtain and verify only the two exact receipt targets above, then extend a
separately frozen pool before any further replay.
