#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "$0")"
command -v java >/dev/null || { echo "Java 21 is required"; exit 1; }
command -v curl >/dev/null || { echo "curl is required"; exit 1; }
mkdir -p logs state
light="${POLYBOT_LIGHT:-true}"
services=(executor-service strategy-service)
if [[ "$light" != true ]]; then
  command -v docker >/dev/null || { echo "Docker Compose is required for full mode"; exit 1; }
  docker compose -f compose.yaml config --quiet
  docker compose -f compose.yaml up -d --wait
  services+=(ingestor-service analytics-service)
fi
for service in "${services[@]}"; do
  pidfile="logs/$service.pid"
  if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    echo "$service is already running; refusing duplicate start"; exit 1
  fi
done
build_required=false
for service in "${services[@]}"; do [[ -f "$service/target/$service-0.0.1-SNAPSHOT.jar" ]] || build_required=true; done
if [[ "$build_required" == true ]]; then
  command -v mvn >/dev/null || { echo "Build first with Maven: mvn verify"; exit 1; }
  mvn --batch-mode --no-transfer-progress verify
fi
started=()
cleanup_failure() {
  for pid in "${started[@]}"; do kill -TERM "$pid" 2>/dev/null || true; done
}
trap cleanup_failure ERR
for service in "${services[@]}"; do
  extra=()
  [[ "$light" == true ]] && extra+=(--hft.events.enabled=false)
  java -Dpolybot.orderState="$PWD/state/strategy-orders.json" -jar "$service/target/$service-0.0.1-SNAPSHOT.jar"     --spring.profiles.active=develop "${extra[@]}" > "logs/$service.log" 2>&1 &
  pid=$!; started+=("$pid"); printf '%s\n' "$pid" > "logs/$service.pid"
  case "$service" in executor-service) port=8080;; strategy-service) port=8081;; ingestor-service) port=8083;; analytics-service) port=8082;; esac
  ready=false
  for ((attempt=0;attempt<30;attempt++)); do
    kill -0 "$pid" 2>/dev/null || { echo "$service exited; see logs/$service.log"; exit 1; }
    if curl --fail --silent --max-time 2 "http://127.0.0.1:$port/actuator/health" >/dev/null; then ready=true; break; fi
    sleep 1
  done
  [[ "$ready" == true ]] || { echo "$service readiness timed out"; cleanup_failure; exit 1; }
done
trap - ERR
echo "PAPER services ready. Conservative print-based fills require EXECUTOR_SIM_FILLS_ENABLED=true. Dashboard: http://127.0.0.1:8080/paper.html. Research results require heldout validation."
