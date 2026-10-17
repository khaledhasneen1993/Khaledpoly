# Contributing to Khaledpoly v0.6.0

**One maintained build** lives in `.github/workflows/verify.yml`; the
canonical branch is `main`. All supported new code must preserve
PAPER-only mode, deterministic provenance, the durable Java cash ledger,
strict no-LIVE gating, and backward-compatible account/session IDs.

## Development

Requires Java 21, Maven and Python 3.10+:

```bash
mvn --batch-mode --no-transfer-progress verify
python3 -m unittest discover -s research/phase2/tests -v
python3 -m unittest discover -s research/phase3/tests -v
python3 -m unittest discover -s research/phase4/tests -v
python3 -m unittest discover -s research/phase5/tests -v
python3 -m unittest discover -s research/phase6/tests -v
python3 -m pip install --no-deps .
```

Do not submit repeated stage-specific build workflows or duplicate
package version declarations. Java Maven and the Python release metadata
both use `0.6.0`. When a later version is approved, change Java
parent/dependents, Python metadata and all fixed jar paths *together*.

For changes to strategies or trade evidence, include source provenance,
timestamps, fees/slippage assumptions, explicit abstention reasons and
independent held-out experiments. Simulated fills, touched book prices
and synthetic PnL are never real fills or verified profits.

Never commit wallets, signing keys, tokens, secret environment files,
PII or private datasets. Prefer tested local PAPER scenarios and
read-only public-market diagnostics. Preserve `NO_GO` until external
data acceptance and independent security approval.

Review the [current project status](README.md), [engineering acceptance
gate](docs/SOFTWARE_RELEASE_GATE.md) and [phase-six contracts](docs/PHASE6.md).
