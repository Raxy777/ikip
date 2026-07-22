# Prototype completion implementation plan

## Implemented in this pass

1. **Correct shape retrieval semantics**: use the `ShapeStore` contract's explicit `None`
   value for an unfiltered channel scan (rather than the literal `"*"` document ID), and
   test unfiltered, empty-scope, allow-list, limiting, and authorization behavior.
2. **Close the ACL administration gap**: require a verified identity with the explicit
   `admin` role before revocation, return a non-disclosing 403 otherwise, and test both
   denial and immediate authorized revocation.
3. **Make development identity explicit and fail closed**: require both
   `IKIP_ENV=development` and `IKIP_DEV_AUTH=1`, and require non-empty `X-Dev-Subject`,
   `X-Dev-Roles`, and `X-Dev-Sites` on every protected request. Runtime no longer invents
   `dev-user` or empty identity scope. Static OpenAPI, generated-doc assertions, README, and
   HTTP tests describe these as insecure caller-controlled development inputs—not
   production authentication.
4. **Align `/answer` serialization and its static contract**: omit unset optional fields
   from HTTP responses, tighten answered/abstained JSON Schema branches, and validate real
   answered and abstained HTTP payloads against the static schema. Document that reviewed
   static OpenAPI and FastAPI's separately generated `/openapi.json` are distinct artifacts,
   with focused alignment tests rather than a byte-equivalence claim.
5. **Make migrations operable and serialized**: add ordered, checksum-verified,
   forward-only migration execution under a transaction-scoped PostgreSQL advisory lock.
   Unit tests use fakes to cover discovery/order, empty discovery, unknown/checksum-invalid
   state, lock-before-inspection, pending-only apply, commit, status rollback, and failure
   rollback; no live PostgreSQL validation is claimed.
6. **Use honest evaluation labels**: deterministic suites are named as behavior regression,
   grounding/citation regression, abstention behavior regression, and access-isolation
   security checks. Documentation reserves recall/precision claims for future governed,
   expert-labeled benchmarks.
7. **Align public descriptions and validate the result**: document seeded stores and
   templated answering accurately, run backend/security/migration/contract/evaluation and
   frontend checks, touched-file lint/format, and `git diff --check`, and regenerate the
   binary patch from HEAD without including the patch itself.

## Production-only follow-ups (not implemented or claimed)

- Verify signed OIDC/SAML tokens (signature, issuer, audience, expiry), map groups/claims to
  roles/sites through governed policy, and disable/remove development headers in deployed
  artifacts.
- Replace seeded in-memory ACL/search/shape stores with durable transactionally consistent
  adapters; implement the pgvector shape adapter and production indexing.
- Replace `DevAnswerGateway` with an approved model gateway, evidence-only prompt isolation,
  provider egress/retention controls, audit, rate limits, and operational resilience.
- Build governed golden and blind holdout datasets with expert labels and calibrated graders;
  the pilot gate intentionally exercises deterministic correctness/security tests only.
- Add source preview, feedback/review workflow, ingestion orchestration, persistent audit,
  and other product endpoints only when their storage/governance semantics are implemented.
- Run migration integration tests against supported PostgreSQL/pgvector versions and establish
  backups, rollback/roll-forward, least-privilege roles, and deployment procedures. The
  advisory lock is unit-tested but has not been exercised against a live database here.
- Resolve repository-wide static typing/lint debt separately where doing so requires broad
  architecture changes; do not confuse touched-file cleanliness with full baseline cleanup.
