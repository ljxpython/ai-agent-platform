#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ "${LOCAL_STACK_LOCKED_ROOT:-}" != "$ROOT_DIR" ] && [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-help}" != help ] && [ "${1:-}" != --help ] && [ "${1:-}" != -h ]; then
  exec python3 "$ROOT_DIR/scripts/local_stack_worktree.py" run "$ROOT_DIR" "$@"
fi
RUNTIME_DIR="$ROOT_DIR/apps/runtime-service"
PLATFORM_API_DIR="$ROOT_DIR/apps/platform-api"
PLATFORM_WEB_DIR="$ROOT_DIR/apps/platform-web"
STATE_DIR="$ROOT_DIR/.local-stack"
PID_DIR="$STATE_DIR/pids"
LOG_DIR="$STATE_DIR/logs"
RUNTIME_ENV_FILE="${RUNTIME_ENV_FILE:-$RUNTIME_DIR/.env}"
PLATFORM_ENV_FILE="${PLATFORM_ENV_FILE:-$PLATFORM_API_DIR/.env}"
RUNTIME_PORT="${RUNTIME_PORT:-}"
PLATFORM_API_PORT="${PLATFORM_API_PORT:-2142}"
PLATFORM_WEB_PORT="${PLATFORM_WEB_PORT:-3000}"
GRAPH_CONFIG=""
RUNTIME_BACKEND_OVERRIDE="${RUNTIME_BACKEND-}"
TERMINAL_ENABLED_OVERRIDE="${RUNTIME_TERMINAL_ENABLED-}"
STARTED_KEYS=()
LOCAL_STACK_PYTHON="${LOCAL_STACK_PYTHON:-python3}"
LOCAL_STACK_WORKTREE=0
LOCAL_STACK_WORKER_JOBS=4

usage() {
  cat <<'EOF'
Usage: bash scripts/local-stack.sh <command>

Commands:
  init     initialize a linked Worktree private configuration and databases
  deps     install frozen dependencies using shared package caches
  doctor   validate local env, dependencies, config, and ports
  migrate  run Platform API and GraphHarbor database migrations
  seed     copy main-workspace configuration data once into migrated empty Worktree databases
  start    start Runtime API/Worker, Platform API, and Platform Web
  stop     stop this repository's stack, including manually started dev servers
  restart  stop and start the local stack
  restart-one <service>  restart only one application process
  status   show managed processes and HTTP health
  logs     show recent logs; optionally pass runtime-api, runtime-worker,
           platform-api, platform-web or redis
  list     show registered Worktree environments (no secrets)
  destroy  delete a stopped environment's data: destroy --confirm <environment-id>

Environment:
  RUNTIME_BACKEND=local|docker (default: local)
  RUNTIME_TERMINAL_ENABLED=0|1 (default: 1 for local stack)
EOF
}

load_stack_identity() {
  local exports
  exports="$("$LOCAL_STACK_PYTHON" "$ROOT_DIR/scripts/local_stack_worktree.py" exports "$ROOT_DIR" "$@")" || exit 1
  eval "$exports"
  PID_DIR="$STATE_DIR/pids"
  LOG_DIR="$STATE_DIR/logs"
  if [ "$LOCAL_STACK_WORKTREE" = 1 ]; then RUNTIME_BACKEND_OVERRIDE=local; fi
}

die() {
  printf 'ERROR %s\n' "$1" >&2
  exit 1
}

