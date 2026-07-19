# ADR-0001: Monorepo with shared contract packages

**Status:** Accepted
**Date:** 2026-07-19

## Context

The platform's safety guarantees depend on the citation schema, statement-class
taxonomy, provenance record, and ACL model being identical across the API, retrieval,
gateway, ingestion, and web. Independent repositories would let these definitions drift.

## Decision

Use a single repository. Shared definitions live in `contracts/` (language-neutral) and
`packages/` (Python libraries). Services and the web app consume generated code; they
never redefine a shared shape.

## Consequences

- Drift between a schema and its consumers becomes a build/CI failure, not a runtime leak.
- One versioned history for architecture, code, and evaluation.
- Requires workspace tooling (uv workspace) and a codegen step (`just codegen`).

## Revisit trigger

If the web and backend teams diverge enough that build coupling causes more friction than
the drift it prevents, reconsider splitting `web/` into its own repository while keeping
generated contract types published as a package.
