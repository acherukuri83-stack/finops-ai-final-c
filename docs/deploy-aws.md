# Deploying to AWS

The counterpart to `deploy-railway.md`. Same four workloads, mapped onto AWS
primitives. The register is the same: a checklist you can follow in the console or
with the CLI, honest about what is optional.

| Workload | What it is | AWS |
|---|---|---|
| **postgres** | one PostgreSQL 16 + `pgvector` — enterprise's Flyway schema, the platform-tier tables (`cases`, `outbox_events`, the finance / wire stores), and `knowledge_chunks` | **RDS for PostgreSQL 16**, `vector` extension enabled |
| **enterprise** | Java 21 / Spring Boot, plain REST + JPA, 512 MB, owns the schema (Flyway on boot) | **ECS Fargate** service, private, behind the internal ALB |
| **ai-platform** | one Python process — FastAPI + `agent_core` + the MCP servers in-process (ADR-0005); the Phase D outbox consumer runs in its lifespan | **ECS Fargate** service, public, behind the ALB |
| **portal** | React + Vite — a static build | **S3 + CloudFront** (primary) or an ECS Fargate + Caddy service (uniform) |
| events | the **Postgres-outbox** bus (default, no broker) or Kafka | nothing extra; **MSK** only if `EVENT_BUS=kafka` |
| traces | spans persisted to Postgres for the Trace screen; no Jaeger in prod | optional **ADOT** sidecar → X-Ray / CloudWatch |

Nothing in the app is AWS-specific — it is the same containers and the same env
vars as Railway. This doc is the wiring.

---

## 0. Prerequisites

- An AWS account, the AWS CLI v2, and Docker.
- The repo pushed to GitHub (for the CI deploy in §12).
- An Anthropic API key (`console.anthropic.com`) — it goes in Secrets Manager, never in an image or a task definition.
- A region. This doc uses `us-east-1`; substitute throughout.
- A hosted zone + an ACM certificate in that region if you want a custom domain (optional — CloudFront and the ALB both hand out a default hostname).

## 1. Network

A minimal VPC is enough. If you already run one, reuse it.

```
VPC 10.0.0.0/16
  public  subnets  (2 AZs)  -> Internet Gateway            : the ALB, the NAT gateway
  private subnets  (2 AZs)  -> NAT gateway                  : the ECS tasks, RDS
```

- **ai-platform tasks need outbound HTTPS to `api.anthropic.com`** — that is public internet, so the private subnets route `0.0.0.0/0` at a **NAT gateway**. The fastembed model is baked into the image (`FASTEMBED_CACHE_PATH`), so there is no Hugging Face egress at runtime.
- Add S3 and ECR **gateway/interface VPC endpoints** to keep image pulls and any S3 traffic off the NAT.

Security groups:

| SG | Inbound | Notes |
|---|---|---|
| `alb-sg` | 443 from `0.0.0.0/0` (and 80 → redirect) | |
| `ai-platform-sg` | 8000 from `alb-sg` | |
| `enterprise-sg` | 8080 from `ai-platform-sg` (and `alb-sg` if you expose `/health` checks there) | never from the internet |
| `rds-sg` | 5432 from `ai-platform-sg` and `enterprise-sg` | plus a **temporary** rule from your bastion / CloudShell for the one-off seed (§9) |

## 2. Images → ECR

Three repositories, one image each.

```bash
aws ecr create-repository --repository-name finops/enterprise
aws ecr create-repository --repository-name finops/ai-platform
aws ecr create-repository --repository-name finops/portal   # only if you run the portal on ECS

ACCT=$(aws sts get-caller-identity --query Account --output text)
REG=$ACCT.dkr.ecr.us-east-1.amazonaws.com
aws ecr get-login-password | docker login --username AWS --password-stdin "$REG"

docker build -t "$REG/finops/enterprise:latest" ./enterprise
docker build -t "$REG/finops/ai-platform:latest" ./ai-platform
docker push "$REG/finops/enterprise:latest"
docker push "$REG/finops/ai-platform:latest"
```

