#!/bin/sh
set -eu

create_user_and_db() {
  db_name="$1"
  db_user="$2"
  db_password="$3"
  export AITESTLAB_INIT_DB_PASSWORD="$db_password"

  psql -X -v ON_ERROR_STOP=1 --username "${POSTGRES_USER:-${PGUSER:?Set POSTGRES_USER or PGUSER}}" --dbname postgres \
    --set=db_name="$db_name" --set=db_user="$db_user" <<'EOSQL'
\set db_password `printf '%s' "$AITESTLAB_INIT_DB_PASSWORD"`
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'db_user', :'db_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'db_user')
\gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'db_name', :'db_user')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'db_name')
\gexec
EOSQL
}

case "${1:-}" in
  --platform-only) ;;
  "") ;;
  *) echo "Usage: $0 [--platform-only]" >&2; exit 2 ;;
esac

if [ "${1:-}" != "--platform-only" ]; then
  create_user_and_db "${RUNTIME_POSTGRES_DB:-runtime_service}" "${RUNTIME_POSTGRES_USER:-runtime_service}" "${RUNTIME_POSTGRES_PASSWORD:-runtime_service}"
fi
create_user_and_db "${PLATFORM_API_POSTGRES_DB:-platform_api}" "${PLATFORM_API_POSTGRES_USER:-platform_api}" "${PLATFORM_API_POSTGRES_PASSWORD:-platform_api}"
if [ "${1:-}" != "--platform-only" ]; then
  create_user_and_db "${INTERACTION_DATA_SERVICE_POSTGRES_DB:-interaction_data_service}" "${INTERACTION_DATA_SERVICE_POSTGRES_USER:-interaction_data_service}" "${INTERACTION_DATA_SERVICE_POSTGRES_PASSWORD:-interaction_data_service}"
fi
