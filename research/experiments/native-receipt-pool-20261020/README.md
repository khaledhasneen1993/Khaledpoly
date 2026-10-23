# Strict native partial-pool reader and synthetic session bridge

Preflight be81835 / draft PR9; run39354913586 SUCCESS,299 GitHub tests
in372.989s and byte-exact cached pool/report regeneration. No overlapping Action.
No new original-tape scan, market capture, receipt request or real order.

## Original source/native proof (NOT an account replay)

Recover EXACT original tradeId byte strings for ALL642 known bindings from
retained original observation samples, including191 reviewed cached observations
and451 recovery observations. Require one SHA256-matching preimage per binding,
and exact token/side/price/size/source facts. No tx-only replacement or guessed
identity serialization is accepted if its original hash differs. Generated
source-identities SHA256:
`2c849a88837b0724e71bfc02bcddbbfa28da238a5ee2fe4c7f325236b3501056`.

New separate ConservedReceiptPool validates the frozen PARTIAL envelope, proven
static condition/pair identity, bounded sorted unique coordinates/txs, allowed
exchanges, positive uint256 amounts, one matching group, DIRECT/MINT/MERGE side
rules, integer shares AND collateral conservation and global unique components.
Converts to original canonical Binding/Portion records; BUY rounds UP28 digits,
SELL DOWN28. Native consumption of ALL642 original identities yields exactly
ALL1,516 tuples from Python, digest:
`3fd8f2d4ce916cd2a70919431e81ec878cb26e94ad7e293ff81e515f6bce092c`.

Unknown coordinate for ANY token/market throws, INCLUDING a previously known
transaction at a different coordinate. No null, empty binding, duplicate
suppression, unrelated-market aggregate fallback or zero-volume interpretation.
Known identity must match actual tradeId bytes, seq/index/arrival/source/token/
side/price/size/tx. Successful consumption happens once; any failed resolve
poisons the reader and further input fails. requireConsumed rejects incomplete
or failed readers.39 native rejection guards plus2 extreme rational rounding
boundaries pass. Native reader creates no market orders or allocations here.

## Source-built session connection (SYNTHETIC ONLY)

Implements the EXISTING generic OfflineSessionLabels protocol and explicit
MIXED_BINDING_BRIDGE0 profile. Existing interface/window adapters,94 original
core sources, two frozen research source patches, policies and config unchanged.
No legacy complete-window flag is forged to satisfy an older constructor.
Frozen producer artifact still correctly retains its historical consumer=false
claim; NEW native proof reports nativePartialPoolReaderImplemented=true.
This does NOT assert complete source coverage or a finished market runner.

Compile the94-source frozen research variant, new reader and helpers. Default-
off complete native report still equals the original untouched-core oracle.
Fresh synthetic500 PAPER ledger, frozen QW0 entry and canonical matcher:
bid0.4/0.4,5 shares each, activation after250ms; queue2x100=200. Synthetic
300-share DIRECT group =200 queue +5 allocated +95 unused. Booked cash498,
holdingA5/basis2 WITHOUT manual holding injection. Next synthetic print reuses
the known tx at WRONG coordinate: must halt ledger, cancel open orders, poison
reader and reject subsequent input, preserving already-booked cash/inventory.
These are fixture expectations, NOT market/account profits or actual bot fills.

## Next / limits

15,675 original observations remain unbound. Native642-identity consumption is
an adapter audit, NOT selected-snippet account replay. No market tape was fed
to a trading account. Full original-frame/timer native runner and exposure-aware
coverage proof still needed; stop at execution-relevant unknown coverage before
requesting bounded missing receipts. Any no-order fast path requires canonical
transition equivalence (including pending activation/cancel/reservation) and must
not count unknown venue volume as zero or fall back to public aggregate matching.

Then SAME-source/config/coverage baseline vs frozen QW0+exit full account, freeze
complete executable BEFORE independent multi-market PAPER. No holdout tuning or
acceptance/queue/fee/risk relaxation. Old control-$1.80 after costs and selected
conditional-$0.03747 vs+$0.11264 remain prior DEVELOPMENT evidence, not current
expanded-coverage account results. Full candidate account net UNKNOWN, NO_GO.
No independent qualification/live authority. PR9 stays draft/unmerged.

Complete local regression:304 tests in310.135s, OK; separate five new targeted
cases in1.432s, OK. Complete94-source Java17 native build and original/default
oracle pass; all frozen dependency hashes verified. New CI checks Java21 from
the same frozen source and retained inputs, not new market data/account PnL.
