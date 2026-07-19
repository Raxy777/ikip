"""Application API — authenticates requests, enforces authorization, orchestrates.

Validates the identity token (signature, issuer, audience, expiry), maps roles, builds
the AuthorizationContext, and orchestrates search/answer/governance/feedback/correction
and audit events. Object-level authorization decisions delegate to ikip-authz; nothing
here reimplements authorization.
"""

__all__: list[str] = []
