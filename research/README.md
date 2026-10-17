# Khaledpoly research v0.6.0 (PAPER only)

This directory contains the actively maintained, causal **PAPER-only**
Polymarket/CEX data collection and research system. Do not interpret
simulated matching or public trade prints as genuine venue fills.

- `research/phase2`: PAPER matching, recorded market replay and fixtures.
- `research/phase3`: strict snapshots, accounts, SDK, public integration smoke,
  virtual execution and source-provenance/second-leg labels.
- `research/phase4`: public-source recorder, audit, supervised capture and
  strict gap/full-UTC-day evidence validation.
- `research/phase5`: CEX signals, future-print labels, event scenarios,
  purged walk-forward tests and joint-risk portfolio optimization.
- `research/phase6`: external strategy SDK, cross-account risk, Java PAPER
  bridge, source-evidence gate, software release manifest and tests.

Run from the **repository root**:

```bash
python3 -m unittest discover -s research/phase2/tests -v
python3 -m unittest discover -s research/phase3/tests -v
python3 -m unittest discover -s research/phase4/tests -v
python3 -m unittest discover -s research/phase5/tests -v
python3 -m unittest discover -s research/phase6/tests -v
python3 -m research.phase6.sdk --help
python3 -m research.phase4.final_gate --help
```

Optional legacy ClickHouse/notebook analytics, snapshot reports, and
replication scoring are **not** separate active deployments or build
pipelines. Keep source-specific raw tapes and hashes; `research/output/`
and private datasets are intentionally Git-ignored.

Read [the canonical project overview](../README.md) and
[the external seven-day capture procedure](../docs/CAPTURE_SUPERVISOR.md).
Source/venue/fill/settlement acceptance remains **NO_GO** until validated;
the seven-day prospective experiment is not yet performed.
