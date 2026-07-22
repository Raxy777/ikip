"""Development-only identity boundary.

There is no production token verifier in this prototype. Caller-controlled identity is
available only when *both* ``IKIP_ENV=development`` and ``IKIP_DEV_AUTH=1`` are set. Every
protected request must provide subject, roles, and sites explicitly; this module never
synthesizes an identity. Any non-development environment fails closed.
"""

from __future__ import annotations

import logging
import os
from typing import Annotated

from fastapi import Header, HTTPException, status
from ikip_authz import AuthorizationContext

_log = logging.getLogger("ikip.api.identity")
_DEVELOPMENT = "development"


def dev_auth_enabled() -> bool:
    """Return true only for an explicit, two-factor development configuration."""
    return (
        os.environ.get("IKIP_ENV", "").lower() == _DEVELOPMENT
        and os.environ.get("IKIP_DEV_AUTH") == "1"
    )


def _split(raw: str) -> frozenset[str]:
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def development_identity(
    x_dev_subject: Annotated[str, Header(min_length=1)],
    x_dev_roles: Annotated[str, Header(min_length=1)],
    x_dev_sites: Annotated[str, Header(min_length=1)],
    x_dev_verified: Annotated[str | None, Header()] = None,
) -> AuthorizationContext:
    """Construct an explicitly supplied, caller-controlled development context."""
    if not dev_auth_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is unavailable: no production identity verifier is configured.",
        )

    subject = x_dev_subject.strip()
    roles = _split(x_dev_roles)
    sites = _split(x_dev_sites)
    if not subject or not roles or not sites:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Development subject, roles, and sites must each contain a value.",
        )

    verified = x_dev_verified != "0"
    _log.warning(
        "INSECURE DEVELOPMENT AUTH: caller-controlled identity subject=%s verified=%s",
        subject,
        verified,
    )
    return AuthorizationContext(
        subject_id=subject,
        roles=roles,
        sites=sites,
        identity_verified=verified,
    )


# Backwards-compatible import for local callers. It retains the same strict environment gate.
dev_identity = development_identity

__all__ = ["dev_auth_enabled", "development_identity"]
