#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_DIR="$ROOT_DIR/apps/lightrag-service"
STATE_DIR="/tmp/aitestlab-lightrag-service"
PID_DIR="$STATE_DIR/pids"
HTTP_HOST="${LIGHTRAG_HTTP_HOST:-127.0.0.1}"
HTTP_PORT="${LIGHTRAG_HTTP_PORT:-9621}"
MCP_HOST="${LIGHTRAG_MCP_HOST:-127.0.0.1}"
MCP_PORT="${LIGHTRAG_MCP_PORT:-8621}"

check_url() {
  local name="$1"
  local url="$2"
  local code
  code="$(python3 - "$url" <<'PY2'
import sys
import urllib.error
import urllib.request

url = sys.argv[1]
try:
    with urllib.request.urlopen(url, timeout=2) as response:
        print(response.getcode())
except urllib.error.HTTPError as exc:
    print(exc.code)
except Exception:
    print("000")
PY2
)"
  printf '%-24s %s -> %s\n' "$name" "$url" "${code:-ERR}"
}

show_pid_status() {
  local name="$1"
  local pid_file="$2"

  if [ ! -f "$pid_file" ]; then
    echo "$name pid -> missing"
    return
  fi

  local pid
  pid="$(tr -d '[:space:]' < "$pid_file")"
  if [ -n "$pid" ] && ps -p "$pid" >/dev/null 2>&1; then
    echo "$name pid -> $pid"
  else
    echo "$name pid -> stale (${pid:-empty})"
  fi
}

echo "== LightRAG service helper =="
echo "service_dir -> $SERVICE_DIR"
if [ ! -d "$SERVICE_DIR" ]; then
  echo "service_dir_status -> missing"
else
  echo "service_dir_status -> present"
fi

echo
echo "== pid files =="
show_pid_status "http" "$PID_DIR/http.pid"
show_pid_status "mcp-sse" "$PID_DIR/mcp-sse.pid"

echo
echo "== port listeners =="
if lsof -ti "tcp:${HTTP_PORT}" >/dev/null 2>&1; then
  echo "http -> listening on :$HTTP_PORT"
else
  echo "http -> not listening on :$HTTP_PORT"
fi
if lsof -ti "tcp:${MCP_PORT}" >/dev/null 2>&1; then
  echo "mcp-sse -> listening on :$MCP_PORT"
else
  echo "mcp-sse -> not listening on :$MCP_PORT"
fi

echo
echo "== http probes =="
check_url "http root" "http://${HTTP_HOST}:${HTTP_PORT}/"
check_url "http health" "http://${HTTP_HOST}:${HTTP_PORT}/health"
check_url "mcp sse" "http://${MCP_HOST}:${MCP_PORT}/sse"
check_url "mcp root" "http://${MCP_HOST}:${MCP_PORT}/"

echo
echo "== logs =="
echo "http log -> $STATE_DIR/http.log"
echo "mcp log -> $STATE_DIR/mcp-sse.log"
