# QW0 — queue-aware pricing with a structural thin-depth reserve

Status: preregistered BEFORE implementation/evaluation; development research only.
One candidate, no grid search. No execution/service wiring or independent capture.

Evidence motivating this hypothesis: DQ3 maximizes combined bid but can choose a
large own-price queue. Its last sampled pair also loses resting-edge validity
when the top-depth thin premium rises from the observed level to its existing
maximum0.02. This motivates a queue objective plus a reserve computed from the
existing policy's analytical bound, NOT an after-the-fact lower risk threshold.

Frozen proposed rule:

- Start from exactly the same causal legacy witness input and all DQ3 admission
  guards: flat/no open orders, source/metadata freshness, market identity/status,
  available cash, portfolio budget, unchanged remaining unpaired loss budget.
- Quantity remains the ORIGINAL min(orderShares,10% smaller BEST bid depth),
  rounded DOWN to two decimals; never raise it to the market minimum. All19
  size-blocked original witnesses must remain blocked.
- Join only actual first3 displayed bid levels per leg, legal tick/post-only
  bounds, with displayed own-level size at least10x the requested quantity.
- Required edge = original causal requiredEdge + (0.02 - original thin premium),
  where original thin premium is min(ceil8(1/max(original best depth,1)),0.02).
  The extra reserve is nonnegative. Volatility/expiry/fees/merge cost remain as
  originally observed; do not substitute deeper depth to reduce any premium.
  This covers only the structural thin-premium bound, not future volatility.
- Among lawful pairs passing that stronger edge floor, minimize the maximum
  displayed own-level queue proxy(size*unchanged queueMultiplier), then minimize
  the sum of both queue proxies, then maximize combined bid, then minimize max
  selected level index, then index sum, then prefer higher first-token price.
  These are observation-only queue proxies, NOT fill probabilities or known
  future activation queues. No cancellation credit, trade-through assumption,
  future prints or achieved PnL may enter quote selection.

First evaluation gate: reproduce all old source/evidence tests; compare QW0,
DQ3 and actual legacy decisions on the SAME immutable34 development witnesses.
Require at least one additional lawful state vs actual legacy and at least one
different pair vs DQ3. If either is absent, reject without a tape scan/capture.
Even a pass authorizes only a separately frozen necessary traffic/causal lifetime
test; never account-performance claims from independent legacy snapshots.

No threshold tuning or alternate queue weights after seeing the screen. Do not
reuse holdout for development. Before independent PAPER, require a frozen
baseline/candidate FULL account comparison on same development inputs with exact
route evidence, current book-source eligibility, actual delayed activation,
resting cancellations and net costs. Acceptance.json remains immutable. No live
orders, funds, wallets or keys. Profits/fills must not be invented.
