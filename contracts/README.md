# Contracts — Single Source of Truth

Everything in this directory is **language-neutral and authoritative**. Python models
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

## Rules

1. Schemas are versioned. Breaking changes require a new `$id` version and an ADR.
2. Every schema ships at least one valid example payload used by `just contracts-check`.
3. A change here is not complete until `just codegen` is run and generated code committed.
