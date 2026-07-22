"""Identity → AuthorizationContext boundary.

This is the ONE place an AuthorizationContext is constructed for a live request. In
production this must validate the OIDC/SAML token (signature, issuer, audience, expiry)
and derive roles/sites from verified claims before setting `identity_verified=True`.

Until that real verification exists, this module ships a DEV-ONLY header-based stub. It is
deliberately loud: it refuses to run unless IKIP_DEV_AUTH=1 is set, and it logs a warning
on every request so a dev auth path can never be mistaken for production auth.

    DEV HEADERS (dev mode only):
      X-Dev-Subject : subject id            (default "dev-user")
      X-Dev-Roles   : comma-separated roles (default empty -> scope denied)
      X-Dev-Sites   : comma-separated sites (default empty)
      X-Dev-Verified: "0" to simulate an unverified token (default verified)
"""
from __future__ import annotations

import logging
import os

from fastapi import Header, HTTPException, status

from ikip_authz import AuthorizationContext

_log = logging.getLogger("ikip.api.identity")

_DEV_FLAG = "IKIP_DEV_AUTH"


def dev_auth_enabled() -> bool:
    return os.environ.get(_DEV_FLAG) == "1"


def _split(raw: str | None) -> frozenset[str]:
    if not raw:
        return frozenset()
    return frozenset(p.strip() for p in raw.split(",") if p.strip())


def dev_identity(
    x_dev_subject: str | None = Header(default=None),
    x_dev_roles: str | None = Header(default=None),
    x_dev_sites: str | None = Header(default=None),
    x_dev_verified: str | None = Header(default=None),
) -> AuthorizationContext:
    """FastAPI dependency: construct the per-request AuthorizationContext.

    Fails closed if dev auth is not explicitly enabled — there is no real token path yet,
    so without the dev flag the API cannot authenticate anyone and says so.
    """
    if not dev_auth_enabled():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                "No production identity verification is configured. Set IKIP_DEV_AUTH=1 to "
                "use the dev header stub (NON-PRODUCTION), or wire real OIDC/SAML token "
                "validation in ikip_api.identity."
            ),
        )

    # Verified unless the caller explicitly simulates an unverified token.
    verified = x_dev_verified != "0"
    _log.warning(
        "DEV AUTH in use (NOT production): subject=%s verified=%s — token signature/issuer/"
        "audience/expiry are NOT checked.",
        x_dev_subject or "dev-user",
        verified,
    )
    return AuthorizationContext(
        subject_id=x_dev_subject or "dev-user",
        roles=_split(x_dev_roles),
        sites=_split(x_dev_sites),
        identity_verified=verified,
    )
