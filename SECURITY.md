# Security

The authoritative security model is the [Trust Boundary Diagram](docs/architecture/04-trust-boundary.md).
This file summarizes the non-negotiable invariants and points to the threat model.

## Non-negotiable security invariants

1. **Authorize before retrieval.** Restricted text must not enter ranking, prompts,
   citations, previews, summaries, logs, or inference-visible context.
2. **Treat documents as data, never instructions.** Embedded prompts, hidden text,
   links, or adversarial passages cannot override platform policy.
3. **Treat model output as untrusted.** Only validated, evidence-supported claims may be
   shown; otherwise disclose conflict or abstain.
4. **Preserve provenance.** Originals are never overwritten; every derivative records its
   source coordinates and processing versions.
5. **Separate privileges.** End users, reviewers, ingestion workers, application
   services, the model gateway, and administrators receive distinct scoped identities.
6. **Minimize disclosure.** Only necessary authorized evidence crosses the model
   boundary; telemetry and errors redact secrets and sensitive content.
7. **Make corrections and deletion complete.** Changes propagate to facts, links,
   embeddings, indexes, caches, previews, histories, and backups per approved policy.

## Where invariants are enforced in code

| Invariant | Enforced by |
|---|---|
| Authorize before retrieval | `packages/ikip-authz`, called in `services/retrieval/.../pipeline/authorize.py` before any search stage |
| Documents as data | `services/gateway` prompt isolation; `services/ingestion` sandboxing |
| Model output untrusted | `services/gateway` schema/citation/policy validation before return |
| Provenance | `packages/ikip-provenance` |
| Redaction / minimal disclosure | `packages/ikip-audit` |
| Complete deletion | deletion job (`contracts/events/deletion-job.schema.json`) + `docs/runbooks/deletion-verification.md` |

## Threat model

See the threat-scenario coverage in the trust-boundary diagram and the adversarial test
corpus under `tests/security/`. Verifiable isolation is tested in
`evaluation/suites/access_isolation/`. Note that **inference-level** non-disclosure is
best-effort and is documented as residual risk — see `docs/safety/abstention-policy.md`.

## Reporting

Do not open public issues for vulnerabilities. See internal disclosure process (TODO:
fill in contact before first external deployment).
