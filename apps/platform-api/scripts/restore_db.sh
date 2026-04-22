#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 3 ]; then
  echo "usage:"
  echo "  $0 sqlite <backup-file> <database-file>"
  echo "  $0 postgres <backup-file> <database-url>"
  exit 1
fi

MODE="$1"
BACKUP_FILE="$2"
TARGET="$3"

case "$MODE" in
  sqlite)
    mkdir -p "$(dirname "$TARGET")"
    cp "$BACKUP_FILE" "$TARGET"
    ;;
  postgres)
    if ! command -v pg_restore >/dev/null 2>&1; then
      echo "pg_restore is required for postgres restores"
      exit 1
    fi
    pg_restore --clean --if-exists --no-owner --dbname="$TARGET" "$BACKUP_FILE"
    ;;
  *)
    echo "unsupported mode: $MODE"
    exit 1
    ;;
esac

echo "database restored: $TARGET"
