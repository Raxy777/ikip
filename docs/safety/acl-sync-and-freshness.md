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

- `packages/ikip-authz/filter.py::evaluate_document` — the staleness check lives here
  (currently a TODO).
- `tests/security/acl_leakage/` — must include a "revoked upstream, stale cache" scenario.
- `evaluation/suites/access_isolation/` — measures whether restricted content surfaces.

## Until resolved

`ikip-authz` treats any ACL without a fresh `synced_at` as stale and denies. Fail closed.
