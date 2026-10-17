# Independent Python PAPER research SDK, v0.6

The top-level **installable** \`khaledpoly-paper-research-extensions\`
package installs namespace packages for Phase-3 strict snapshot parsing,
Phase-4 recorder audit, Phase-5 event/CEX strategy research, and Phase-6
restricted PAPER proposal helpers.

Install from the project root (not from \`research/phase3\`):

    python3 -m venv .venv-paper
    .venv-paper/bin/pip install --no-deps .
    .venv-paper/bin/khaledpoly-paper-sdk --help

Declarative strategy producers can create a local JSON file with exactly
\`schema=1\`, \`version="1.0"\`, a kebab-case \`strategyId\`, and
\`proposals\`. Every proposal contains precisely \`id\`, \`edge\`, and
\`legs\` (condition, token, buy, price, size, expiresMs). The strict
library injects only the validated PAPER account/session/sequence/time
from the snapshot. All proposal fields are rechecked against the
**existing central PAPER risk allocator** and a future Java read-only
screen. No user strategy code is imported/executed in the bot process,
and there is no wallet or real exchange route in this SDK.

    .venv-paper/bin/khaledpoly-paper-sdk \
      --snapshot ./paper-snapshot.json \
      --spec ./strategy-hypotheses.json \
      --at-ms 1800000000000 \
      --output ./sdk-preview.json

The supplied clock is for recorded offline PAPER replay only. For live
PAPER snapshots, omit it so the local wall clock rejects stale data.

For multi-step PAPER experiments:
1. Generate hypotheses externally in an isolated process with **no**
   executor credentials.
2. Preview and inspect rejections via this SDK.
3. If explicitly and separately authorized to execute **virtual**
   PAPER orders, pass the original snapshot and envelope into
   \`research.phase6.virtual_paper_bridge\` with its separate flag.
   The Java ledger alone may reserve fictional account cash.
4. Archive immutable reports/receipts; do not infer real fill rates or
   market profitability from such runs.

**External arbitrary Python plugins are not loaded by the trading
runtime.** Declarative JSON is the supported untrusted-provider
interface. Polygon real transactions, funded trading, and LIVE remain
disabled in these Python tools. Acceptance of *research software*
does not imply a qualified model or venue strategy.
