#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
for service in strategy-service executor-service ingestor-service analytics-service infrastructure-orchestrator-service; do
  file="logs/$service.pid"; [[ -f "$file" ]] || continue
  pid=$(cat "$file"); [[ "$pid" =~ ^[0-9]+$ ]] || { echo "Invalid PID file: $file"; exit 1; }
  if kill -0 "$pid" 2>/dev/null; then
    [[ -r "/proc/$pid/cmdline" ]] || { echo "Cannot verify process $pid"; exit 1; }
    command_line=$(tr '\0' ' ' < "/proc/$pid/cmdline")
    [[ "$command_line" == *"$service-0.6.0.jar"* ]] || { echo "PID no longer belongs to $service"; exit 1; }
    kill -TERM "$pid"
    for ((attempt=0;attempt<15;attempt++)); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
    if kill -0 "$pid" 2>/dev/null; then echo "$service has not stopped; keeping its PID file"; exit 1; fi
  fi
  rm -f "$file"
done
echo "Services stopped. Durable account state retained."
