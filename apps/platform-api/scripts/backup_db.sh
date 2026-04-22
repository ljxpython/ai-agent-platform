#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 3 ]; then
  echo "usage:"
  echo "  $0 sqlite <database-file> <backup-file>"
  echo "  $0 postgres <database-url> <backup-file>"
  exit 1
fi

MODE="$1"
SOURCE="$2"
BACKUP_FILE="$3"

mkdir -p "$(dirname "$BACKUP_FILE")"

case "$MODE" in
  sqlite)
    cp "$SOURCE" "$BACKUP_FILE"
    ;;
  postgres)
    if ! command -v pg_dump >/dev/null 2>&1; then
      echo "pg_dump is required for postgres backups"
      exit 1
    fi
    pg_dump --format=custom --file="$BACKUP_FILE" "$SOURCE"
    ;;
  *)
    echo "unsupported mode: $MODE"
    exit 1
    ;;
esac

echo "backup created: $BACKUP_FILE"
