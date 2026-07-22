# Contracts — Single Source of Truth

Everything in this directory is **language-neutral and authoritative** for the static contract. Python models
(`packages/ikip-contracts`) and web types (`web/src/lib/generated`) are *generated* from
here. Never hand-edit generated code; edit the schema and run `just codegen`.

## Why this exists

The platform's safety guarantees depend on the citation schema, statement-class
taxonomy, provenance record, and ACL model being **byte-for-byte identical** across the
API, retrieval, gateway, ingestion, and web. If each service defined its own, the
invariants would drift silently. Keeping one definition makes drift a build failure
instead of a production leak.

## Layout

| Path | Contents |
|---|---|
| `schemas/` | Core data contracts (evidence, citation, answer, statement class, provenance, ACL, abstention) |
| `events/` | Queue job and audit event envelopes |
| `openapi/` | HTTP API surface (`api.v1.yaml`) |
| `codegen/` | Generators + validators (`generate.py`, `validate.py`) |

## Static and generated API documentation

`openapi/api.v1.yaml` is the reviewed static HTTP contract. FastAPI also serves a separate,
Pydantic-derived `/openapi.json`; it is useful for interactive development but is not
generated from the static file and is not byte-for-byte identical. Automated API tests
check required development identity headers in both documents and validate representative
answered and abstained runtime payloads against the static Answer JSON Schema.

## Rules

1. Schemas are versioned. Breaking changes require a new `$id` version and an ADR.
2. Representative runtime payloads are validated against their static schemas in automated tests.
3. A change here is not complete until `just codegen` is run and generated code committed.