The `ai-platform` build runs `fastembed` once to cache the ONNX model into the
image — the build host needs Hugging Face reachable; runtime does not.

For the portal, prefer the **S3 build** (§7) — no image. If you want it on ECS,
build the `build`-then-`caddy` stage with `--build-arg VITE_API_BASE=<the ALB /
CloudFront URL of ai-platform>` (Vite inlines it at build time) and push
`finops/portal`.

## 3. RDS PostgreSQL + pgvector

- **RDS → Create database → PostgreSQL 16**, one instance (`db.t4g.small` is plenty for the demo), in the private subnets, `rds-sg`, storage-encrypted, automated backups on.
- Master user `finops`, DB name `finops`. Put the generated password straight into Secrets Manager (§4) — do not keep it.
- After it is available, connect once (psql from CloudShell / a bastion in the VPC) and:

  ```sql
  create extension if not exists vector;
  ```

  RDS PG 16 ships `pgvector`; the `rds_superuser` role (your master user) may create it.

## 4. Secrets Manager

Two secrets, referenced by the task definitions — never inlined.

| Secret | Contents |
|---|---|
| `finops/db` | `{"DATABASE_URL":"postgresql://finops:<pw>@<rds-endpoint>:5432/finops"}` — the app rewrites `postgresql://` → `postgresql+psycopg://` itself |
| `finops/anthropic` | `{"ANTHROPIC_API_KEY":"sk-ant-..."}` |

Give the ECS **task execution role** `secretsmanager:GetSecretValue` on both, and
the KMS key `kms:Decrypt`.

## 5. ECS cluster + roles

- **ECS → Create cluster → Fargate**, name `finops`.
- **Task execution role** (`ecsTaskExecutionRole`): `AmazonECSTaskExecutionRolePolicy` + the Secrets Manager / KMS grants from §4 + `logs:CreateLogGroup`.
- **Task role** for `ai-platform`: it needs nothing AWS-side unless you add the ADOT sidecar (then `xray:PutTraceSegments`, `xray:PutTelemetryRecords`) or run the seed as an ECS task (then it needs the DB secret too — it already has it).
- One CloudWatch log group per service: `/ecs/finops/enterprise`, `/ecs/finops/ai-platform`.

## 6. ECS services — enterprise, then ai-platform

Deploy **enterprise first** — Flyway creates every table on boot; `ai-platform`
expects the schema to exist.

### enterprise — task definition

| | |
|---|---|
| image | `$REG/finops/enterprise:latest` |
| cpu / mem | 512 / 1024 |
| port | 8080 |
| env | `SPRING_FLYWAY_ENABLED=true`, `JAVA_TOOL_OPTIONS=-Xmx512m` |
| env from JDBC | `SPRING_DATASOURCE_URL=jdbc:postgresql://<rds-endpoint>:5432/finops`, `SPRING_DATASOURCE_USERNAME=finops` |
| secret | `SPRING_DATASOURCE_PASSWORD` ← `finops/db` (store the raw password as a second key in that secret, or a separate `finops/db-password` secret — Spring wants the bare value, not a URL) |
| health check | `CMD-SHELL curl -f http://localhost:8080/health || exit 1` |

Service: 1 task, private subnets, `enterprise-sg`, **no** public IP, register with
the ALB's `enterprise` target group (internal listener rule, §8) so `ai-platform`
resolves it by a stable name.

### ai-platform — task definition

