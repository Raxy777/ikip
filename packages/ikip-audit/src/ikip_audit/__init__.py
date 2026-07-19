"""ikip-audit — the one place redaction and audit emission live.

Query-flow invariant #8: the audit record uses governed identifiers and redaction rules;
unnecessary document content and secrets are never logged. Centralizing this means no
service can accidentally log restricted content — they emit through here.
"""

__all__: list[str] = []
