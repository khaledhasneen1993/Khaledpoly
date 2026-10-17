#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export EXECUTOR_ACCOUNT_STATE_PATH="${EXECUTOR_ACCOUNT_STATE_PATH:-$PWD/state/phase3-paper/account.json}"
export PAPER_RECORD_DIRECTORY="${PAPER_RECORD_DIRECTORY:-$PWD/research/data/phase3-paper}"
export PAPER_PHASE3_EXECUTION_ENABLED=true
exec ./scripts/start-phase3-research.sh
