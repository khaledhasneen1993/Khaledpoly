# TWO exact post-activation receipt reads, NOT bot fills — 2026-10-20

Previous frozen SOURCE_LAG0 run39459692699 stopped original candidate9035 and
baseline82964 with source timestamps8ms and18ms AFTER actual activation. This
invalidates the temporal shortcut; no guard, risk, queue, fee or strategy change.

The new collection is fixed BEFORE reads to exactly these transactions:
- Candidate9035:0x740e975da87f07493fd104e7a8aecead4727eb365955e732c8bc3ff4f5972a1c
- Baseline82964:0x6fb0a9218d26394ca3ce7f6874218e38ed8f886ca60e1dd3a6b44f1f43446590

selection.json preserves exact original raw preimages and identity hashes from
the validated prior artifact. Public read-only RPC allowlist ONLY:eth_chainId,
eth_getTransactionReceipt,eth_getBlockByHash. Chain137 required, max2 receipts/
2 blocks, shared block caching, checkpoint after every successful response and
resume without refetching successful receipts. No keys/wallet/real orders.

Reuse reviewed ABI/exchange decoder and independent conserved maker-share/
collateral route checks; require unique original token/side/size group, public
rounded price consistency within.005 and block timestamp within120s of source.
Unknown/ambiguous/failed/removed/duplicate receipt data never becomes zero volume.
These are public-RPC corroborated settlement parts, NOT cryptographic finality
proof, original bot fills, queue allocation, market PnL or independent acceptance.

Local19 targeted offline tests PASS14.839s, including synthetic two-target
conservation, shared block budget, failed-block receipt checkpoint/resume, bad
selection/chain/status/hash/time refusal; existing receipt/route/source checks
unchanged. New frozen workflow performs ONLY these bounded reads after tests.
No original tape replay, new market capture, holdout or strategy tuning.

NEXT inspect this run/artifact and re-derive both routes offline before a
separately frozen expanded real pool/native reader. Existing pool643/components
1532 and SOURCE_LAG0 remain unchanged. Do not rerun the original tape unchanged.
Full net after costs UNKNOWN, PAPER/NO_GO, no independent acceptance passed.

## Actual public receipt run39468514569 COMPLETE SUCCESS

Frozen source1f2c7e9d0f1897ace68c0665b943663fd883f381,job118786128207.
19 targeted tests PASS14.733s before reads. EXACTLY1 chain-ID,2 receipt and2
block requests; both original identities uniquely conserved and corroborated.

Candidate9035:ONE DIRECT maker SELL on tokenB,3.846154 shares,2.000000 collateral,
price0.5199999792000008319999667200. Recorded orders were BUYs, so this component
fails their necessary side/token matching conditions; no eligible recorded order.

Baseline82964:ONE MINT maker BUY on tokenA,9.000000 shares,2.610000 maker
collateral,price0.29 (taker collateral6.390000). Recorded tokenA BUY bid0.24 is
below0.29; tokenB BUY differs in token. No recorded order passes necessary
token/side/price/source conditions. This is a receipt-specific comparison,
NOT original native replay, queue allocation, or a new runtime shortcut.

Artifact12286053123,15018 bytes,SHA256
b18b80b960a5de5273197fc04460f4a70224ead77d0307827c494ba5a4337e79
retained ci-artifact.zip (4 bounded members including both raw receipt/blocks).
postactivation_receipts_result.py independently re-decodes raw data and exact
source identity, rejects report/hash/volume/profit promotion, compares necessary
matching conditions to retained original orders. verification.json records real
parts2 and model fills0, no native pool extension, no account/PnL/qualification.

NEXT freeze a NEW645-binding/1534-component real pool preserving all643 old
bindings byte/logically unchanged, then native reader/source parity tests BEFORE
one new same-source baseline/QW0 comparison. Do not widen receipt reads or rerun
the unchanged source. No strategy/holdout/queue/fee/risk/acceptance adjustment.
This retention-only commit does not touch workflow/freeze or start another read.