| | |
|---|---|
| image | `$REG/finops/ai-platform:latest` |
| cpu / mem | 512 / 1024 (bump mem to 2048 if you keep the fastembed model resident) |
| port | 8000 |
| env | `ENTERPRISE_BASE_URL=http://<enterprise ALB name>:8080`, `TRACES_ENABLED=1`, `EVENTS_ENABLED=1` (`EVENT_BUS` defaults to `outbox` — no broker), `CORS_ALLOW_ORIGINS=<portal URL>` (or `*` for the demo), `FASTEMBED_CACHE_PATH=/opt/fastembed-cache`, optionally `FINOPS_STRONG_MODEL` / `FINOPS_CHEAP_MODEL` |
| secrets | `DATABASE_URL` ← `finops/db`, `ANTHROPIC_API_KEY` ← `finops/anthropic` |
| health check | `CMD-SHELL curl -f http://localhost:8000/health || exit 1` |

Service: 1 task (the Phase D consumer runs in-process — do **not** scale this to
N tasks without moving the consumer out; ADR-0005), private subnets,
`ai-platform-sg`, register with the ALB's public `ai-platform` target group.

> **Splitting the MCP servers** (`AI_PLATFORM_SPLIT=1`) is a scale path, not the
> default: it turns each server into its own ECS service and the app into an
> HTTP client of them. The demo runs everything in one task.

## 7. Portal — S3 + CloudFront

```bash
cd portal
VITE_API_BASE="https://<ai-platform public hostname>" npm ci && npm run build
aws s3 mb s3://finops-portal-<acct>
aws s3 sync dist/ s3://finops-portal-<acct> --delete
```

- **CloudFront distribution** → origin the S3 bucket (OAC, bucket stays private), default root object `index.html`, and a **custom error response** mapping 403/404 → `/index.html` 200 (the SPA router).
- `VITE_API_BASE` is inlined at build time. Change it → rebuild + `s3 sync` + a CloudFront invalidation (`/*`).
- Put the CloudFront domain into `ai-platform`'s `CORS_ALLOW_ORIGINS` and redeploy that service.

(Alternative: run `finops/portal` on ECS Fargate behind the same ALB — same as
Railway. Keeps one deploy mechanism; costs a running task.)

## 8. ALB

One **Application Load Balancer** in the public subnets, `alb-sg`.

| Listener | Rule | Target group |
|---|---|---|
| 443 (ACM cert) | default | `ai-platform` (IP target, port 8000, health `/health`) |
| 80 | redirect → 443 | |
| internal (a second internal ALB, or the same one on a private listener) | host/path for enterprise | `enterprise` (IP target, port 8080, health `/health`) |

Simplest: **two ALBs** — one internet-facing for `ai-platform`, one internal for
`enterprise` — and point `ENTERPRISE_BASE_URL` at the internal ALB's DNS name.
Cloud Map / ECS Service Connect works too if you prefer service discovery.

## 9. Seed the data (once)

Same two parts as Railway — scenario data and the corpus — because they need
different things.

**a) Scenario data.** `scripts/deploy-seed.sh` needs a repo checkout and a
reachable Postgres. From **CloudShell** or a bastion in the VPC, with a
**temporary** `rds-sg` rule allowing your source:

```bash
git clone <repo> && cd finops-ai-final-c
DATABASE_URL='postgresql://finops:<pw>@<rds-endpoint>:5432/finops' ./scripts/deploy-seed.sh
```

It waits for the Flyway schema, seeds every scenario (baseline + Sc. 1–16, 30 —
including the wire scenarios), and — if the machine can reach Hugging Face —
ingests the corpus too. Idempotent. **Remove the temporary SG rule afterwards.**

Or run it as a one-off **ECS RunTask** using the `ai-platform` image with an
overridden command — but that image does not carry `simulator/`, so the
checkout-in-CloudShell path is simpler for a first deploy. A dedicated `seed`
image (repo + `uv`) is the clean long-term answer.

**b) Corpus.** The embedding model is in the `ai-platform` image, so the reliable
path is to ingest inside the running task:

```bash
aws ecs execute-command --cluster finops --task <task-id> --container ai-platform \
  --interactive --command "uv run python -m knowledge.ingest --fixtures CN-2026-081"
```

(needs ECS Exec enabled on the service). Skip if step (a) already ingested.
Verify: `curl https://<ai-platform-host>/knowledge?q=counterparty+ssi` returns hits.

