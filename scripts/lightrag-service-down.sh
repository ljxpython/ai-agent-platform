#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="/tmp/aitestlab-lightrag-service"
PID_DIR="$STATE_DIR/pids"
HTTP_PORT="${LIGHTRAG_HTTP_PORT:-9621}"
MCP_PORT="${LIGHTRAG_MCP_PORT:-8621}"

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

kill_pid_file "lightrag http" "$PID_DIR/http.pid"
kill_pid_file "lightrag mcp sse" "$PID_DIR/mcp-sse.pid"

kill_port "lightrag http" "$HTTP_PORT"
kill_port "lightrag mcp sse" "$MCP_PORT"

echo "stopped optional lightrag-service processes (if running)"
