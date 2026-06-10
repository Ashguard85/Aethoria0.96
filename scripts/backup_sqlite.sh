#!/usr/bin/env sh
set -eu
DATA_DIR="${AETHORIA_DATA_DIR:-./runtime/aethoria-data}"
DB_FILE="${AETHORIA_DB_FILE:-aethoria.sqlite}"
BACKUP_DIR="${AETHORIA_BACKUP_DIR:-./runtime/backups}"
mkdir -p "$BACKUP_DIR"
TS=$(date +%Y%m%d-%H%M%S)
if [ ! -f "$DATA_DIR/$DB_FILE" ]; then
  echo "DB nicht gefunden: $DATA_DIR/$DB_FILE" >&2
  exit 1
fi
cp "$DATA_DIR/$DB_FILE" "$BACKUP_DIR/aethoria-$TS.sqlite"
echo "Backup erstellt: $BACKUP_DIR/aethoria-$TS.sqlite"
