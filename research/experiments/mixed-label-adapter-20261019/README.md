# Conserved mixed-side adapter: implementation dependency, not account profitability

2026-10-19. Parent branch/PR9 source `498542892bb7290b1eaee125bb3a40deea7a0d82`.
Prior independent-exit proof run39305626305 completed SUCCESS: 261 tests and
byte-identical retained verification/comparison. No active experiment overlapped.

Implemented a **separate research-only adapter**, leaving legacy
`SettlementReplayLabels`, matcher, session, production/default policies and all
frozen candidate sources unchanged. It emits the existing canonical
`SettlementReplayLabels.Binding`/`Portion` records; it does not create orders,
inject inventory or replace `ResearchSession` yet.

The exporter revalidates ALL451 retained receipts/block identities and original
source frames. It exports raw matched orders, not trusted pre-priced components.
The Java adapter independently checks both public sides, DIRECT/MINT/MERGE
routes, exact integer shares AND collateral, allowed exchanges, binary tokens,
group/transaction/coordinate/component uniqueness, uint256 bounds, exact source
hash/clock/price/size, and full binding consumption. It rounds maker BUY prices
UP and SELL prices DOWN to28 places. This rounding never makes a cent-price
threshold easier to cross. The old <=100 BUY-only adapter is not relaxed.

Unknown scoped observations fail closed, even outside this partial coverage
window if fed to this adapter. A repeated covered transaction's alternate public
aggregate yields an empty binding, never additional volume. Reconsuming an exact
original binding is an error. Unrelated unlabelled markets return null; this
validation does not simulate them or claim full-account coverage.

| Route | Actual maker components |
| --- | ---: |
| DIRECT | 208 |
| MINT | 821 |
| MERGE (complementary SELL/burn route) | 9 |
| Total | 1,038 |

The native adapter consumed all451 original coordinates. Independent Python
recomputed a digest of EVERY original coordinate, identity, token, side, exact
quantity and conservatively rounded price. Both languages matched:
`402d6f602110befe0b62fd06e34ee93e34e8e960c3c4f88bd5e3b1bf5969e849`.
Native output and independent verification are retained here. The exact
1,556,983-byte label input is reproducible using `mixed_replay_labels`; its hash
is retained in provenance/native report, avoiding another duplicate large file.

Local Java17 compiler successfully compiled ALL94 unchanged core sources plus
both new adapter classes against libraries from the verified retained executor
artifact. No wallets/keys/network operations were invoked. Native self-tests pass:
four canonical matcher queue bridges (both DIRECT sides, MINT and MERGE),
22 rejection cases, and two BUY-UP/SELL-DOWN sub-28-digit boundary cases. These
are explicitly SYNTHETIC fixtures, never counted as market fills. Four new Python
tests validate actual export/parity, reject altered component hashes/subsets and
scope escalation, and pin the old adapter's exact SHA.

Reproduction (Java21 with existing engine libraries):

```sh
python3 -m research.phase6.mixed_replay_labels --output labels.json
javac -proc:none -cp 'engine/BOOT-INF/lib/*' -d classes research/phase6/ConservedMixedReplayLabels.java research/phase6/ConservedMixedReplayLabelsProbe.java
java -cp 'classes:engine/BOOT-INF/lib/*' com.polybot.hft.paper.ConservedMixedReplayLabelsProbe --self-test
java -cp 'classes:engine/BOOT-INF/lib/*' com.polybot.hft.paper.ConservedMixedReplayLabelsProbe labels.json research/experiments/queue-aware-quote-20261019/post-gap-result/context.records.jsonl.gz report.json
python3 -m research.phase6.mixed_replay_labels_proof report.json
```

The new CI workflow repeats this adapter validation only, after all regressions,
against the retained canonical Java21 engine. No new receipts, full original tape
scan, capture, native strategy experiment or live trading. Local native output
ordering may differ across JVMs; compare parsed fields/digests, not JSON key order.

## Next work

1. Introduce an explicit research-only label-resolver integration point while
   retaining legacy/default behavior and reproducible frozen baseline binaries.
   The adapter cannot be passed to the current concrete-type session constructor.
2. Wire frozen QW0 entry + fee-positive exit into a default-OFF research profile;
   keep canonical account ledger/cash, all cancellations, risk and execution-net
   recheck. No manually injected holding, no aggregate-plus-component double use.
3. Establish exact coverage for the whole replay, not merely this451-observation
   recovery window. Start SAME-source baseline/candidate account comparison only
   after transition parity and coverage checks; missing coverage is not zero.
4. Freeze integrated code/config before independent multi-market PAPER. Preserve
   acceptance unchanged and never tune on that evaluation.

No new financial result: selected conditional exit remains +$0.11264 versus
-$0.03747; known separate full-account control remains -$1.80 after costs. Full
QW0 account UNKNOWN; NO_GO, no independent acceptance or live permission.
