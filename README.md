# Industrial Knowledge Intelligence Platform

**Unified Asset & Operations Brain** — an information and decision-support system that
converts governed industrial documents into searchable, evidence-grounded knowledge,
links assets to events and requirements, and answers operational questions with
claim-level citations — or safely abstains when evidence is insufficient.

> **This platform is decision-support only. It never controls equipment and never
> authorizes operation, maintenance, isolation, inspection deferral, or safety action.**

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

## Getting started

```bash
just up        # local full stack (postgres+pgvector, object store, queue)
just test      # unit + contract tests
just eval      # run the evaluation gate
```

See `docs/architecture/` for the seven C4 / trust-boundary / sequence / lifecycle
diagrams and `docs/decisions/` for the architecture decision records.

## Runnable pilot scope

The checked-in API is a self-contained development pilot: it uses a small synthetic,
in-memory corpus and ACL store plus a deterministic templated answer gateway. Data and ACL
changes disappear when the process restarts; no production model provider is called.

```bash
uv sync --all-packages
IKIP_ENV=development IKIP_DEV_AUTH=1 uv run uvicorn ikip_api.app:app
# caller-controlled headers are intentionally loud and local-only:
curl -H 'X-Dev-Subject: pilot' -H 'X-Dev-Roles: engineer' \
  -H 'X-Dev-Sites: site-a' -X POST http://localhost:8000/search \
  -H 'content-type: application/json' -d '{"question":"pump P-101"}'
```

Outside explicit development mode the API rejects authenticated routes because this
repository does not implement production OIDC/SAML verification. See
`IMPLEMENTATION_PLAN.md` for implemented pilot improvements and honest production gaps.
The reviewed static OpenAPI contract describes the implemented `/healthz`, `/search`, `/answer`, and
verified-admin-only `/admin/acl/revoke` endpoints. FastAPI serves separate generated docs;
see `contracts/README.md` for the distinction and alignment tests.
