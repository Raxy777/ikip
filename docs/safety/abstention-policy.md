# Abstention Policy

**Status:** Core capability. Schema: `contracts/schemas/abstention.schema.json`.

Abstention is a measured, gated capability with its own precision/recall metrics — not a
silent failure and not an error path. The system abstains when it cannot produce a
grounded, adequately-cited answer.

## Reasons

| Reason | When |
|---|---|
| `insufficient` | No adequate authorized evidence found |
| `ambiguous` | Evidence exists but the question/asset is under-specified |
| `stale` | Only superseded/withdrawn sources apply |
| `conflicting` | Authorized sources disagree and cannot be reconciled from evidence |
| `unauthorized_scope` | The answer would require content the user may not see |
| `unavailable` | A dependency (e.g. model provider) is degraded |

## Non-leakage requirement

`unauthorized_scope` messages must not reveal that restricted content exists. Phrase as
"no accessible evidence" — identical to `insufficient` from the user's perspective.

## Residual risk (honest limit)

Retrieval, citation, and preview leakage are testable and tested
(`access_isolation_security`). **Inference-level** non-disclosure — never
leaking an inference *about* a restricted document's existence or content — cannot be
fully proven. It is treated as best-effort with named residual risk, and metrics should
not imply it is guaranteed.

## Degraded mode

On model-provider outage, prefer returning an authorized evidence list (search-only) with
reason `unavailable` over failing hard. Tie the fallback to an availability SLO.
