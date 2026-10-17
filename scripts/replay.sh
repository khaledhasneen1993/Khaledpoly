#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec java -Dloader.main=com.polybot.hft.executor.replay.ReplayMain -cp executor-service/target/executor-service-0.6.0.jar org.springframework.boot.loader.launch.PropertiesLauncher "$@"
