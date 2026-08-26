#!/usr/bin/env bash
# Backs up the CCC MySQL database to a timestamped, gzip-compressed SQL dump.
# Reads connection info from the same CCC_DB_* env vars the app itself uses.
#
# Manual run:  ops/backup_ccc.sh [output-dir]
# Cron (daily 2am, keep on the box that also hosts the DB):
#   0 2 * * * CCC_DB_PW=... /opt/ccc/ops/backup_ccc.sh /var/backups/ccc >> /var/log/ccc-backup.log 2>&1
set -euo pipefail

OUT_DIR="${1:-./backups}"
mkdir -p "$OUT_DIR"

DB_HOST="${CCC_DB_HOST:-127.0.0.1}"
DB_USER="${CCC_DB_USER:-ccc}"
DB_PW="${CCC_DB_PW:?CCC_DB_PW must be set}"
DB_NAME="${CCC_DB_NAME:-ccc}"

STAMP=$(date +%Y%m%d-%H%M%S)
OUT_FILE="$OUT_DIR/ccc-$STAMP.sql.gz"

mysqldump \
  --host="$DB_HOST" --user="$DB_USER" --password="$DB_PW" \
  --single-transaction --routines --triggers --hex-blob \
  "$DB_NAME" | gzip > "$OUT_FILE"

echo "Backup written to $OUT_FILE ($(du -h "$OUT_FILE" | cut -f1))"

# Keep the last 14 daily backups on this box; the real retention policy (offsite
# copy, longer retention) is an infra decision - see RUNBOOK.md.
find "$OUT_DIR" -name 'ccc-*.sql.gz' -mtime +14 -delete
