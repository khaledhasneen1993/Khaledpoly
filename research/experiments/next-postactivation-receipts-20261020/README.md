# Exact645 next two public receipts

This folder retains the bounded, public, read-only evidence produced by GitHub
Actions run `39481141401` (job `118829716023`) at source commit
`94021314a6f63809237ed1c7dc20f7b30ffd1d96`.

- Artifact `12290764619`, 14,356 bytes
- SHA-256 `bfc9043ca0ca851914b90aa388967d7eba7c7b6db0f906927b16356f04a2dcf1`
- Exactly one chain-ID, two receipt, and two block requests
- Candidate coordinate 9060: one conserved DIRECT maker SELL component,
  38.461539 shares at public maker price approximately 0.52
- Baseline coordinate 82986: one conserved DIRECT maker SELL component,
  40 shares at public maker price 0.32

`verification.json` is independently re-derived from the two raw receipts and
the retained exact645 replay identities. Both receipt components fail the
necessary recorded-order side predicate: the recorded PAPER quotes are BUY,
while the actual maker components are SELL. Therefore these are public venue
routes, not bot fills. Queue allocation, account replay, and net PnL were not
computed. Acceptance was not evaluated and the decision remains `NO_GO`.

No wallet, key, funds, live order, capture, holdout access, strategy tuning, or
replay occurred in this evidence run.
