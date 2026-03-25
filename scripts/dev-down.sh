#!/usr/bin/env bash
set -euo pipefail

pkill -f "uvicorn main:app --host 0.0.0.0 --port 8090 --reload" || true
pkill -f "langgraph dev --config graph_src_v2/langgraph.json --port 8123" || true
pkill -f "uvicorn main:app --host 0.0.0.0 --port 2024 --reload" || true
pkill -f "next dev" || true

echo "stopped local dev processes (if running)"
