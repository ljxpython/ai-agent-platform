#!/usr/bin/env bash
set -euo pipefail

pkill -f "langgraph dev --config runtime_service/langgraph.json --port 8123" || true
pkill -f "uvicorn main:app --host 127.0.0.1 --port 8081 --reload" || true
pkill -f "uvicorn main:app --host 0.0.0.0 --port 2024 --reload" || true
pkill -f "uvicorn main:app --host 127.0.0.1 --port 2142 --reload" || true
pkill -f "apps/platform-api-v2.*python worker.py" || true
pkill -f "uv run python worker.py" || true
pkill -f "vite --host 127.0.0.1 --port 3000" || true
pkill -f "pnpm dev -- --host 127.0.0.1 --port 3000" || true

echo "stopped platform-web-vue demo processes (if running)"