load_runtime_env() {
  [ -f "$RUNTIME_ENV_FILE" ] || die "missing Runtime env file: $RUNTIME_ENV_FILE"
  [ -f "$PLATFORM_ENV_FILE" ] || die "missing Platform API env file: $PLATFORM_ENV_FILE"
  require_command python3
  local platform_runtime_secret
  platform_runtime_secret="$("$LOCAL_STACK_PYTHON" - "$PLATFORM_ENV_FILE" <<'PY'
import sys
from pathlib import Path

from dotenv import dotenv_values

value = dotenv_values(Path(sys.argv[1])).get("PLATFORM_API_RUNTIME_DELEGATION_SECRET")
if not value:
    raise SystemExit("Platform runtime delegation secret is empty")
print(value)
PY
)"
  set -a
  export PLATFORM_API_RUNTIME_DELEGATION_SECRET="$platform_runtime_secret"
  # shellcheck disable=SC1090
  if [ "$LOCAL_STACK_WORKTREE" = 0 ]; then
    . "$RUNTIME_ENV_FILE"
  fi
  set +a
  export RUNTIME_BACKEND="${RUNTIME_BACKEND_OVERRIDE:-${RUNTIME_BACKEND:-local}}"
  export RUNTIME_TERMINAL_ENABLED="${TERMINAL_ENABLED_OVERRIDE:-${RUNTIME_TERMINAL_ENABLED:-1}}"
  case "$RUNTIME_TERMINAL_ENABLED" in
    0|1) ;;
    *) die "RUNTIME_TERMINAL_ENABLED must be 0 or 1" ;;
  esac
  case "$RUNTIME_BACKEND" in
    local|docker) ;;
    *) die "RUNTIME_BACKEND must be local or docker" ;;
  esac
  printf '[config] Runtime backend: %s (changes require Runtime API/Worker restart)\n' "$RUNTIME_BACKEND"
  RUNTIME_PORT="${RUNTIME_PORT:-${RUNTIME_SERVICE_PORT:-8123}}"
  GRAPH_CONFIG="${RUNTIME_GRAPH_CONFIG_PATH:-$RUNTIME_DIR/langgraph.json}"
  export PLATFORM_THREAD_AUTHORIZATION_URL="${PLATFORM_THREAD_AUTHORIZATION_URL:-http://127.0.0.1:$PLATFORM_API_PORT/api/runtime/internal/thread-authorization}"
  export RUNTIME_PORT PLATFORM_API_PORT PLATFORM_WEB_PORT
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command is missing: $1"
}

shell_quote() {
  printf '%q' "$1"
}

pid_file() {
  printf '%s/%s.pid' "$PID_DIR" "$1"
}

read_pid() {
  local file
  file="$(pid_file "$1")"
  [ -f "$file" ] || return 1
  tr -d '[:space:]' < "$file"
}

pid_alive() {
  local pid="$1"
  [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1
}

managed_alive() {
  local key="$1"
  local pid
  pid="$(read_pid "$key" 2>/dev/null || true)"
  if pid_alive "$pid" && python3 "$ROOT_DIR/scripts/local_stack_processes.py" "$ROOT_DIR" "$key" "$pid" >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

port_in_use() {
  lsof -ti "tcp:$1" -sTCP:LISTEN >/dev/null 2>&1
}

check_port() {
  local key="$1"
  local port="$2"
  if ! port_in_use "$port"; then
    return 0
  fi

  local owner_status
  owner_status="$(python3 "$ROOT_DIR/scripts/local_stack_processes.py" port-owner "$ROOT_DIR" "$key" "$port" 2>/dev/null || true)"
  case "$owner_status" in
    owned*)
      if managed_alive "$key"; then return 0; fi
      die "port $port is used by an untracked $key; stop this environment explicitly before starting"
      ;;
    external*)
      local ext_detail
      ext_detail="$(echo "$owner_status" | cut -d' ' -f2-)"
      die "port $port is already in use by external process ($ext_detail); refusing to kill external process"
      ;;
    *)
      die "port $port is already in use; refusing to kill an unmanaged process"
      ;;
  esac
}

spawn_detached() {
  local workdir="$1"
  local command="$2"
  local logfile="$3"

  python3 - "$workdir" "$command" "$logfile" <<'PY'
import os
import subprocess
import sys

workdir, command, logfile = sys.argv[1:]
environment = dict(os.environ)
environment.pop("LOCAL_STACK_LOCKED_ROOT", None)
environment.pop("LOCAL_STACK_PG_ADMIN_DSN", None)
with open(logfile, "ab", buffering=0) as stream:
    process = subprocess.Popen(
        ["/bin/bash", "-lc", f"exec {command}"],
        cwd=workdir,
        stdin=subprocess.DEVNULL,
        stdout=stream,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
        env=environment,
    )
print(process.pid)
PY
}

