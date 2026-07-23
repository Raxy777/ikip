# Industrial Knowledge Intelligence Platform

**Unified Asset & Operations Brain** — an information and decision-support system that
converts governed industrial documents into searchable, evidence-grounded knowledge,
links assets to events and requirements, and answers operational questions with
claim-level citations — or safely abstains when evidence is insufficient.

> **This platform is decision-support only. It never controls equipment and never
> authorizes operation, maintenance, isolation, inspection deferral, or safety action.**

---

## Run it with Docker (recommended — works on any machine)

This is the easiest way to run the whole stack. You only need Docker installed — no
Python, Node, or database setup required.

### 1. Prerequisites

| Requirement | Version | Get it |
|---|---|---|
| **Docker Desktop** | 4.x or newer (includes Docker Engine + Compose v2) | https://www.docker.com/products/docker-desktop/ |
| Git | any recent | https://git-scm.com/downloads |

Verify Docker is installed and running:

```bash
docker --version
docker compose version
```

Both commands should print a version. If `docker compose version` errors, update
Docker Desktop — this project uses Compose **v2** (the `docker compose` subcommand, not
the old standalone `docker-compose`).

> **Windows note:** run these commands in **Git Bash**, **PowerShell**, or **WSL2**.
> Make sure Docker Desktop is open and shows "Engine running" before you start.

### 2. Get the code

```bash
git clone <repo-url>
cd ikip
```

### 3. Build and start the full stack

```bash
docker compose -f deploy/compose/docker-compose.yml up --build -d
```

- `--build` builds the API and web images from source (first run only needs this; it's
  safe to keep for later runs too).
- `-d` runs everything in the background (detached).

The **first build takes 3–5 minutes** — it downloads base images and installs
dependencies. Later starts take a few seconds.

### 4. Wait for everything to become healthy

```bash
docker compose -f deploy/compose/docker-compose.yml ps
```

Wait until the `postgres`, `api`, and `web` services show `healthy` (about 60 seconds
after the build finishes). The `create-bucket` service is a one-shot initializer — it
runs, creates the object-store bucket, and exits `0`; that is expected.

### 5. Open the app

Open **http://localhost:8080** in your browser.

You'll land on the **Workspace** tab with a question pre-filled. Submit it to get a
grounded, cited answer.

### 6. Stop the stack

```bash
# Stop containers, keep the database/object-store data
docker compose -f deploy/compose/docker-compose.yml down

# Stop AND wipe all stored data (fresh start next time)
docker compose -f deploy/compose/docker-compose.yml down -v
```

---

## What runs, and on which ports

| Service | What it is | Reachable at |
|---|---|---|
| **web** | React UI served by nginx; proxies `/api/` to the backend | http://localhost:8080 |
| **api** | FastAPI backend (retrieval + templated answer gateway) | internal only — reach it through the web proxy at `/api/` |
| **postgres** | PostgreSQL 16 + pgvector (governed store) | internal only |
| **objectstore** | MinIO, S3-compatible object storage | console: http://localhost:9001 (user `localdev` / pass `localdevsecret`) |
| **create-bucket** | One-shot job that creates the `ikip-originals` bucket, then exits | — |

The API runs in **development mode** (`IKIP_ENV=development`, `IKIP_DEV_AUTH=1`) with a
durable storage profile backed by Postgres + MinIO. Identity is supplied by
caller-controlled `X-Dev-*` headers — this is **intentionally not production auth** and
is local-only.

---

## Trying it from the command line (optional)

The web UI is the intended demo surface, but you can also hit the API directly through
the nginx proxy:

```bash
# Health check
curl http://localhost:8080/api/healthz

# Cited answer as a site-a engineer
curl -X POST http://localhost:8080/api/answer \
  -H 'content-type: application/json' \
  -H 'X-Dev-Subject: pilot' \
  -H 'X-Dev-Roles: engineer' \
  -H 'X-Dev-Sites: site-a' \
  -H 'X-Dev-Verified: 1' \
  -d '{"question":"What is the inspection interval for pump P-101?"}'
```

