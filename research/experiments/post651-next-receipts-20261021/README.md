# Exact651 next two public receipts

PAPER evidence only. GitHub Actions run `39601135971`, job `119225630940`,
artifact `12346192183` completed successfully from frozen commit
`53a88f7b58a7dbedd832740f58bb088a9bba9791`.

The workflow made exactly one `eth_chainId`, two
`eth_getTransactionReceipt`, and two matching `eth_getBlockByHash` public
read-only calls after 13 offline tests. It did not replay a tape, capture a new
market, use a wallet/key, submit an order, extend the native pool, or compute
account PnL.

- QW0 seq `9305`: one conserved `MINT` group with one maker `BUY` complement
  component at about `0.48`, totaling `5.865385` shares. No recorded QW0 PAPER
  order passes the necessary source-time, side, token and price conditions.
- baseline seq `83144`: one conserved `MINT` group with two maker `BUY`
  complement components at about `0.71`, totaling `23.517242` shares. No
  recorded baseline PAPER order passes those necessary conditions.

These three public venue maker components are not bot fills. Exact queue
allocation is not proven. Model fills remain zero and full net performance
after costs is unknown.

`ci-artifact.zip` is the exact retained four-member workflow artifact; SHA-256
`3cb5b02414a81e5fca39f81d56ab536c4e4d44cd8f8c3aa62a28274cdaad1eb9`.
`post651_next_receipts_result.py` re-decodes the raw receipts and blocks, checks
the retained source identities and necessary matching predicates, and rejects
promotion to PnL, account comparison, qualification or LIVE use.

Next: extend a separately frozen 653-binding/1553-component pool preserving all
651 prior bindings, then prove native/source parity before any further replay.