start_process() {
  local key="$1"
  local workdir="$2"
  local command="$3"
  local logfile="$4"
  local port="${5:-}"
  local pid

  if managed_alive "$key"; then
    printf '[skip] %s already running\n' "$key"
    return
  fi
  local untracked
  untracked="$(python3 "$ROOT_DIR/scripts/local_stack_processes.py" find "$ROOT_DIR" "$key")"
  [ -z "$untracked" ] || die "$key has untracked processes in this environment; stop them explicitly first"
  mkdir -p "$PID_DIR" "$LOG_DIR"
  rm -f "$(pid_file "$key")"
  [ -z "$port" ] || check_port "$key" "$port"
  pid="$(spawn_detached "$workdir" "$command" "$logfile")"
  printf '%s\n' "$pid" > "$(pid_file "$key")"
  STARTED_KEYS+=("$key")
  printf '[start] %s pid=%s\n' "$key" "$pid"
}

start_managed_key() {
  local key="$1"
  case "$key" in
    redis)
      start_process redis "$STATE_DIR" \
        "redis-server $(shell_quote "$STATE_DIR/redis.conf")" \
        "$LOG_DIR/redis.log" "$LOCAL_STACK_REDIS_PORT"
      ;;
    runtime-api)
      start_process runtime-api "$RUNTIME_DIR" \
        "env RUNTIME_SELF_URL=http://127.0.0.1:$(shell_quote "$RUNTIME_PORT") uv run --no-sync --frozen graphharbor serve --host 127.0.0.1 --port $(shell_quote "$RUNTIME_PORT") --config $(shell_quote "$GRAPH_CONFIG") --n-jobs-per-worker 0" \
        "$LOG_DIR/runtime-api.log" "$RUNTIME_PORT"
      ;;
    runtime-worker)
      start_process runtime-worker "$RUNTIME_DIR" \
        "env PLATFORM_RUNTIME_MESSAGE_AUTH_URL=http://127.0.0.1:$(shell_quote "$PLATFORM_API_PORT")/api/runtime/internal/message-authorization PLATFORM_RUNTIME_MEMORY_AUTH_URL=http://127.0.0.1:$(shell_quote "$PLATFORM_API_PORT")/api/runtime/internal/memory-authorization uv run --no-sync --frozen graphharbor worker --config $(shell_quote "$GRAPH_CONFIG") --n-jobs-per-worker $(shell_quote "$LOCAL_STACK_WORKER_JOBS")" \
        "$LOG_DIR/runtime-worker.log"
      ;;
    platform-api)
      start_process platform-api "$PLATFORM_API_DIR" \
        "uv run --no-sync --frozen uvicorn platform_api.main:create_app --factory --host 127.0.0.1 --port $(shell_quote "$PLATFORM_API_PORT") --reload" \
        "$LOG_DIR/platform-api.log" "$PLATFORM_API_PORT"
      ;;
    platform-web)
      start_process platform-web "$PLATFORM_WEB_DIR" \
        "env VITE_PLATFORM_API_URL=/ VITE_PLATFORM_API_RUNTIME_ENABLED=true VITE_DEV_PORT=$(shell_quote "$PLATFORM_WEB_PORT") VITE_DEV_PROXY_TARGET=http://127.0.0.1:$(shell_quote "$PLATFORM_API_PORT") pnpm exec vite --host 127.0.0.1 --port $(shell_quote "$PLATFORM_WEB_PORT")" \
        "$LOG_DIR/platform-web.log" "$PLATFORM_WEB_PORT"
      ;;
    *)
      die "unknown managed process: $key"
      ;;
  esac
}

stop_process() {
  local key="$1"
  local port="${2:-}"
  if [ -z "$port" ]; then
    case "$key" in
      redis) port="$LOCAL_STACK_REDIS_PORT" ;;
      runtime-api) port="$RUNTIME_PORT" ;;
      platform-api) port="$PLATFORM_API_PORT" ;;
      platform-web) port="$PLATFORM_WEB_PORT" ;;
    esac
  fi
  # PID files can be stale or absent after a manual dev start. Resolve ownership
  # from the app directory, listening port, and executable; never kill an unrelated port owner.
  if [ -n "$port" ]; then
    python3 "$ROOT_DIR/scripts/local_stack_processes.py" stop "$ROOT_DIR" "$key" "$port"
  else
    python3 "$ROOT_DIR/scripts/local_stack_processes.py" stop "$ROOT_DIR" "$key"
  fi
  rm -f "$(pid_file "$key")"
}

