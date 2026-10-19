# Full original tape coverage census (DEVELOPMENT, PAPER only)

This is a coverage dependency, NOT a strategy experiment, account comparison,
holdout, new public capture, or a source of simulated fills / PnL.

Preflight: branch cff52ff / draft PR9 unchanged, latest run39330038356 completed
SUCCESS, no overlapping run. Downloaded prior integrated-profile artifact
12223933817 (14,623 bytes), ZIP SHA256
`a93fed68383898170d9faf05a40575e018880b5f14a5e698979f0780766628d0`.
Reverified its42 full quote proposals,18 exit decisions, complete default-off
parity and canonical synthetic execution guards with frozen_policy_result.
GitHub logs confirm278 tests in350.063s, both native build and execution steps
successful. That proof is synthetic, not new market performance.

## Frozen census

Source run39067539123, fresh-paper-compressed-tape artifact12117311261:
6,163,831 original journal rows. Both compressed and logical SHA256 pinned in
research/phase6/full-tape-coverage-freeze.json. No slicing/selected snippets.

Revalidate existing451 receipt bindings /1,038 components OFFLINE, then scan the
complete original journal once. Check every row's schema, sequence, run and
arrival clock, including all tail rows; match every RAW/frame boundary; reject
unknown/unframed research inputs, incomplete terminal, missing bound coordinate,
changed price/size/side/time/token/hash and ambiguous market identity.

Each normalized TRADE gets exactly one coverage class:

- Existing coordinate-bound conserved group.
- Same known transaction aggregate suppressed (no additional volume).
- Missing scoped pair label.
- Other-market unbound (NOT public aggregate fallback).
- Unknown market unbound.

Report per-condition counts and earliest missing observation per reason.
Persist EVERY missing identity to deterministic gzip JSONL, preserving original
sequence/eventIndex/arrival/source/token/side/price/size/public-identity hash and
transaction hash if present. Hash full observation census and full missing
stream. Bounded memory/256MiB missing-output ceiling FAILS rather than truncates;
no list of millions of full depth frames in memory. Failed output retains only
.partial evidence and no successful coverage.json. Count observations, not
unique transactions: never infer independent liquidity from duplicate prints.

Even zero missing observations does NOT authorize full account replay or
independent qualification: the present mixed adapter is still explicitly
single-pair/partial and needs a full-source routing contract. Unknown coverage
is not converted to zero. Existing source matcher, queues, fees, risk, acceptance
and frozen QW0/exit rules unchanged. No RPC or order submission.

## Next

Local complete offline regression:285 tests in280.195s, OK; separate new targeted
seven tests in0.006s, OK. Frozen dependency hashes, downloaded prior GitHub proof
and unchanged acceptance/config verified. Full source scan runs once on GitHub;
no coverage totals are asserted before its output exists.

Wait for this census instead of launching another source scan. Revalidate its
original hashes, count conservation and missing-stream digest. Inspect missing
routes / earliest blocker and reuse retained receipts before requesting any
new bounded evidence. Build a fail-closed multi-market full-tape route/runner
contract; only then compare baseline and frozen candidate on exactly the same
complete source/config/coverage and freeze before independent PAPER.

No new market-account net: original control -$1.80 after costs; old selected
conditional exit -$0.03747 versus +$0.11264 only. QW0 full-account market result
UNKNOWN. NO_GO; no acceptance edits, holdout retuning or live access.
