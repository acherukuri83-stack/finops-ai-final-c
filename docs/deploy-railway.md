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
| `EVENTS_ENABLED` | `1` (Phase D — runs the in-process outbox consumer; `EVENT_BUS` defaults to `outbox`, no broker needed) |
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

The schema is Flyway's (created when `enterprise` boots). The trades / SSIs / logs are
the simulator's; the knowledge corpus is `knowledge.ingest`. Two parts because they need
different things.

**a) Scenario data — needs a repo checkout + a reachable Postgres.** Railway's Postgres
is private by default, so `railway run` (which injects the *internal* URL) can't reach it
from your laptop. Enable the public proxy: **Postgres → Settings → Networking → TCP
Proxy → port 5432**, then copy `DATABASE_PUBLIC_URL` from the Postgres **Variables** tab
and run:

```bash
DATABASE_URL='<DATABASE_PUBLIC_URL>' ./scripts/deploy-seed.sh
```

It waits for the schema, seeds all scenarios, and — if your machine can reach Hugging
Face — also ingests the corpus. Idempotent. Turn the TCP proxy back off afterwards if
you want the DB locked down.

**b) Knowledge corpus — needs the embedding model.** It is baked into the `ai-platform`
image (`FASTEMBED_CACHE_PATH`), so the reliable path is to ingest *inside* the container:

```bash
railway ssh --service ai-platform
# then, in the container:
uv run python -m knowledge.ingest --fixtures CN-2026-081
```

(If step (a) already ingested successfully because your machine has Hugging Face access,
skip (b).) Verify: `curl https://<ai-platform-domain>/knowledge?q=counterparty+ssi` returns hits.

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
5. **Phase D:** from a machine with the repo + `DATABASE_PUBLIC_URL` (TCP proxy, step 4):
   `make emit TRADE=T100245` — within a few seconds a **Cases** row appears with source
   `event`, no user prompt, its own investigation trace (root span `event:failed`). Run it
   again → the same case gets a "repeat FAILED event" audit line, no second case. Or
   `POST /events` with an `Event` body against the public API.

That is the Weekend-4 + Phase-D exit criteria met on a public URL.

## Redeploys

`main` is connected to each service, so a merge auto-deploys. Order still matters on a
schema change: enterprise (Flyway) before ai-platform. The Phase-D consumer runs in-process
on ai-platform when `EVENTS_ENABLED=1` (Postgres-outbox; no Kafka anywhere).
