# Khaledpoly v0.6.0 — single PAPER software acceptance gate

The *engineering* gate checks the files listed in
`research.phase6.software_gate.REQUIRED` and their SHA-256 hashes.
The CI workflow runs the gate **after** its Maven Java, Python
unit/integration, installed SDK, offline replay, and required CLI
tests pass. A software **review candidate** means that the configured
workflow reached its last validation step on a specific Git revision;
it does not imply that static file presence independently verifies
security, performance, or production readiness.

The one CI workflow uploads a short-lived artifact bundle named
`khaledpoly-paper-0.6.0-evidence`, containing both the software manifest
`research/output/phase6-software-check.json` and the independent public
PAPER artifact reconciliation result. Each report records
the exact revision/hash inventory and explicit **NO_GO** status.
Run locally with:

    mkdir -p research/output
    python3 -m research.phase6.software_gate \
      --root . --output research/output/phase6-software-check.json

Outside verified CI, `softwareReviewCandidate=false` even with
all files present. The gate is intentionally one-way: no
`liveAllowed=true` path, no automated main merge and no funded or
on-chain execution.

## External acceptance still required

- A real stable host and seven consecutive **complete UTC days** of
  independently validated Polymarket order-book/market plus
  Binance/Bybit market source data, with audited silent outages.
- Real order queue/fill/second-leg and fee/cost labels from venue
  evidence rather than touched-price PAPER assumptions.
- Terminal settlement and oracle disputes/challenges, negative-risk
  and multi-outcome group membership, exchange market downtime.
- Freeze strategy parameters and test on later independent held-out
  markets; PnL net of measured costs must pass separately.
- End-to-end actual environment/restart/security/performance review.

These are deliberately deferred by the user's requested engineering
order, **not** approved, simulated, or replaced by the software
manifest. There is no claim that any strategy is profitable.
