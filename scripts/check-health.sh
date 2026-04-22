#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

exec bash "$ROOT_DIR/scripts/platform-web-demo-health.sh"
