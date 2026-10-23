# exact659 same-source baseline/QW0 replay evidence

[Run 39913163089](https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39913163089), job `120280580234`, completed successfully from frozen commit
`7e49e5a6ff2d779a666a0bdda937edb77fd2ae31`. The retained artifact SHA-256 is
`bddf259f8d999668f3cafcdadb99479d3c7c66f361f9a5d9ffc1812e23657cda`.

The unchanged original development source was replayed once for baseline and
once for unchanged QW0 behind the exact659 native gate. Both profiles stopped
fail-closed at the next unknown source identities and canceled all PAPER orders.

- Baseline stopped at sequence 83216 after 846 source identities and 17 known
  receipt bindings. It had zero executions, fills, allocated quantity, and
  queue absorption; both actual queues remained zero.
- QW0 stopped at sequence 9801 after 107 source identities and 9 known receipt
  bindings. The newly incorporated exact657 components conservatively absorbed
  9.55 shares of queue, reducing the first queue from 1182.3 to 1172.75. They
  produced no allocation, execution, holding, or fill; the second queue remained
  180.

The `500` cash and zero fees are incomplete prefix state, not net performance.
The complete comparison remains false, full after-cost net remains UNKNOWN, and
the decision is PAPER/NO_GO. The next bounded step is to verify only the two new
receipt blockers before any pool extension or replay.
