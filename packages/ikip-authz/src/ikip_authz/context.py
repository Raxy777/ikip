"""The per-request authorization context.

Constructed once by the API from the verified identity token and the user's scope, then
passed down to retrieval. Retrieval stages REQUIRE this object in their signatures, so a
search cannot be performed without an authorization context — the ordering invariant is
enforced by types, not discipline.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuthorizationContext:
    subject_id: str
    roles: frozenset[str] = field(default_factory=frozenset)
    sites: frozenset[str] = field(default_factory=frozenset)
    # Set True only after the token signature, issuer, audience, and expiry are verified.
    identity_verified: bool = False

    def require_verified(self) -> None:
        if not self.identity_verified:
            raise PermissionError("Authorization context used before identity verification.")