Endpoints: `GET /api/healthz`, `POST /api/search`, `POST /api/answer`, and
`POST /api/admin/acl/revoke` (admin role required).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Cannot connect to the Docker daemon` | Docker Desktop isn't running. Open it and wait for "Engine running". |
| `port is already allocated` (8080 or 9001) | Another process is using the port. Stop it, or edit the `ports:` mapping in `deploy/compose/docker-compose.yml`. |
| Web page won't load | Check `docker compose -f deploy/compose/docker-compose.yml ps` — `api` must be `healthy` before `web` accepts traffic. Give it ~60s. |
| Build fails on first run | Ensure you have internet access (base images are pulled from Docker Hub) and a few GB of free disk. |
| Want to see logs | `docker compose -f deploy/compose/docker-compose.yml logs -f api` (or `web`, `postgres`). |
| Want a totally clean rebuild | `docker compose -f deploy/compose/docker-compose.yml down -v` then repeat step 3. |

---

## Repository map

| Path | What lives here |
|---|---|
| `docs/` | Architecture diagrams, ADRs, safety specs, runbooks |
| `contracts/` | **Single source of truth** for schemas, events, and the API — everything else is generated from or validated against these |
| `packages/` | Shared libraries imported by every service (authz, contracts, provenance, statements, audit, observability) |
| `services/` | Deployable containers: `api`, `retrieval`, `gateway`, `ingestion` |
| `web/` | Browser application (search, cited Q&A, source viewer, review queue, admin) |
| `db/` | Governed-store migrations and non-sensitive fixtures |
| `evaluation/` | Benchmark, blind holdout, graders, suites, regression reports — **gates releases** |
| `tests/` | Cross-cutting security, integration, and end-to-end tests |
| `infra/`, `deploy/` | Infrastructure-as-code and container/compose definitions |

## Design invariants enforced by structure

1. **Authorize before retrieval.** Authorization lives in exactly one library
   (`packages/ikip-authz`) that every service imports; it is never reimplemented.
2. **Contracts are single-source.** Citation, statement-class, provenance, and ACL
   schemas live once in `contracts/` and are generated into every language.
3. **Evaluation is a product artifact**, not test scaffolding — hence its top-level
   placement. The blind holdout set is access-controlled and never enters prompts.
4. **Technology behind ports.** Swappable choices (vector store, queue, model provider)
   sit behind interfaces so a replacement is an adapter change, not a rewrite.

See `docs/architecture/` for the seven C4 / trust-boundary / sequence / lifecycle
diagrams and `docs/decisions/` for the architecture decision records.

---

## Running without Docker (local dev)

If you'd rather run the API directly with [uv](https://docs.astral.sh/uv/) instead of
Docker, the pilot runs against a self-contained in-memory corpus and ACL store plus a
deterministic templated answer gateway. Data and ACL changes disappear on restart; no
production model provider is called.

```bash
uv sync --all-packages
IKIP_ENV=development IKIP_DEV_AUTH=1 uv run uvicorn ikip_api.app:app
# caller-controlled headers are intentionally loud and local-only:
curl -H 'X-Dev-Subject: pilot' -H 'X-Dev-Roles: engineer' \
  -H 'X-Dev-Sites: site-a' -X POST http://localhost:8000/search \
  -H 'content-type: application/json' -d '{"question":"pump P-101"}'
```

Common workspace tasks are wrapped in the `justfile`:

```bash
just up        # local full stack via docker compose
just test      # unit + contract tests
just eval      # run the evaluation gate
```

Outside explicit development mode the API rejects authenticated routes because this
repository does not implement production OIDC/SAML verification. See
`IMPLEMENTATION_PLAN.md` for implemented pilot improvements and honest production gaps.
The reviewed static OpenAPI contract describes the implemented `/healthz`, `/search`,
`/answer`, and verified-admin-only `/admin/acl/revoke` endpoints. FastAPI serves separate
generated docs; see `contracts/README.md` for the distinction and alignment tests.
