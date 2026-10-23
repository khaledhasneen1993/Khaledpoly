# Exact645 receipt pool — 2026-10-20

PAPER/development evidence only. The canonical pool preserves all 643 prior
bindings byte-for-byte and adds exactly the two raw receipts retained in
`postactivation-receipts-20261020`. It contains 645 source bindings and 1,534
actual maker components: DIRECT 355, MINT 1,162 and MERGE 17.

`summary.json` records the canonical logical hashes. `pool.json.gz` is only a
lossless retained transport of that pool. The generated `SOURCE_LAG0` helper is
pinned to the new pool hash; the new replay orchestrator requires consumption
of all 645 bindings on the complete 16,317-identity source index.

The local native parity probe matched all 645 source preimages and 1,534
conservative integer-derived tuples and passed 39 fail-closed reader guards.
The GitHub workflow deliberately does not download or replay the market tape.
Its retained Java 21 proof must exist before the separately predeclared single
same-source baseline/QW0 replay can run.

No model fill, queue allocation, account comparison, PnL, or independent PAPER
qualification is asserted here. Queue, fees, latency, risk, strategy and fixed
acceptance criteria are unchanged. LIVE remains disabled.

GitHub run `39478398235`, job `118820264563`, passed on Java 21: 29 Python
tests in 62.421 seconds plus all645/all1534 native parity and the39 reader
guards. Artifact `12291405729` has SHA-256
`279ef3b0a279c8dfc6ca0b722fcfaffcd8dc0a9c792374d7fd266712a34034bf`.
`native-proof.json` and `verification.json` retain the bounded result.
