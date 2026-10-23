# exact661 same-source baseline/QW0 replay evidence

[Run 39942073892](https://github.com/khaledhasneen1993/Khaledpoly/actions/runs/39942073892), job `120375686832`, completed successfully from frozen commit
`5c746033a3fa8712030d6b6c2e2408e92353ba17`. The retained artifact SHA-256 is
`68c9466fab20e14dd518e3f3bfbe1cb4cffbcde6cb79332aaa725000175c0172`.

The unchanged original development source was replayed once for baseline and
once for unchanged QW0 behind the exact661 native and generated-source gates.
Both profiles stopped fail-closed at the next unknown source identities and
canceled all PAPER orders.

- Baseline stopped at sequence 83262 after 847 source identities and 19 known
  receipt bindings. It had zero executions, fills, allocated quantity, and
  queue absorption; both actual queues remained zero.
- QW0 stopped at sequence 9982 after 108 source identities and 10 known receipt
  bindings. The conserved known components absorbed 9.55 shares of queue, so
  the first actual queue remained 1172.75. They produced no allocation,
  execution, holding, or fill; the second queue remained 180.

The `500` cash and zero fees are incomplete prefix state, not net performance.
The complete comparison remains false, full after-cost net remains UNKNOWN, and
the decision is PAPER/NO_GO. The next bounded step is to verify only the two new
receipt blockers before any pool extension or replay.
