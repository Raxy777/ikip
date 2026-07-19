# Task runner for the Industrial Knowledge Intelligence Platform.
# Run `just` with no arguments to list recipes.

default:
    @just --list

# Install all workspace dependencies.
install:
    uv sync --all-packages

# Lint + format check + type check.
lint:
    uv run ruff check .
    uv run ruff format --check .
    uv run mypy packages services

# Auto-fix formatting and lint issues.
fmt:
    uv run ruff format .
    uv run ruff check --fix .

# Regenerate models/types from contracts/ (Python + web).
codegen:
    uv run python contracts/codegen/generate.py

# Validate all example payloads against contracts/schemas.
contracts-check:
    uv run python contracts/codegen/validate.py

# Unit + contract tests across the workspace.
test:
    uv run pytest packages services

# Security safety-gate tests (prompt injection, ACL leakage, boundaries).
test-security:
    uv run pytest tests/security

# Full evaluation gate. Fails the build on regression.
eval:
    uv run python -m evaluation.run --suite all --gate

# Apply database migrations against the local governed store.
migrate:
    uv run python db/migrate.py up

# Bring up the local full stack (postgres+pgvector, object store, queue).
up:
    docker compose -f deploy/compose/docker-compose.yml up -d

# Tear down the local stack.
down:
    docker compose -f deploy/compose/docker-compose.yml down

# CI aggregate: everything that must pass before merge.
ci: lint contracts-check test test-security eval
