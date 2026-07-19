# Architecture

This file is the entry point to the architecture documentation. The authoritative
diagrams live in [`docs/architecture/`](docs/architecture/) and are version-controlled
alongside the code they describe.

## Diagrams

| # | Diagram | Purpose |
|---|---|---|
| 01 | [C4 Context](docs/architecture/01-c4-context.md) | System landscape and external actors |
| 02 | [C4 Container](docs/architecture/02-c4-container.md) | Deployable units and their relationships |
| 03 | [Deployment](docs/architecture/03-deployment.md) | Logical controlled-production zones |
| 04 | [Trust Boundary](docs/architecture/04-trust-boundary.md) | Security zones and mandatory controls |
| 05 | [Query Flow (sequence)](docs/architecture/05-sequence-query-flow.md) | Authorize → retrieve → answer → cite → abstain |
| 06 | [Ingestion Pipeline](docs/architecture/06-ingestion-pipeline.md) | Untrusted document → governed knowledge |
| 07 | [Data Lifecycle](docs/architecture/07-data-lifecycle.md) | Registration → use → correction → deletion |

## Container → code mapping

Each C4 container maps to a deployable unit in the repository:

| Container (diagram 02) | Code location |
|---|---|
| Web Application | `web/` |
| Application API | `services/api/` |
| Retrieval & Answer Service | `services/retrieval/` |
| Model Gateway | `services/gateway/` |
| Ingestion Workers | `services/ingestion/` |
| Governed Knowledge Store | `db/migrations/` (schema) + `packages/ikip-contracts` (models) |
| Object Storage | provisioned in `infra/`; accessed via adapters |
| Processing Queue | provisioned in `infra/`; behind a port interface |
| Observability & Evaluation | `packages/ikip-observability` + `evaluation/` |

## Cross-cutting concerns → shared packages

| Concern | Package |
|---|---|
| Deny-by-default authorization, applicability, authority filtering | `packages/ikip-authz` |
| Schemas / models (generated from `contracts/`) | `packages/ikip-contracts` |
| Lineage, processing versions, checksums | `packages/ikip-provenance` |
| Statement classification + claim-support validation | `packages/ikip-statements` |
| Redaction + append-only audit emission | `packages/ikip-audit` |
| Structured logging, metrics, tracing | `packages/ikip-observability` |

## Known design debt

Tracked openly rather than hidden. See `docs/safety/`:

- **ACL synchronization & freshness** — how document ACLs enter the system and stay in
  sync with source systems; invalidation of stale authorization. *(highest-risk gap)*
- **Conflict & authority-ranking composition** — the answer logic that prefers approved
  applicable sources while disclosing material conflicts.
- **pgvector scale trigger** — see `docs/decisions/0002-pgvector-with-scale-trigger.md`.
