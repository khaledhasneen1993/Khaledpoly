#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || { echo 'Commit source before starting an auditable PAPER runtime.' >&2; exit 1; }
revision="$(git rev-parse HEAD)"
build_stamp=executor-service/target/minimal-build-revision.txt
if [[ ! -f executor-service/target/executor-service-0.6.0.jar || ! -f "$build_stamp" || "$(cat "$build_stamp")" != "$revision" ]]; then
  mvn --batch-mode --no-transfer-progress verify
  printf '%s\n' "$revision" > "$build_stamp"
fi
exec python3 -m research.phase6.minimal_runtime --root "$PWD" \
  --state "${PAPER_MINIMAL_STATE:-$PWD/state/minimal}" \
  --port "${PAPER_MINIMAL_PORT:-8080}" --max-restarts "${PAPER_MAX_RESTARTS:-0}"
