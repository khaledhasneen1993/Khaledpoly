# PAPER order lifecycle correction

The original two-hour run (39048983750, revision 7848cfcf8ddf3a321fe1b290efcf99cb270363a3) submitted 44 orders and filled none. A read-only journal audit found 38 CANCELED and six REJECTED terminals, lifetimes 251–753 ms (median 502), and no terminal input containing a GAP. Six activation-time books were consistent with post-only crossing rejection. Gaps were a separate data-quality problem; they were not proven as the direct cause of those 44 terminals.

## Corrected behavior

- Existing pairs are reviewed before constructing a new-entry quote. Their own limit prices and remaining matched quantity determine economics. A replacement's minimum-size failure no longer cancels an already reserved valid pair. Existing partial remainders are not subjected to a new-order minimum.
- The full dynamic risk premium and settlement cost still apply. No net-edge floor was lowered. Invalid/stale books, invalid prices/ticks and risk stops still cancel immediately with the configured cancellation latency. Quote repricing requires a valid replacement, improved competitiveness and the existing two-second interval; the interval does not override risk cancellation.
- A rejected leg immediately requests cancellation of open buy peers in that market. The matching engine still honors activation/cancel latency, print-only fills, queue and partial fills. Cancellation is not treated as instantaneous; a peer can fill during the race.
- Every terminal carries its actual matcher reason (including POST_ONLY_WOULD_CROSS and ACTIVATION_BOOK_UNAVAILABLE). Strategy CANCEL_REQUEST records include the first request's reason and timestamp. Duplicate requests do not reset the deadline or overwrite the first reason. Metrics count terminal statuses/reasons independently of AccountLedger's generic canceled reservation state.
- A known token gap is expanded to its binary market pair, cancels both entry legs, and removes that market's books/pending takers. Unrelated market state is preserved. Unknown scope, socket loss and decoder-wide corruption still invalidate globally. Native full snapshots restore invalid depth; existing reconnect fallback remains available when resnapshot cannot complete.
- Streaming and raw replay both derive affected token IDs from nested price_changes. A strictly older late message is discarded when a newer source timestamp is already accepted; it does not refresh the book clock. An advancing stale event still invalidates its affected scope. No timestamp is rebased and the two-second source-age cap remains.

## Recording transport

`paper.record.compress=true` writes lossless `events.jsonl.gz` with synchronous gzip flush before group fsync and a final verified trailer. The compatibility default is false; the minimal profile enables compression. Journal writtenBytes remains logical uncompressed bytes; storedBytes exposes persisted compressed bytes. This reduces disk footprint without dropping source messages, normalized frames or audit records. It does not claim to reduce logical message volume or remove upstream latency.

Java replay and Python ingestor inspection, labels, capture-window gates and replay smoke accept plain and gzip tapes. Plain legacy recordings remain readable. New compressed public captures must pass raw/normalized action parity. Raw replay of the old run deliberately uses the corrected decoder; it is a counterfactual, not an assertion that old normalized decoder output is identical after policy changes.

## Verification

The branch workflow runs the complete Java and Python suites, SDK installation, a short compressed public PAPER capture, raw/normalized action parity and stress replay. Regression cases cover valid orders surviving bad replacement quotes, entry-size separation, immediate safety cancellation, peer rejection races, market-scoped/global gaps, source-order freshness and gzip round trips.

The workflow also replays the original two-hour tape OFFLINE through the updated raw decoder/strategy. Original logical tape bytes are hashed while losslessly recompressing for storage; the original run/artifact digest is retained. The report compares observed original PAPER metrics with an updated counterfactual. This cannot prove actual venue fills or out-of-sample performance. Do not relax the queue model or force fills to obtain a favorable result. All acceptance remains NO_GO.
