#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
[[ -z "$(git status --porcelain)" ]] || { echo 'Commit source/configuration before collecting an auditable dataset.' >&2; exit 1; }
command -v timeout >/dev/null || { echo 'The timeout utility is required.' >&2; exit 1; }
mvn --batch-mode --no-transfer-progress verify
revision="$(git rev-parse HEAD)"
status=0
timeout --signal=TERM --kill-after=20 "${PAPER_RECORD_SECONDS:-3600}" java -jar executor-service/target/executor-service-0.6.0.jar \
 --server.port="${PAPER_RECORD_PORT:-18080}" --spring.application.name=paper-ingestor --hft.mode=PAPER --hft.events.enabled=false \
 --executor.sim.enabled=false --hft.strategy.gabagool.enabled=false --hft.polymarket.market-ws-enabled=true \
 --paper.market-data.enabled=true --paper.universe.five-minute="${PAPER_FIVE_MINUTE:-false}" \
 --paper.record.directory="${PAPER_RECORD_DIRECTORY:-$PWD/research/data/paper}" --paper.record.revision="$revision" || status=$?
[[ "$status" == 0 || "$status" == 124 ]] || exit "$status"
