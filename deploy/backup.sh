#!/usr/bin/env bash
# Daily SQLite backup — run from cron or manually.
# Usage: ./backup.sh [/path/to/db] [/path/to/backup/dir]

set -euo pipefail

DB_PATH="${1:-/opt/trade-engine/app/data/trade.db}"
BACKUP_DIR="${2:-/opt/trade-engine/backups}"
DATE=$(date +"%Y-%m-%d_%H%M%S")
DEST="${BACKUP_DIR}/trade_${DATE}.db"

mkdir -p "$BACKUP_DIR"

# Use SQLite's online backup so we don't lock the live DB.
sqlite3 "$DB_PATH" ".backup '$DEST'"

# Keep the 30 most recent backups; delete older ones.
ls -tp "${BACKUP_DIR}"/trade_*.db | tail -n +31 | xargs -r rm --

echo "Backed up to $DEST"