wait_http() {
  local name="$1"
  local url="$2"
  local timeout="${3:-60}"
  local elapsed=0
  while [ "$elapsed" -lt "$timeout" ]; do
    if curl -fsS --max-time 2 "$url" >/dev/null 2>&1; then
      printf '[ready] %s %s (%ss)\n' "$name" "$url" "$elapsed"
      return
    fi
    sleep 1
    elapsed=$((elapsed + 1))
    if [ $((elapsed % 10)) -eq 0 ]; then
      printf '[wait] %s still starting (%ss/%ss)...\n' "$name" "$elapsed" "$timeout"
    fi
  done
  die "$name did not become ready within ${timeout}s: $url"
}

require_managed_process() {
  managed_alive "$1" || die "$1 exited during startup; inspect $LOG_DIR/$1.log"
}

cleanup_startup_failure() {
  local exit_code=$?
  [ "$exit_code" -eq 0 ] && return
  set +e
  for ((i = ${#STARTED_KEYS[@]} - 1; i >= 0; i--)); do
    stop_process "${STARTED_KEYS[$i]}"
  done
  exit "$exit_code"
}

validate_runtime() {
  load_runtime_env
  check_installed_sources
  require_command uv
  require_command python3
  [ -f "$GRAPH_CONFIG" ] || die "missing Runtime graph config: $GRAPH_CONFIG"
  (cd "$RUNTIME_DIR" && uv run --no-sync --frozen python scripts/validate_runtime_config.py \
    --env-file "$RUNTIME_ENV_FILE")
}

check_redis() {
  (cd "$RUNTIME_DIR" && uv run --no-sync --frozen python - "$RUNTIME_ENV_FILE" <<'PY'
import asyncio
import os
import sys
from pathlib import Path

from dotenv import dotenv_values
from redis.asyncio import Redis


async def main() -> None:
    settings = {**dotenv_values(Path(sys.argv[1])), **os.environ}
    redis_uri = str(settings.get("REDIS_URI") or "").strip()
    if not redis_uri:
        raise SystemExit("REDIS_URI is empty")
    client = Redis.from_url(redis_uri)
    try:
        await client.ping()
    except Exception as exc:
        raise SystemExit("Redis is unavailable at REDIS_URI") from exc
    finally:
        await client.aclose()


asyncio.run(main())
print("Redis connectivity check passed")
PY
  )
}

check_postgres() {
  require_command pg_isready
  local endpoint
  endpoint="$(python3 - "$RUNTIME_ENV_FILE" <<'PY'
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values

settings = dotenv_values(Path(sys.argv[1]))
uri = str(settings.get("DATABASE_URI") or "").strip()
parsed = urlparse(uri)
host = parsed.hostname or "127.0.0.1"
port = parsed.port or 5432
print(host, port)
PY
)"
  local host port
  read -r host port <<< "$endpoint"
  if ! pg_isready -q -t 30 -h "$host" -p "$port"; then
    local detail
    detail="$(pg_isready -t 30 -h "$host" -p "$port" 2>&1 || true)"
    local data_dir="/usr/local/var/postgresql@17"
    if [ -f "$data_dir/postmaster.pid" ]; then
      local pid
      pid="$(head -n 1 "$data_dir/postmaster.pid" 2>/dev/null || true)"
      if [ -n "$pid" ] && ! kill -0 "$pid" >/dev/null 2>&1; then
        die "PostgreSQL unavailable at $host:$port ($detail); stale postmaster.pid detected at $data_dir/postmaster.pid. Confirm the database process is stopped, remove that lock file manually, then restart PostgreSQL."
      fi
    fi
    die "PostgreSQL unavailable at $host:$port ($detail); start the configured local PostgreSQL service before starting the stack."
  fi
  printf 'PostgreSQL connectivity check passed (%s:%s)\n' "$host" "$port"
}

validate_stack() {
  validate_runtime
  check_postgres
  (cd "$PLATFORM_API_DIR" && uv run --no-sync --frozen python scripts/database.py preflight)
  if [ "$LOCAL_STACK_WORKTREE" = 1 ]; then
    require_command redis-server
    check_port redis "$LOCAL_STACK_REDIS_PORT"
    if managed_alive redis; then check_redis; fi
  else
    check_redis
  fi
  require_command curl
  require_command lsof
  require_command pnpm
  [ -f "$PLATFORM_ENV_FILE" ] || die "missing Platform API env file: $PLATFORM_ENV_FILE"
  (cd "$PLATFORM_API_DIR" && uv run --no-sync --frozen python - "$RUNTIME_PORT" "$RUNTIME_ENV_FILE" "$PLATFORM_ENV_FILE" <<'PY'
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

runtime_port, runtime_env_path, platform_env_path = sys.argv[1:]
runtime = {**dotenv_values(Path(runtime_env_path)), **os.environ}
platform = {**dotenv_values(platform_env_path), **os.environ}
expected_upstream = f"http://127.0.0.1:{runtime_port}"
upstream = str(platform.get("PLATFORM_API_LANGGRAPH_UPSTREAM_URL") or "").rstrip("/")
if upstream != expected_upstream:
    raise SystemExit(
        f"Platform upstream must be {expected_upstream}, got {upstream or '<empty>'}"
    )
if not platform.get("PLATFORM_API_RUNTIME_DELEGATION_SECRET"):
    raise SystemExit("Platform runtime delegation secret is empty")
if platform["PLATFORM_API_RUNTIME_DELEGATION_SECRET"] != runtime.get(
    "PLATFORM_RUNTIME_DELEGATION_SECRET"
):
    raise SystemExit("Platform and Runtime delegation secrets do not match")
PY
  )
  check_port runtime-api "$RUNTIME_PORT"
  check_port platform-api "$PLATFORM_API_PORT"
  check_port platform-web "$PLATFORM_WEB_PORT"
}

migrate() {
  validate_runtime
  check_postgres
  (cd "$PLATFORM_API_DIR" && uv run --no-sync --frozen python scripts/database.py upgrade)
  (cd "$RUNTIME_DIR" && uv run --no-sync --frozen graphharbor migrate upgrade)
  (cd "$RUNTIME_DIR" && uv run --no-sync --frozen python -m runtime_service.messaging)
}

start() {
  trap cleanup_startup_failure EXIT
  STARTED_KEYS=()
  validate_stack
  migrate
  if [ "$LOCAL_STACK_WORKTREE" = 1 ]; then
    "$LOCAL_STACK_PYTHON" "$ROOT_DIR/scripts/local_stack_worktree.py" seed "$ROOT_DIR" --if-empty
    start_managed_key redis
    for _ in {1..50}; do
      if port_in_use "$LOCAL_STACK_REDIS_PORT"; then break; fi
      sleep 0.1
    done
    require_managed_process redis
    check_redis
  fi
  start_managed_key runtime-api
  start_managed_key runtime-worker
  require_managed_process runtime-worker
  wait_http runtime-api "http://127.0.0.1:$RUNTIME_PORT/ready" 120
  require_managed_process runtime-api
  start_managed_key platform-api
  wait_http platform-api "http://127.0.0.1:$PLATFORM_API_PORT/_system/health"
  require_managed_process platform-api
  start_managed_key platform-web
  wait_http platform-web "http://127.0.0.1:$PLATFORM_WEB_PORT"
  require_managed_process platform-web
  printf '[done] local stack is ready: http://127.0.0.1:%s\n' "$PLATFORM_WEB_PORT"
  trap - EXIT
}

status() {
  printf '[environment] %s\n[web] http://127.0.0.1:%s\n[api] http://127.0.0.1:%s\n[runtime] http://127.0.0.1:%s\n[state] %s\n' \
    "${LOCAL_STACK_ID:-primary}" "$PLATFORM_WEB_PORT" "$PLATFORM_API_PORT" "$RUNTIME_PORT" "$STATE_DIR"
  local keys=(runtime-api runtime-worker platform-api platform-web)
  if [ "$LOCAL_STACK_WORKTREE" = 1 ]; then keys+=(redis); fi
  for key in "${keys[@]}"; do
    if managed_alive "$key"; then
      printf '%-16s running\n' "$key"
    else
      local real_pids
      real_pids="$(python3 "$ROOT_DIR/scripts/local_stack_processes.py" find "$ROOT_DIR" "$key" 2>/dev/null || true)"
      if [ -n "$real_pids" ]; then
        printf '%-16s running (untracked pid: %s)\n' "$key" "$real_pids"
      else
        printf '%-16s stopped\n' "$key"
      fi
    fi
  done
  curl -fsS --max-time 2 "http://127.0.0.1:$RUNTIME_PORT/ready" >/dev/null 2>&1 \
    && echo "runtime-ready    yes" || echo "runtime-ready    no"
  curl -fsS --max-time 2 "http://127.0.0.1:$PLATFORM_API_PORT/_system/health" >/dev/null 2>&1 \
    && echo "platform-api     yes" || echo "platform-api     no"
}

logs() {
  local key="${1:-}"
  if [ -n "$key" ]; then
    [ -f "$LOG_DIR/$key.log" ] || die "unknown or unavailable log: $key"
    tail -n 80 "$LOG_DIR/$key.log"
    return
  fi
  for file in "$LOG_DIR"/*.log; do
    [ -e "$file" ] || continue
    printf '\n== %s ==\n' "$(basename "$file")"
    tail -n 20 "$file"
  done
}

restart_one() {
  local key="$1"
  load_runtime_env
  case "$key" in
    runtime-api|runtime-worker|platform-api|platform-web) ;;
    *) die "restart-one requires one of runtime-api, runtime-worker, platform-api, platform-web" ;;
  esac
  # Reject invalid Runtime configuration before stopping a healthy process.
  case "$key" in
    runtime-api|runtime-worker) validate_runtime ;;
  esac
  if [ "$key" = "platform-api" ]; then
    (cd "$PLATFORM_API_DIR" && uv run --no-sync --frozen python scripts/database.py upgrade)
  fi
  stop_process "$key"
  start_managed_key "$key"
  case "$key" in
    runtime-api) wait_http runtime-api "http://127.0.0.1:$RUNTIME_PORT/ready" 120 ;;
    platform-api) wait_http platform-api "http://127.0.0.1:$PLATFORM_API_PORT/_system/health" ;;
    platform-web) wait_http platform-web "http://127.0.0.1:$PLATFORM_WEB_PORT" ;;
    runtime-worker) require_managed_process "$key" ;;
  esac
}

deps() {
  require_command uv
  require_command pnpm
  uv sync --project "$RUNTIME_DIR" --python 3.13 --frozen
  uv sync --project "$PLATFORM_API_DIR" --python 3.13 --frozen
  pnpm --dir "$PLATFORM_WEB_DIR" install --frozen-lockfile
  check_installed_sources
}

check_installed_sources() {
  for app in runtime-service platform-api; do
    local module="${app//-/_}"
    [ -x "$ROOT_DIR/apps/$app/.venv/bin/python" ] || die "missing $app dependencies; run bash scripts/local-stack.sh deps"
    "$ROOT_DIR/apps/$app/.venv/bin/python" - "$module" "$ROOT_DIR/apps/$app/src" <<'PY'
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.find_spec(sys.argv[1])
paths = list(spec.submodule_search_locations or []) if spec else []
if not paths or any(not Path(path).resolve().is_relative_to(Path(sys.argv[2]).resolve()) for path in paths):
    raise SystemExit("Dependency environment imports another Worktree's application source")
print(f"[deps] {sys.argv[1]} resolves to this Worktree")
PY
  done
}

stop_stack() {
  stop_process platform-web
  stop_process platform-api
  stop_process runtime-worker
  stop_process runtime-api
  if [ "$LOCAL_STACK_WORKTREE" = 1 ]; then stop_process redis; fi
}

command="${1:-help}"
case "$command" in
  init|seed|destroy|list)
    "$LOCAL_STACK_PYTHON" "$ROOT_DIR/scripts/local_stack_worktree.py" "$command" "$ROOT_DIR" "${@:2}"
    exit
    ;;
  help|-h|--help) usage; return 0 2>/dev/null || exit 0 ;;
  stop|status|logs) load_stack_identity --resources-only ;;
  doctor|migrate|start|restart|restart-one|deps) load_stack_identity ;;
  *) usage >&2; exit 2 ;;
esac
case "$command" in
  deps) deps ;;
  doctor) validate_stack ;;
  migrate) migrate ;;
  start) start ;;
  stop) stop_stack ;;
  restart) validate_runtime; stop_stack; start ;;
  restart-one) restart_one "${2:-}" ;;
  status) status ;;
  logs) logs "${2:-}" ;;
  help|-h|--help) usage ;;
  *) usage >&2; exit 2 ;;
esac