## 10. Events

Nothing to do — `EVENTS_ENABLED=1` runs the Postgres-outbox consumer in the
`ai-platform` task, polling `outbox_events`. `make emit TRADE=…` /
`make emit WIRE=…` (or `POST /events`) against the deployed DB / API works exactly
as local.

**MSK** is only for `EVENT_BUS=kafka`: create an MSK Serverless cluster, put its
bootstrap string in `KAFKA_BOOTSTRAP`, set `EVENT_BUS=kafka`, and give the task's
SG egress to the cluster. The consumer code is identical; the outbox path is the
tested one and needs no broker.

## 11. Observability (optional)

No Jaeger in prod; the Postgres span store backs the Trace screen regardless
(`TRACES_ENABLED=1`). To also ship spans to AWS: add an **ADOT collector
sidecar** to the `ai-platform` task, set `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318`
(the default), and configure the collector to export to **X-Ray** (traces) and
**CloudWatch** (metrics/logs). Grant the task role the X-Ray write actions.

## 12. Guardrails (do not skip)

- **AWS Budgets** — a monthly cost budget with an alert. Fargate + RDS + NAT + ALB for this demo is ~\$70–110/month left running; sleep the ECS services (desired count 0) between demos.
- **Anthropic spend cap** — `console.anthropic.com` → Limits → a monthly cap + email alert. Every investigation is ~\$0.04; a runaway loop is the real risk.

## 13. Smoke test

Open the CloudFront URL — same script as `deploy-railway.md` §6:

1. **Trades → `T100245` → Investigate** → a `Finding`: root cause `COUNTERPARTY_INSTRUCTION_STALE`, `update_ssi` rejected.
2. **Cases →** the case → **Approve** the `resubmit_settlement` (role `OPS_ANALYST`).
3. **Traces →** that trace shows `agent` / `tool` / `retrieval` / `policy` / `guardrail` / `approval` spans; the synthesis payload carries the rejected `update_ssi` with *Settlement Handbook §8.4 ¶3*.
4. **Prime Finance → Wire →** `W300917` → Investigate → `route_to_reviewer` + a cutoff warning; then **Wire Review →** release it (role `WIRE_REVIEWER`).
5. **Events:** `make emit TRADE=T100245` from CloudShell (temporary `rds-sg` rule) → a **Cases** row appears with source `event`, its own trace (root span `event:failed`); run again → a "repeat FAILED event" audit line, no second case. `make emit WIRE=W300917 DEADLINE=<+30m>` → a wire case at `HIGH`.

## 14. As code

This checklist is the manual path. For a repeatable one:

- **AWS Copilot** (`copilot init` per service) covers ECS + ALB + ECR + roles + log groups with almost no YAML; add RDS as a Copilot "database" addon or import an existing one. Closest to the Railway experience.
- **Terraform / CDK** if you want the VPC, RDS, MSK, and CloudFront in the same state. Module boundaries: `network`, `data` (RDS + the `vector` extension via a `null_resource` / a Lambda), `ecs` (cluster + the two services + ALBs), `portal` (S3 + CloudFront), `secrets`.

Whichever, the app config surface is the eight `ai-platform` env vars + the two
enterprise datasource vars + the two secrets — nothing else.

## 15. Redeploys / CI

A GitHub Actions workflow on `main`:

1. build + push `finops/enterprise` and `finops/ai-platform` to ECR (tag `:$GITHUB_SHA`);
2. `aws ecs update-service --force-new-deployment` for **enterprise first**, wait for it to stabilise (Flyway runs on the new task), then `ai-platform`;
3. `npm run build` the portal with the prod `VITE_API_BASE`, `s3 sync`, CloudFront invalidation.

Order matters only on a schema change (enterprise before ai-platform); otherwise
the two are independent. The Phase D consumer comes up with the new `ai-platform`
task — no separate worker to roll.
