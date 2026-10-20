# Complete original identity index — proof only

Reproduce offline from retained, hash-checked evidence:

```sh
python3 -m research.phase6.complete_source_index --output /tmp/complete-source-index-proof.json
python3 -m unittest research.phase6.tests.test_complete_source_index -v
```

The exact canonical identity stream is reconstructed in memory from all451 old
bound observations and all15,866 original missing observations. Its SHA256 equals
the prior full original scan. Historical coverage values are preserved; they do
not promote observations to settlement labels. Global transaction and public-ID
uniqueness is checked jointly across ALL16,317 observations, not just the missing
subset. No receipt request, source recapture, full tape rescan or execution.

The strict Python reference consumer checks original coordinate, receive/source
time, token, side, decimal price/quantity, SHA256 of exact tradeId UTF8 bytes and
its transaction hash. Duplicate, reverse, missing or changed input poisons the
consumer. It owns validated copies. Full mode permits no omitted observations;
the explicitly separate subset test mode cannot certify completion.

All643 available retained original raw preimages match. The other15,674 raw
preimages are NOT invented or claimed consumed. Their canonical identity facts
are source-bound through the exact full-census digest, not a new replay.

This is NOT a Java native consumer, atomic session guard, no-order witness or
runtime integration. Those remain required before any shortcut. No labels are
returned, no unknown volume is turned into zero, no matching/queue/fee/risk or
acceptance settings change. Actual baseline/candidate still stop at628; full
account net remains UNKNOWN and independent acceptance remains NO_GO.
