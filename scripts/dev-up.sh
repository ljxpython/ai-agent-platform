#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "[1/5] starting runtime-service on :8123"
(
  cd "$ROOT_DIR/apps/runtime-service"
  nohup uv run langgraph dev --config runtime_service/langgraph.json --port 8123 --no-browser > /tmp/agent-platform-runtime-service.log 2>&1 &
)

echo "[2/5] starting interaction-data-service on :8090"
(
  cd "$ROOT_DIR/apps/interaction-data-service"
  nohup uv run uvicorn main:app --host 0.0.0.0 --port 8090 --reload > /tmp/agent-platform-interaction-data-service.log 2>&1 &
)

echo "[3/5] starting platform-api on :2024"
(
  cd "$ROOT_DIR/apps/platform-api"
  nohup uv run uvicorn main:app --host 0.0.0.0 --port 2024 --reload > /tmp/agent-platform-platform-api.log 2>&1 &
)

echo "[4/5] starting platform-web-vue on :3000"
(
  cd "$ROOT_DIR/apps/platform-web-vue"
  nohup env VITE_DEV_PORT=3000 pnpm dev > /tmp/agent-platform-platform-web-vue.log 2>&1 &
)

echo "[5/5] starting runtime-web on :3001"
(
  cd "$ROOT_DIR/apps/runtime-web"
  nohup env PORT=3001 pnpm dev > /tmp/agent-platform-runtime-web.log 2>&1 &
)

echo "done. logs:"
echo "  /tmp/agent-platform-interaction-data-service.log"
echo "  /tmp/agent-platform-runtime-service.log"
echo "  /tmp/agent-platform-platform-api.log"
echo "  /tmp/agent-platform-platform-web-vue.log"
echo "  /tmp/agent-platform-runtime-web.log"
