#!/usr/bin/env bash
# Applies enterprise's Flyway SQL migrations directly via psql.
#
# Spring Boot normally applies these itself on startup (flyway.enabled: true).
# This script exists for the two paths that need a ready schema without
# starting the JVM app: `scripts/verify.sh` (so simulator's DB-backed tests
# have tables to write to) and local `make seed` runs against a bare `docker
# compose up postgres`. It is a thin, idempotent substitute for Flyway's own
# bookkeeping — safe to run repeatedly, but it is not a replacement for Flyway
# in the running `enterprise` service, which still owns migration history.
set -euo pipefail
cd "$(dirname "$0")/.."

: "${PGHOST:=localhost}"
: "${PGPORT:=5432}"
: "${PGUSER:=finops}"
: "${PGPASSWORD:=finops}"
: "${PGDATABASE:=finops}"
export PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE

MIGRATIONS_DIR="enterprise/src/main/resources/db/migration"

already_migrated() {
    psql -tAc "select to_regclass('public.trades') is not null" | grep -q '^t$'
}

if already_migrated; then
    echo "[migrate] schema already present, skipping"
    exit 0
fi

for f in "$MIGRATIONS_DIR"/V*.sql; do
    echo "[migrate] applying $(basename "$f")"
    psql -v ON_ERROR_STOP=1 -f "$f" >/dev/null
done
echo "[migrate] done"
