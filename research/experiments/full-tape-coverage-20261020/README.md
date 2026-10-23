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

LATEST: corrected run39342821835 completed SUCCESS. Exact complete artifact,
independent reconstruction of ALL16,317 trade identities,15,866 missing
observations and191 reviewed-cache receipt candidates are retained in
[result/README.md](result/README.md).293 local tests pass. No further full-source
scan or new receipt request in this result verification. Historical preparation
and failure notes below are preserved for provenance, not current run status.

FOLLOW-UP: all191 reviewed cached candidates are now rebound to conserved
source groups:642 bindings /1,516 components in the explicitly PARTIAL
[cached receipt pool](../cached-receipt-pool-20261020/README.md).299 local tests
pass. Original census/artifact/counts remain immutable; native consumer and
full-account baseline/candidate comparison are still pending. No new RPC/PnL.

### First census stopped safely; standalone timer correction

Run39336641679 failed AFTER285 tests passed in322.708s and the complete original
artifact download digest matched. It produced only a201-byte partial artifact,
not coverage.json. The census whitelist omitted RESEARCH_TICK. This is a known
canonical scheduler input (ResearchSession.accept), not a new trade route.
Original independent capture-inspection.json already counts28,743 such rows;
its event counts total exactly6,163,831 journal rows and16,317 normalized trades.
The retained original recovery context contains109 TICKs, first at original
sequence258642 /1792269759067, payload{}. Regression uses that actual row.

Correction counts standalone TICK without adding observation liquidity and
keeps TICK forbidden INSIDE a frame, like the canonical engine. Unknown research
input still fails, now with kind + original sequence in the exception. Added
post-scan equality checks against the pinned pre-existing independent inspector:
ALL journal kind counts, all four normalized market-event counts, total rows,
trade count and scheduler count. No tape/labels/QW0/exit/account config changes.
Revised census-only freeze pins corrected parser/tests and existing inspection;
this is NOT strategy selection, acceptance relaxation or a holdout retune.

Ten targeted tests pass, including real timer, no timer volume/market fills,
forbidden framed timer, unknown-kind coordinates and inspector-count tampering.
Re-run ONLY this failed census workflow with the corrected source; do not repeat
any strategy experiment or launch overlapping capture.

Corrected-parser complete local regression:288 tests in275.584s, OK; separate
final10 targeted cases (including original inspector vocabulary) in0.006s, OK.
Frozen corrected source/test/inspector dependency hashes verified. Original
acceptance/account config remain unchanged. Full census totals remain PENDING.

Initial implementation local offline regression:285 tests in280.195s, OK; separate new targeted
seven tests in0.006s, OK. Frozen dependency hashes, downloaded prior GitHub proof
and unchanged acceptance/config verified. Full source scan runs once on GitHub;
no coverage totals are asserted before its output exists.

The completed census hashes/counts/full-identity digest are verified; do not
launch another source scan. Rebind retained receipt candidates and inspect
execution-relevant missing routes before requesting new bounded evidence.
Build a fail-closed multi-market full-tape route/runner
contract; only then compare baseline and frozen candidate on exactly the same
complete source/config/coverage and freeze before independent PAPER.

No new market-account net: original control -$1.80 after costs; old selected
conditional exit -$0.03747 versus +$0.11264 only. QW0 full-account market result
UNKNOWN. NO_GO; no acceptance edits, holdout retuning or live access.
