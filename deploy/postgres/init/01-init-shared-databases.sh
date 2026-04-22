#!/bin/sh
set -eu

create_user_and_db() {
  db_name="$1"
  db_user="$2"
  db_password="$3"

  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
    DO
    \$\$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$db_user') THEN
        CREATE ROLE "$db_user" LOGIN PASSWORD '$db_password';
      END IF;
    END
    \$\$;
EOSQL

  if ! psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$db_name'" | grep -q 1; then
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -c "CREATE DATABASE \"$db_name\" OWNER \"$db_user\";"
  fi
}

create_user_and_db "${RUNTIME_POSTGRES_DB:-runtime_service}" "${RUNTIME_POSTGRES_USER:-runtime_service}" "${RUNTIME_POSTGRES_PASSWORD:-runtime_service}"
create_user_and_db "${PLATFORM_API_POSTGRES_DB:-platform_api}" "${PLATFORM_API_POSTGRES_USER:-platform_api}" "${PLATFORM_API_POSTGRES_PASSWORD:-platform_api}"
create_user_and_db "${INTERACTION_DATA_SERVICE_POSTGRES_DB:-interaction_data_service}" "${INTERACTION_DATA_SERVICE_POSTGRES_USER:-interaction_data_service}" "${INTERACTION_DATA_SERVICE_POSTGRES_PASSWORD:-interaction_data_service}"
