# PostgreSQL backup, restore and recovery

This runbook applies to the production PostgreSQL/PostGIS database used by the
API. Backups contain personal, organisational and potentially sensitive research
metadata. Restrict access, encrypt at rest and in transit, and record the person
responsible for backup verification.

## Backup policy

- Use a managed PostgreSQL point-in-time recovery service where available, plus
  regular logical exports for portability.
- Minimum initial schedule: daily logical backup; retain at least 14 daily copies
  and a separate weekly/monthly encrypted off-site copy according to the
  organisation's approved retention policy.
- Keep database backups separate from object-storage backups. Dataset file bytes
  are stored in private object storage and are **not** included in `pg_dump`.
  Back up object storage/versioning and verify restoration of metadata-to-object
  references together.
- Keep encryption keys, database credentials and backup archives in separate
  secret/storage controls. Never commit `.env`, `.pgpass`, dumps or keys.
- Define and approve recovery-point objective (RPO), recovery-time objective
  (RTO), retention, legal holds and deletion policy before production launch.

## Create a logical backup

Install PostgreSQL client tools compatible with the server major version. Use a
standard libpq URL for the backup command (the application `DATABASE_URL` uses
SQLAlchemy's `+asyncpg` driver and is not accepted by `pg_dump`). Prefer a
restricted backup role with read access to the required schemas and sequences.

```bash
install -d -m 700 backups
install -m 600 /dev/null "$HOME/.pgpass"
# Add the managed database host:port:database:backup_user:password entry
# using a secret manager; do not paste the password into shell history.
chmod 600 "$HOME/.pgpass"
export PGPASSFILE="$HOME/.pgpass"
export BACKUP_DATABASE_URL='postgresql://backup_user@db-host:5432/nextgen'
BACKUP_DIR=/secure/local/path/backups RETENTION_DAYS=14 \
  bash scripts/backup_postgres.sh
```

The script uses a restrictive umask, serialises concurrent runs, writes to a
temporary file, validates the custom archive with `pg_restore --list`, writes a
SHA-256 sidecar and only then publishes the archive. It prunes local archives
older than the configured retention period only after a new verified backup is
created. The script does not encrypt or upload the archive: use an encrypted
backup volume and copy it to approved off-site storage with access logging.

## Restore drill (never experiment on production)

1. Provision a **new, empty, isolated staging/recovery database** on a compatible
   PostgreSQL major version with PostGIS and required extensions available.
2. Retrieve the dump and checksum from off-site storage; verify the checksum:

   ```bash
   cd /secure/restore/location
   sha256sum --check nextgenearth-YYYYMMDDTHHMMSSZ.sha256
   pg_restore --list nextgenearth-YYYYMMDDTHHMMSSZ.dump >/dev/null
   ```

3. Restore into the empty recovery database using a dedicated restore role. Do
   not point `PGRESTORE_DATABASE_URL` at production during a drill:

   ```bash
   export PGRESTORE_DATABASE_URL='postgresql://restore_user@recovery-host:5432/nextgen_restore'
   pg_restore --exit-on-error --no-owner --no-acl \
     --dbname="$PGRESTORE_DATABASE_URL" \
     nextgenearth-YYYYMMDDTHHMMSSZ.dump
   ```

4. Run `uv run alembic current` with the recovery database configured, then
   verify tenant counts, representative organisation/programme/research records,
   spatial extension availability, and application read-only smoke checks.
   Compare object-storage keys and restore corresponding object versions using
   the object-storage provider's separate recovery procedure.
5. Record archive checksum, source timestamp, restore start/end, migration head,
   validation evidence, issues, operator and elapsed time. Destroy the temporary
   recovery database under the approved disposal policy after sign-off.

For point-in-time recovery, use the managed provider's documented PITR workflow
and restore to a separate instance. Do not improvise WAL recovery commands on
production.

## Release and incident controls

- Take and verify a pre-release backup before schema migrations that may be
  destructive or difficult to reverse.
- Migrations are explicit release operations (`uv run alembic upgrade head`),
  not API startup actions. Confirm the target database and current revision
  before migration.
- A successful `pg_dump` or archive listing is not a restore drill. Production
  readiness requires a timed restore to an isolated database and a recorded
  owner-approved result.
- In an incident, preserve logs and evidence, restrict access, notify the named
  incident/data-protection owners, and follow the organisation's approved
  breach-response and legal notification procedures.

## Launch blockers to assign

- [ ] Named database backup owner and backup monitoring recipient.
- [ ] Managed backup/PITR configuration and documented RPO/RTO.
- [ ] Encrypted off-site backup destination and access policy.
- [ ] Separate object-storage backup/versioning and recovery test.
- [ ] Successful isolated restore drill with recorded duration and evidence.
- [ ] Approved retention, deletion and legal-hold schedule.
