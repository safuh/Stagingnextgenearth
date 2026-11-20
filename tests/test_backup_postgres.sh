#!/usr/bin/env bash
# Black-box regression tests for scripts/backup_postgres.sh.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/backup_postgres.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
BIN="$TMP/bin"
mkdir -p "$BIN"

cat > "$BIN/pg_dump" <<'MOCK'
#!/usr/bin/env bash
set -Eeuo pipefail
[[ "${MOCK_DUMP_FAIL:-0}" == 0 ]] || exit 41
for arg in "$@"; do
  case "$arg" in --file=*) printf 'mock-postgres-archive\n' > "${arg#--file=}" ;; esac
done
MOCK
cat > "$BIN/pg_restore" <<'MOCK'
#!/usr/bin/env bash
set -Eeuo pipefail
[[ "${MOCK_RESTORE_FAIL:-0}" == 0 ]] || exit 42
[[ "${1:-}" == --list && -s "${2:-}" ]]
MOCK
chmod +x "$BIN/pg_dump" "$BIN/pg_restore"
for command in sha256sum sed mv chmod mkdir flock date find rm; do
  ln -s "$(command -v "$command")" "$BIN/$command"
done

fail() { echo "FAIL: $*" >&2; exit 1; }
run_backup() {
  env PATH="$BIN:/usr/bin:/bin" BACKUP_DATABASE_URL='postgresql://backup@localhost/test' BACKUP_DIR="$1" "${@:2}" "$SCRIPT"
}

# Successful dump is structurally checked, checksummed, and permission-restricted.
SUCCESS="$TMP/success"
run_backup "$SUCCESS" >/dev/null
archive="$(find "$SUCCESS" -maxdepth 1 -name 'nextgenearth-*.dump' -print -quit)"
checksum="${archive%.dump}.sha256"
[[ -n "$archive" && -s "$archive" && -s "$checksum" ]] || fail "successful backup artifacts missing"
grep -q 'nextgenearth-.*\.dump' "$checksum" || fail "checksum does not name archive"
( cd "$SUCCESS" && sha256sum -c "$(basename "$checksum")" ) >/dev/null || fail "checksum verification failed"
[[ "$(stat -c '%a' "$archive")" == 600 && "$(stat -c '%a' "$checksum")" == 600 ]] || fail "backup permissions are not 0600"

# A dump failure must not publish a final archive or prune old backups.
DUMP_FAIL="$TMP/dump-fail"
mkdir -p "$DUMP_FAIL"
touch "$DUMP_FAIL/nextgenearth-old.dump" "$DUMP_FAIL/nextgenearth-old.sha256"
touch -d '30 days ago' "$DUMP_FAIL/nextgenearth-old.dump" "$DUMP_FAIL/nextgenearth-old.sha256"
if run_backup "$DUMP_FAIL" MOCK_DUMP_FAIL=1 >/dev/null 2>&1; then fail "dump failure unexpectedly succeeded"; fi
[[ -f "$DUMP_FAIL/nextgenearth-old.dump" ]] || fail "old backup pruned after dump failure"
[[ -z "$(find "$DUMP_FAIL" -maxdepth 1 -name 'nextgenearth-*.dump' ! -name 'nextgenearth-old.dump' -print -quit)" ]] || fail "partial archive was published"

# A restore-list validation failure must not publish the archive or prune retention.
RESTORE_FAIL="$TMP/restore-fail"
mkdir -p "$RESTORE_FAIL"
touch "$RESTORE_FAIL/nextgenearth-old.dump"
touch -d '30 days ago' "$RESTORE_FAIL/nextgenearth-old.dump"
if run_backup "$RESTORE_FAIL" MOCK_RESTORE_FAIL=1 >/dev/null 2>&1; then fail "restore validation failure unexpectedly succeeded"; fi
[[ -f "$RESTORE_FAIL/nextgenearth-old.dump" ]] || fail "old backup pruned after validation failure"
[[ -z "$(find "$RESTORE_FAIL" -maxdepth 1 -name 'nextgenearth-*.dump' ! -name 'nextgenearth-old.dump' -print -quit)" ]] || fail "unvalidated archive was published"

# Invalid retention configuration is rejected before invoking backup utilities.
if env PATH="$BIN:/usr/bin:/bin" BACKUP_DATABASE_URL='postgresql://backup@localhost/test' BACKUP_DIR="$TMP/invalid" RETENTION_DAYS=0 "$SCRIPT" >/dev/null 2>&1; then
  fail "zero-day retention unexpectedly accepted"
fi

echo "backup_postgres shell tests passed"
