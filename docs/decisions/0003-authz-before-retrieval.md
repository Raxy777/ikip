# ADR-0003: Authorization happens before retrieval, in one library

**Status:** Accepted
**Date:** 2026-07-19

## Context

The system's first security invariant is that restricted text must never enter ranking,
prompts, citations, previews, summaries, logs, or inference-visible context. Filtering
the *answer* after generation is too late — the restricted content has already been
processed by the model. Filtering must happen on the *evidence*, before retrieval ranks
it.

## Decision

1. A single library, `packages/ikip-authz`, is the only place authorization is decided.
   No service reimplements it.
2. Retrieval stages take an `AuthorizationContext` as a required argument, so a search
   cannot be issued without one — the ordering invariant is enforced by function
   signatures, not by convention.
3. Authorization is deny-by-default. An unresolved or stale ACL denies.
4. Citation access is re-checked when a user opens a source, because permissions and
   document status can change after an answer is produced.

## Consequences

- The ordering invariant is testable (`tests/security/acl_leakage`) and hard to bypass.
- ACL freshness becomes the critical dependency — see
  [acl-sync-and-freshness](../safety/acl-sync-and-freshness.md).

## Revisit trigger

If a legitimate use case requires post-retrieval authorization (e.g. field-level
redaction within an authorized document), extend `ikip-authz` rather than moving
decisions into services.
