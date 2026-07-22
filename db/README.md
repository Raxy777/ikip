# Governed Knowledge Store

Forward-only SQL migrations target PostgreSQL 16 with pgvector. Apply them with `just
migrate`, or inspect with `uv run python db/migrate.py status`. The runner applies ordered
files transactionally under a PostgreSQL transaction-scoped advisory lock and records their
SHA-256 checksums in `schema_migration`; modifying
an applied migration fails closed.

Configuration accepts `IKIP_DATABASE_URL`, or the `IKIP_DB_HOST`, `IKIP_DB_PORT`,
`IKIP_DB_NAME`, `IKIP_DB_USER`, and `IKIP_DB_PASSWORD` variables in `.env.example`. Use
`uv run python db/migrate.py up --dry-run` to validate discovery without a database.

The local compose PostgreSQL image includes pgvector. This pilot runner is not a production
migration service: backups, least-privilege migration roles, supported
version integration tests, and operational roll-forward procedures remain required.
