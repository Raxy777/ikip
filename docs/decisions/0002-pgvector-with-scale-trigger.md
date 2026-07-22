# ADR-0002: pgvector for the focused release, behind a port, with an explicit scale trigger

**Status:** Accepted
**Date:** 2026-07-19

## Context

The architecture commits to PostgreSQL + pgvector for the governed knowledge store,
while corpus size, page volume, query load, and latency ceilings are deferred to
"before architecture approval." Committing to a vector technology before those numbers
are known is a risk. The alignment review flagged that the diagrams harden this choice
without recording when to revisit it — unlike the processing queue, which the C4 diagram
correctly marks as implementation-neutral.

## Decision

Use pgvector for the focused core release. Keep it **behind a `VectorStore` port**
(`services/retrieval/src/ikip_retrieval/ports/vector_store.py`) so replacement is an
adapter change, not a rewrite. Co-locating vectors with governed metadata in one
transactional store keeps ACL filtering and vector search consistent, which is worth
more than raw ANN performance at the focused-release scale.

## Revisit trigger (make this concrete before GA)

Re-evaluate the vector store when **any** of the following is projected within two
quarters (fill in real numbers once §9.3 scale figures exist):

- Indexed chunk count exceeds **[TBD, e.g. 5–10M]**.
- p95 retrieval latency under production filters exceeds **[TBD, e.g. 300 ms]**.
- ACL-filtered ANN recall drops below a future governed, expert-labeled benchmark floor.

At that point, evaluate a dedicated vector engine while preserving the same port and the
same authorization-before-retrieval guarantee.

## Consequences

- Simpler operations and consistent ACL filtering now.
- A clear, measurable line for when the decision must be reopened.
