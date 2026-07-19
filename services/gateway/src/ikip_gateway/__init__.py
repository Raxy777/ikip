"""Model Gateway — the approved AI boundary and the only egress to model providers.

Responsibilities:
  - Enforce approved provider, data residency, retention, and token limits.
  - Build evidence-only prompts that separate document text (DATA) from instructions.
  - Route only over an allow-list; empty allow-list blocks all egress.
  - Treat model output as UNTRUSTED: validate schema and policy before returning.

Used both by retrieval (answer synthesis) and ingestion (bounded structured extraction);
the same untrusted-output rules apply to both paths.
"""

__all__: list[str] = []
