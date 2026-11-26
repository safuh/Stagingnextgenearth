#!/usr/bin/env bash
# Create and verify a PostgreSQL custom-format backup without exposing credentials.
set -Eeuo pipefail
umask 077

: "${BACKUP_DATABASE_URL:?Set BACKUP_DATABASE_URL to a PostgreSQL URI (postgresql://...), not the async SQLAlchemy URL}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

if [[ ! "$RETENTION_DAYS" =~ ^[0-9]+$ ]] || (( RETENTION_DAYS < 1 )); then
  echo "RETENTION_DAYS must be a positive integer" >&2
  exit 2
fi
for command in pg_dump pg_restore sha256sum flock; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Required command not found: $command" >&2
    exit 2
  }
done

mkdir -p -- "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
exec 9>"$BACKUP_DIR/.backup.lock"
flock -n 9 || { echo "Another backup is already running" >&2; exit 3; }

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
base="nextgenearth-${stamp}"
tmp="$BACKUP_DIR/.${base}.dump.tmp"
final="$BACKUP_DIR/${base}.dump"
checksum_tmp="$BACKUP_DIR/.${base}.sha256.tmp"
checksum="$BACKUP_DIR/${base}.sha256"
cleanup() { rm -f -- "$tmp" "$checksum_tmp"; }
trap cleanup EXIT

# Use PGPASSFILE or another libpq-supported secret mechanism. Never put a
# database password on the command line or in shell history.
pg_dump --format=custom --no-owner --no-acl --file="$tmp" "$BACKUP_DATABASE_URL"
pg_restore --list "$tmp" >/dev/null
sha256sum "$tmp" | sed "s#  .*#  ${base}.dump#" > "$checksum_tmp"
mv -- "$tmp" "$final"
mv -- "$checksum_tmp" "$checksum"
chmod 600 "$final" "$checksum"

# Retention is applied only after a new archive has passed structural checks.
find "$BACKUP_DIR" -maxdepth 1 -type f -name 'nextgenearth-*.dump' -mtime "+$RETENTION_DAYS" -delete
find "$BACKUP_DIR" -maxdepth 1 -type f -name 'nextgenearth-*.sha256' -mtime "+$RETENTION_DAYS" -delete

echo "Backup created and structurally verified: $final"
echo "Checksum: $checksum"
echo "Copy the archive and checksum to encrypted off-site storage; local copies alone are not disaster recovery."
