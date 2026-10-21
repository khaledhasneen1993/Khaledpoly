# Exact649 next two public receipts

PAPER evidence only. GitHub Actions run `39562983382`, job `119098396467`,
artifact `12328971016` completed successfully from frozen commit
`91e0b30c70189ac93b72f0fad34c5320d1c464e3`.

The workflow made exactly one `eth_chainId`, two
`eth_getTransactionReceipt`, and two matching `eth_getBlockByHash` public
read-only calls after 13 offline tests. It did not replay a tape, capture a new
market, use a wallet/key, submit an order, extend the native pool, or compute
account PnL.

- QW0 seq `9227`: one conserved `MINT` group with eight maker `BUY` tokenA
  components, all at `0.48`, totaling `66.79` shares. The recorded tokenA PAPER
  bid was `0.47`, so none passes the necessary price condition.
- baseline seq `83130`: one conserved `MINT` group with two maker `BUY` tokenA
  components at `0.32` and `0.30`, totaling `31.37` shares. The recorded tokenA
  PAPER bid was `0.24`, so neither passes the necessary price condition.

These are public venue maker components, not bot fills. Exact queue allocation
is not proven. Model fills remain zero and full net performance after costs is
unknown.

`ci-artifact.zip` is the exact retained four-member workflow artifact; SHA-256
`19634d571efb8ab38b34518a7371a781990c5082343b91d82bb1eb8f8786cbfc`.
`post649_next_receipts_result.py` re-decodes the raw receipts and blocks, checks
the retained source identities and necessary matching predicates, and rejects
promotion to PnL, account comparison, qualification or LIVE use.

Next: extend a separately frozen 651-binding/1550-component pool preserving all
649 prior bindings, then prove native/source parity before any further replay.
