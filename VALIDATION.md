# Validation results

Validated against baseline commit `6334c4748de0a398d00d2115ea4ed7ff3f4ccf0e`.

## Passing checks

| Command | Result |
|---|---|
| `uv run pytest packages services tests` | Pass: **112 passed**, with 1 third-party Starlette/httpx deprecation warning. This includes **6 fake-based migration runner tests** and API/static-contract response checks. |
| `uv run pytest tests/security` | Pass: **4 passed**. |
| `uv run python contracts/codegen/validate.py` | Pass: validated **10 JSON Schemas** against their metaschemas and parsed the static OpenAPI 3.1 document. |
| `uv run python -m evaluation.run --suite all --gate` | Pass: **4/4** deterministically named regression/security suites. These are tests, not recall/precision measurements. |
| `uv run python db/migrate.py up --dry-run` | Pass: discovered and checksummed ordered migrations `0001` and `0002`; no database was contacted. |
| `uv run ruff check ...` on all 11 touched Python files | Pass. The list included API identity/app/tests, migration runner/tests, contract validator, evaluation runner, and the prior ingestion/retrieval/statement files. |
| `uv run ruff format --check ...` on the same 11 files | Pass: all 11 formatted. |
| `cd web && npm run typecheck && npm run lint && npm run build` | Pass: TypeScript, ESLint, and Vite production build (41 modules). No frontend source was changed in this pass. |
| `git diff --check` | Pass. |
| `git apply --check ikip-prototype-completion.patch` in a detached worktree at the baseline commit | Pass; the regenerated binary patch applies mechanically to the stated baseline. |

## Contract/runtime scope

Real answered and abstained `/answer` HTTP payloads are validated in API tests against the
static Draft 2020-12 Answer schema and assert that unset `claims`, `conflicts`, or
`abstention` members are omitted rather than serialized as `null`. Tests also assert that
all three development identity headers are required at runtime and represented in both the
reviewed static OpenAPI security requirement and FastAPI-generated development docs.

The static `contracts/openapi/api.v1.yaml` and FastAPI's generated `/openapi.json` are
separate artifacts and are not claimed to be byte-equivalent. Focused tests cover the
security-header and response-contract behavior relevant to this implementation.

## PostgreSQL validation limit

The migration runner's lock/order/checksum/apply/status/commit/rollback behavior was covered
with unit fakes. Dry-run covered real migration-file discovery. **No live PostgreSQL or
pgvector service was available or used**, so advisory-lock semantics and SQL migrations
were not integration-tested against PostgreSQL; that remains a production follow-up.

## Known pre-existing repository-wide static-analysis debt

Repository-wide Ruff and mypy checks were not rerun in this follow-up because the prior
review pass had already recorded broad failures in untouched files. This validation makes
no claim that repository-wide lint, format, or typing is clean; only the explicit touched
Python file set above is clean.
