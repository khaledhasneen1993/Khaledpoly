#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -z "$(git status --porcelain)" ]] || { echo 'Commit the frozen source before a reproducible replay.' >&2; exit 1; }
mvn --batch-mode --no-transfer-progress verify
revision="$(git rev-parse HEAD)"
exec java -Dpaper.replay.revision="$revision" -Dloader.main=com.polybot.hft.executor.replay.ClosedLoopMain -cp executor-service/target/executor-service-0.0.1-SNAPSHOT.jar org.springframework.boot.loader.launch.PropertiesLauncher "$@"
