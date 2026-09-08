#!/usr/bin/env bash
# Seed the demo data against a deployed stack. Run once after the first Railway
# deploy, from a checkout of this repo, with DATABASE_URL pointing at the deploy's
# Postgres — e.g.
#
#     railway run --service ai-platform ./scripts/deploy-seed.sh
#
# or set DATABASE_URL by hand. Idempotent: the simulator resets to a fresh
# baseline and knowledge.ingest truncates + reloads.
set -euo pipefail
cd "$(dirname "$0")/.."

# SQLAlchemy needs the +psycopg scheme; managed Postgres hands out plain postgresql://
export DATABASE_URL="${DATABASE_URL/#postgresql:\/\//postgresql+psycopg://}"

echo "[deploy-seed] waiting for the schema (enterprise Flyway creates it)…"
for _ in $(seq 1 90); do
  if (cd ai-platform && uv run python - <<'PY'
import os, sys, sqlalchemy
try:
    e = sqlalchemy.create_engine(os.environ["DATABASE_URL"])
    with e.connect() as c:
        sys.exit(0 if c.exec_driver_sql("select to_regclass('public.trades')").scalar() else 1)
except Exception:
    sys.exit(1)
PY
  ); then echo "[deploy-seed] schema present"; break; fi
  sleep 4
done

echo "[deploy-seed] seeding all scenarios…"
(cd simulator && uv run python -m simulator.cli seed --scenario all)

echo "[deploy-seed] ingesting the knowledge corpus…"
(cd ai-platform && uv run python -m knowledge.ingest --fixtures CN-2026-081)

echo "[deploy-seed] done"
