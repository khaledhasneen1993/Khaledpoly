#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
research_api_token="${POLYBOT_EXECUTOR_TOKEN:-}"
if [[ ${#research_api_token} -lt 24 || -z "${research_api_token//[[:space:]]/}" ]]; then
  echo 'POLYBOT_EXECUTOR_TOKEN must contain at least 24 characters.' >&2
  exit 1
fi
export PAPER_PHASE3_ENABLED=true
exec ./scripts/start-paper-research.sh
