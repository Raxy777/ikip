# ACL Synchronization & Freshness (HIGHEST-RISK OPEN DESIGN)

**Status:** Open design problem. This is where authorization leaks are most likely.

## Problem

Document-level ACLs are the backbone of the platform, but the plan and diagrams do not
specify **where ACLs come from** or **how they stay in sync** with the source systems
(CMMS / EDMS / QMS) that actually own permissions. "Stale authorization cache" is listed
as a threat with no invalidation mechanism. A user whose access was revoked upstream must
not continue to retrieve or cite content here.

## Design questions to resolve

1. **Source of truth.** Which upstream system owns each document's ACL? Recorded as
   `source_of_truth` in `acl-policy.schema.json`.
2. **Sync mechanism.** Push (webhook/event from source) or pull (periodic reconciliation)
   or both? Push minimizes staleness; pull bounds worst-case drift if push fails.
3. **Staleness policy.** `max_staleness_seconds` in the ACL schema: once exceeded,
   `ikip-authz` must deny or force a live re-check rather than trust the cached ACL.
4. **Runtime re-check.** The query flow already re-checks authorization when a citation
   is opened (sequence step 68). Decide whether high-sensitivity queries also re-check at
   answer time.
5. **Revocation propagation.** When upstream access is revoked, what is the maximum
   acceptable window before this platform stops serving that content? This is an SLO.

## Enforcement points

- `packages/ikip-authz/freshness.py::check_freshness` — the staleness gate. Fail-closed
  rules: no `synced_at` denies, unparseable `synced_at` denies, missing
  `max_staleness_seconds` falls back to `DEFAULT_MAX_STALENESS_SECONDS` (never unbounded),
  and age beyond the bound denies. Small future skew is tolerated; implausible future
  timestamps deny.
- `packages/ikip-authz/filter.py::evaluate_document` — calls `check_freshness` FIRST, so a
  stale ACL denies before its (untrustworthy) site/role data is ever evaluated.
- `tests/security/acl_leakage/test_stale_acl_does_not_leak.py` — the "revoked upstream,
  stale cache" scenario, at both the filter and full-pipeline (`run_query`) level.
- `evaluation/suites/access_isolation/` — measures whether restricted content surfaces.

## Implemented so far (fail closed)

`ikip-authz` treats any ACL that cannot be proven fresh as stale and denies (freshness
gate, above).

The sync layer (`packages/ikip-authz/sync.py`) is the one place `synced_at` is written:
- `reconcile(source, store)` — PULL. Makes the local store match the upstream current set:
  upserts current ACLs (re-stamping `synced_at`) and DELETES any document no longer present
  upstream. Deletion is the revocation path.
- `apply_event(store, event)` — PUSH. Applies a single UPSERT or REVOKE (webhook) for low
  latency. REVOKE deletes.
- `synced_at` is always stamped with reconcile/apply time, never a timestamp the source
  supplied, so a source can't extend an ACL's trusted life by reporting a stale time.

Sync and freshness are defense-in-depth for the same leak: if a push REVOKE is missed, the
freshness gate still fails the ACL closed once `max_staleness_seconds` is exceeded.

Still open: the concrete `AclSource` adapters per source system (CMMS/EDMS/QMS), the
production `AclStore` (only `InMemoryAclStore` exists), the reconcile schedule and the
revocation-window SLO, and whether high-sensitivity queries re-check at answer time. The
`DEFAULT_MAX_STALENESS_SECONDS` fallback should be replaced by per-document
`max_staleness_seconds` from the source systems.
