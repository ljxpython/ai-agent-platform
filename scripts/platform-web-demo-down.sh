#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="/tmp/aitestlab-platform-web-demo"
PID_DIR="$LOG_DIR/pids"

bash "$ROOT_DIR/scripts/lightrag-service-down.sh"

kill_pid() {
  local pid="$1"

  if ! [[ "$pid" =~ ^[0-9]+$ ]]; then
    return
  fi

  if ! ps -p "$pid" >/dev/null 2>&1; then
    return
  fi

  kill -TERM -- "-$pid" >/dev/null 2>&1 || kill -TERM "$pid" >/dev/null 2>&1 || true
  sleep 1

  if ps -p "$pid" >/dev/null 2>&1; then
    kill -KILL -- "-$pid" >/dev/null 2>&1 || kill -KILL "$pid" >/dev/null 2>&1 || true
  fi
}

kill_pid_file() {
  local label="$1"
  local pid_file="$2"

  if [ ! -f "$pid_file" ]; then
    return
  fi

  local pid
  pid="$(tr -d '[:space:]' < "$pid_file")"
  if [ -n "$pid" ]; then
    echo "[stop] $label pid=$pid"
    kill_pid "$pid"
  fi
  rm -f "$pid_file"
}

kill_port() {
  local label="$1"
  local port="$2"
  local pids

  pids="$(lsof -ti "tcp:${port}" 2>/dev/null || true)"
  if [ -z "$pids" ]; then
    return
  fi

  echo "[stop] $label port=:$port"
  while IFS= read -r pid; do
    [ -n "$pid" ] || continue
    kill_pid "$pid"
  done <<< "$pids"
}

kill_pattern() {
  local label="$1"
  local pattern="$2"
  local pids

  pids="$(pgrep -f "$pattern" 2>/dev/null || true)"
  if [ -z "$pids" ]; then
    return
  fi

  echo "[stop] $label pattern=$pattern"
  while IFS= read -r pid; do
    [ -n "$pid" ] || continue
    kill_pid "$pid"
  done <<< "$pids"
}

kill_pid_file "runtime-service" "$PID_DIR/runtime-service.pid"
kill_pid_file "interaction-data-service" "$PID_DIR/interaction-data-service.pid"
kill_pid_file "platform-api" "$PID_DIR/platform-api.pid"
kill_pid_file "platform-api worker" "$PID_DIR/platform-api-worker.pid"
kill_pid_file "platform-web" "$PID_DIR/platform-web.pid"

kill_port "runtime-service" "8123"
kill_port "interaction-data-service" "8081"
kill_port "platform-api" "2142"
kill_port "platform-web" "3000"

kill_pattern "platform-api worker" "uv run python worker.py"
kill_pattern "platform-api worker" "apps/platform-api.*python worker.py"

echo "stopped platform-web demo processes (if running)"
