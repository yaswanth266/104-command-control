# CCC backup & recovery

## Backup

`ops/backup_ccc.sh [output-dir]` runs `mysqldump` with `--single-transaction`
(consistent snapshot without locking the tables — important since this is a live
ticketing system) and gzips the output to `ccc-YYYYmmdd-HHMMSS.sql.gz`.

```bash
CCC_DB_HOST=127.0.0.1 CCC_DB_USER=ccc CCC_DB_PW=*** CCC_DB_NAME=ccc \
  ops/backup_ccc.sh /var/backups/ccc
```

On the live server, schedule it from `ccc.env`'s values via cron/systemd-timer,
e.g. daily at 02:00. The script keeps the last 14 daily dumps on-box and prunes
older ones — that is **not** a substitute for an offsite/off-box copy; someone
with server access needs to also ship these dumps somewhere else (S3, a second
host, etc.). That decision and its implementation are outside what I can set up
from here.

## Restore drill

Steps, and what to expect:

```bash
# 1. Decompress if needed
gunzip -k ccc-20260825-020000.sql.gz

# 2. Create a scratch database - NEVER restore directly over a live one
mysql -u root -p -e "CREATE DATABASE ccc_restore_check CHARACTER SET utf8mb4;"

# 3. Restore into the scratch database
mysql -u root -p ccc_restore_check < ccc-20260825-020000.sql

# 4. Compare row counts against the source
mysql -u root -p -e "
SELECT (SELECT COUNT(*) FROM ccc.ccc_ticket), (SELECT COUNT(*) FROM ccc_restore_check.ccc_ticket);"

# 5. Once satisfied, drop the scratch database
mysql -u root -p -e "DROP DATABASE ccc_restore_check;"
```

### Verified 2026-08-25 against the local dev `ccc` database (not production)

I ran this exact sequence end-to-end against the local dev copy of `ccc`
(confirmed non-production - see README) using the real `mysqldump`/`mysql`
binaries, not a simulation:

1. `mysqldump --single-transaction --routines --triggers --hex-blob ccc` → a
   243-line SQL dump.
2. Restored it into a fresh `ccc_restore_drill` database.
3. Compared **exact** `COUNT(*)` (not the `information_schema` estimate, which
   can be stale right after a restore) across every table:

   | table | ccc | ccc_restore_drill |
   |---|---|---|
   | ccc_ticket | 0 | 0 |
   | ccc_event | 0 | 0 |
   | ccc_user | 16 | 16 |
   | ccc_notification | 0 | 0 |
   | ccc_config | 0 | 0 |

4. Spot-checked that a real value round-tripped byte-for-byte: the `ccmanager`
   user's password hash was identical between source and restored copy.
5. Dropped `ccc_restore_drill` and deleted the dump file - nothing left behind.

One thing this drill caught: my first attempt at the row-count comparison used
`information_schema.tables.table_rows`, which showed a spurious 16-vs-15
mismatch on `ccc_user` purely because that column is an approximate estimate
that hasn't been refreshed right after an import - not a real discrepancy.
Always verify a restore with `SELECT COUNT(*)`, not the estimate.

The database used above had 0 tickets (this project is pre-go-live), so this
drill proves the *mechanics* work correctly, not that they'll perform
acceptably at production data volume/duration - that still needs to be timed
against a real production-sized dump on the actual server.

## Recommended production DB-user grants (not applied here - I don't have
access to the production server, and this needs whoever administers it)

The app should **not** connect as a MySQL superuser. Recommended minimum:

```sql
CREATE USER 'ccc'@'localhost' IDENTIFIED BY '...';
GRANT SELECT, INSERT, UPDATE, DELETE ON ccc.* TO 'ccc'@'localhost';
-- ccc_event is the audit trail (SOP: "never update or delete a row"). MySQL
-- supports per-table grants, so enforce that at the DB layer, not just in
-- application code where a bug or a future change could bypass it:
REVOKE UPDATE, DELETE ON ccc.ccc_event FROM 'ccc'@'localhost';
```

A separate, distinct account (not the app's `ccc` user) should own backups, and
that account is the one that needs `SELECT`/`LOCK TABLES` for `mysqldump`
(`--single-transaction` avoids needing `LOCK TABLES` on InnoDB, which this
schema exclusively uses).
