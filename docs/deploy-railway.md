# Deploying the demo to Railway

Four services in one Railway project: **postgres** (pgvector) · **enterprise**
(Java, 512 MB) · **ai-platform** (one Python process) · **portal** (static build
behind Caddy). The Java tier owns the schema (Flyway on boot); the demo data is
seeded once with a script after the first deploy.

Config-as-code lives in `ai-platform/railway.json`, `enterprise/railway.json`,
`portal/railway.json` (each picks the service's `Dockerfile`). Everything else is
dashboard work — this is the checklist.

---

## 0. Prerequisites

- A Railway account and the repo pushed to GitHub.
- An Anthropic API key (`console.anthropic.com`). It is **never** committed.
- Optional: the Railway CLI (`npm i -g @railway/cli`) for the one seeding step.

## 1. Project + Postgres

1. **New Project → Deploy from GitHub repo** → pick this repo. Railway creates one
   service; you'll add the rest.
2. **New → Database → PostgreSQL.** Rename it `postgres`.
3. Confirm pgvector: open the Postgres service → **Data** (or `railway connect`) and
   run `create extension if not exists vector;`. Railway's PG 16 image ships it. If
   the extension is missing, delete this DB and instead **New → Docker Image →
   `pgvector/pgvector:pg16`** with a small volume at `/var/lib/postgresql/data` and
   `POSTGRES_USER/PASSWORD/DB = finops`.

## 2. The three app services

For each of `enterprise`, `ai-platform`, `portal`: **New → GitHub Repo →** this repo,
then **Settings → Root Directory** = `/enterprise`, `/ai-platform`, `/portal`
respectively. Railway reads that folder's `railway.json` and `Dockerfile`.

### enterprise — Variables

| Key | Value |
|---|---|
| `SPRING_DATASOURCE_URL` | `jdbc:postgresql://${{postgres.PGHOST}}:${{postgres.PGPORT}}/${{postgres.PGDATABASE}}` |
| `SPRING_DATASOURCE_USERNAME` | `${{postgres.PGUSER}}` |
| `SPRING_DATASOURCE_PASSWORD` | `${{postgres.PGPASSWORD}}` |
| `JAVA_TOOL_OPTIONS` | `-Xmx512m` |
| `SPRING_FLYWAY_ENABLED` | `true` |

Deploy it first — Flyway creates every table on boot.

### ai-platform — Variables

| Key | Value |
|---|---|
| `DATABASE_URL` | `${{postgres.DATABASE_URL}}` (the app rewrites `postgresql://` → `postgresql+psycopg://`) |
| `ENTERPRISE_BASE_URL` | `http://${{enterprise.RAILWAY_PRIVATE_DOMAIN}}:${{enterprise.PORT}}` |
| `ANTHROPIC_API_KEY` | *(paste your key)* |
| `TRACES_ENABLED` | `1` |
| `CORS_ALLOW_ORIGINS` | the portal's public URL once you have it (step 3), or `*` for the demo |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | leave default — there is no Jaeger in prod; the Postgres span store still runs |

### portal — Variables

| Key | Value |
|---|---|
| `VITE_API_BASE` | `https://${{ai-platform.RAILWAY_PUBLIC_DOMAIN}}` |

`VITE_API_BASE` is read at **build** time (Railway passes service variables as Docker
build args). If you change it, redeploy the portal.

## 3. Public domains

**Settings → Networking → Generate Domain** on **portal** and **ai-platform**. Put the
portal's domain into the ai-platform `CORS_ALLOW_ORIGINS` var and redeploy ai-platform;
the portal already points at ai-platform via the template ref above.

## 4. Seed the demo data (once)

The schema is Flyway's; the trades / SSIs / logs / corpus are the simulator's. From a
checkout of this repo with the Railway CLI linked to the project:

```bash
railway run --service ai-platform ./scripts/deploy-seed.sh
```

(or export `DATABASE_URL` from the Postgres service's Connect tab and run
`./scripts/deploy-seed.sh` directly). It waits for the schema, seeds all scenarios,
and ingests the knowledge corpus (`--fixtures CN-2026-081`). Idempotent — rerun any
time to reset.

## 5. Guardrails (do not skip)

- **Railway usage cap:** Project → **Settings → Usage** → set a hard monthly limit.
- **Anthropic spend alert:** `console.anthropic.com` → **Limits** → set a monthly cap
  and an email alert. Every investigation is ~$0.04; a runaway loop is the risk.

## 6. Smoke test

Open the portal URL:

1. **Trades → `T100245` → Investigate.** A `Finding` renders: root cause
   `COUNTERPARTY_INSTRUCTION_STALE`, `update_ssi` as a rejected alternative.
2. **Cases →** the new case → **Approve** the proposed `resubmit_settlement`
   (role `OPS_ANALYST`).
3. **Traces →** open that trace: the timeline shows `agent` / `tool` / `retrieval` /
   `policy` / `guardrail` and now an `approval` span; the synthesis span's payload
   carries the rejected `update_ssi` with *Settlement Handbook §8.4 ¶3*.
4. Evidence rows in **Trades** and the audit log in **Cases** deep-link back into the
   trace.

That is the Weekend-4 exit criteria met on a public URL.

## Redeploys

`main` is connected to each service, so a merge auto-deploys. Order still matters on a
schema change: enterprise (Flyway) before ai-platform. `EventBus` stays a no-op — no
Kafka anywhere.
