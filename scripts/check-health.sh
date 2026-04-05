#!/usr/bin/env bash
set -euo pipefail

echo "== interaction-data-service =="
curl -sS -o /dev/null -w 'http://127.0.0.1:8090/_service/health -> %{http_code}\n' http://127.0.0.1:8090/_service/health || true

echo "== platform-api =="
curl -sS -o /dev/null -w 'http://127.0.0.1:2024/_proxy/health -> %{http_code}\n' http://127.0.0.1:2024/_proxy/health || true

echo "== runtime-service =="
curl -sS -o /dev/null -w 'http://127.0.0.1:8123/info -> %{http_code}\n' http://127.0.0.1:8123/info || true

echo "== platform-web-vue =="
curl -sS -o /dev/null -w 'http://127.0.0.1:3000 -> %{http_code}\n' http://127.0.0.1:3000 || true

echo "== runtime-web =="
curl -sS -o /dev/null -w 'http://127.0.0.1:3001 -> %{http_code}\n' http://127.0.0.1:3001 || true
