# Security Tests — Safety Gates

Separate from functional tests because these assert the platform's **safety invariants**,
not features. A failure here blocks release regardless of feature completeness.

| Suite | Asserts |
|---|---|
| `prompt_injection/` | Adversarial/hidden content in documents cannot override policy (Security invariant #2). Uses an adversarial-document corpus. |
| `acl_leakage/` | Restricted content never surfaces across sites/roles/tenants; includes a "revoked upstream, stale cache" scenario (see docs/safety/acl-sync-and-freshness.md). |
| `trust_boundary/` | The invariants drawn in docs/architecture/04-trust-boundary.md actually hold in code (authorize-before-retrieval, untrusted output validation, egress allow-list). |

Run with `just test-security`.
