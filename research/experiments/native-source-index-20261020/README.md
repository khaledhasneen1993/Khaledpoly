# Native complete source identity reader — proof only

`CompleteSourceIdentityIndex` is a standalone research Java reader, not a label
adapter, engine plugin or runtime skip. It requires the COMPLETE8,364,298-byte
original canonical census with exact SHA256
`1f8d1d953f3755b8244c7ac11f7a3f72ccd8d73b1c9807b7cec417b6b710c1c2`.
No configurable source hash, partial index, generated IDs or receipt fallback.
The old451 historical coverage values remain unchanged.

Before use it validates bounded UTF8 input, all16,317 row schemas/order/clocks,
prices/quantities, global transaction/public-ID uniqueness and source bounds.
Immutable records/maps are owned by the reader. Consumption is synchronized,
checks exact coordinates/time/token/side/decimal values/original raw UTF8 hash
and parsed transaction; failures and incomplete finalization poison the reader.

Default full-sequence mode accepts original97 but rejects jumping from97 to the
next available retained receipt preimage: original628 must not be omitted.
The probe does NOT claim that628 was replayed or rejected as an invalid identity.
Explicit diagnostic subset mode matches all643 available exact original raw
preimages, then must reject completion. Other15,674 preimages are not invented,
read or certified consumed. There is no complete market/account replay result.

23 negative guards:21 input/finalization rejection cases plus failed-reader
continuation and changed full-census bytes. Changed constructor input is rejected
before a reader exists; all consumption/finalization failures poison the reader.
Inputs are independently reconstructed by `native_source_index.py`; its verifier
rejects source/count/guard/scope promotion. Tests include future no-order proof
counterexamples; there is no core/session/pool/policy modification.

```sh
python3 -m research.phase6.native_source_index --prepare /tmp/new-native-index-inputs
# Compile the two Java files against the pinned Jackson dependency, then run
# CompleteSourceIdentityProbe with complete-index.jsonl, source-identities.json,
# and a NEW output directory. See .github/workflows/native-source-index.yml.
python3 -m research.phase6.native_source_index --verify research/experiments/native-source-index-20261020/native-index-proof.json
```

Next required: explicit no-order witness, atomic synchronized session health /
empty exposure guard including persistence failure, per-trade identity checks
before any expiry/filter skip, and honest separate unknown venue-volume counters.
No empty/null labels, aggregate fallback or artificial zero-volume assumption.
Only after frozen differential/guard tests should SAME original source advance
to first execution-relevant unknown. Current actual execution still stops628.
PAPER/NO_GO; no new PnL or independent acceptance; fees/queue/risk unchanged.
