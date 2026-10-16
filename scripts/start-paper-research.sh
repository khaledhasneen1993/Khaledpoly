#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
export PAPER_RECORD_DIRECTORY="${PAPER_RECORD_DIRECTORY:-$PWD/research/data/paper}"
export PAPER_RECORD_REVISION="$(git rev-parse HEAD)"
if [[ -n "$(git status --porcelain)" ]]; then echo 'Commit the research configuration before recording a reproducible run.' >&2; exit 1; fi
command -v mvn >/dev/null || { echo 'Maven is required to bind this recording to a fresh verified build.' >&2; exit 1; }
mvn --batch-mode --no-transfer-progress verify
export EXECUTOR_SIM_FILLS_ENABLED=true
export HFT_MODE=PAPER
exec ./start-all-services.sh
