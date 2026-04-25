#!/usr/bin/env bash
set -euo pipefail

check_url() {
  local name="$1"
  local url="$2"
  local code
  code="$(python3 - "$url" <<'PY'
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
PY
)"
  printf '%-28s %s -> %s\n' "$name" "$url" "${code:-ERR}"
}

echo "== http health =="
check_url "runtime-service" "http://127.0.0.1:8123/info"
check_url "interaction-data-service" "http://127.0.0.1:8081/_service/health"
check_url "lightrag http" "http://127.0.0.1:9621/health"
check_url "lightrag mcp sse" "http://127.0.0.1:8621/sse"
check_url "platform-api" "http://127.0.0.1:2142/_system/health"
check_url "platform-web" "http://127.0.0.1:3000"

echo
echo "== worker =="
if pgrep -f "apps/platform-api.*python worker.py" >/dev/null 2>&1 || pgrep -f "uv run python worker.py" >/dev/null 2>&1; then
  echo "platform-api worker -> running"
else
  echo "platform-api worker -> not running"
fi

echo
echo "== lightrag helper =="
bash "$(cd "$(dirname "$0")" && pwd)/lightrag-service-health.sh"
