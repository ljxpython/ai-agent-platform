#!/usr/bin/env bash
set -e
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE="$1"

case "$SERVICE" in
  runtime-api)
    cd "$ROOT_DIR/apps/runtime-service"
    exec "$ROOT_DIR/apps/runtime-service/.venv/bin/graphharbor" serve --host 127.0.0.1 --port 8123 --config langgraph.json --n-jobs-per-worker 0
    ;;
  runtime-worker)
    cd "$ROOT_DIR/apps/runtime-service"
    exec "$ROOT_DIR/apps/runtime-service/.venv/bin/graphharbor" worker --config langgraph.json --n-jobs-per-worker 1
    ;;
  platform-api)
    cd "$ROOT_DIR/apps/platform-api"
    exec "$ROOT_DIR/apps/platform-api/.venv/bin/uvicorn" platform_api.main:create_app --factory --host 127.0.0.1 --port 2142 --workers 1 --env-file .env
    ;;
  *)
    echo "Unknown service: $SERVICE"
    exit 1
    ;;
esac
