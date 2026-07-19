"""ACL freshness — the staleness gate for authorization.

Implements the "fail closed" rule from docs/safety/acl-sync-and-freshness.md: a cached ACL
is only trustworthy while it is fresh relative to its source of truth. If it has never
been synced, its sync time can't be parsed, or it is older than its allowed staleness,
authorization must DENY rather than trust stale data — a user whose access was revoked
upstream must stop being served here within the staleness bound.

This is deliberately conservative because it is the highest-risk leak path:
  - No `synced_at`            -> deny (never synced).
  - Unparseable `synced_at`   -> deny (can't establish freshness).
  - No `max_staleness_seconds`-> apply DEFAULT_MAX_STALENESS_SECONDS, never "unbounded".
  - age > allowed staleness   -> deny (stale; force upstream re-sync/re-check).

The default bound is intentionally short. It is a safety fallback, not the intended
per-document policy — real values come from `acl-policy.schema.json::max_staleness_seconds`
once the sync mechanism (ADR / safety spec) is finalized.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from ikip_authz.decision import AccessDecision

# Conservative fallback when an ACL does not carry its own staleness bound. Chosen to fail
# closed quickly; tune per source system when the sync design lands.
DEFAULT_MAX_STALENESS_SECONDS = 3600

# Tolerance for clock skew between this service and the source of truth, so a just-synced
# ACL whose timestamp is marginally in the future is not treated as an error.
_CLOCK_SKEW_TOLERANCE_SECONDS = 60


class HasFreshness(Protocol):
    synced_at: object  # str (ISO 8601) | datetime | None
    max_staleness_seconds: int | None


def _to_datetime(value: object) -> datetime | None:
    """Normalize a `synced_at` value to an aware UTC datetime, or None if unusable."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            # Python 3.12 fromisoformat accepts a trailing 'Z'.
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None
    else:
        return None
    # Treat naive timestamps as UTC rather than guessing a local zone.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def check_freshness(acl: HasFreshness, now: datetime | None = None) -> AccessDecision:
    """Return ALLOW only if the ACL is fresh enough to be trusted; otherwise DENY.

    `now` is injectable for testing; it defaults to the current UTC time.
    """
    now = now or datetime.now(timezone.utc)

    synced = _to_datetime(getattr(acl, "synced_at", None))
    if synced is None:
        return AccessDecision.deny("acl not synced from source of truth (fail closed)")

    max_stale = acl.max_staleness_seconds
    if max_stale is None:
        max_stale = DEFAULT_MAX_STALENESS_SECONDS

    age_seconds = (now - synced).total_seconds()
    # A timestamp slightly in the future (clock skew) is fresh, not stale.
    if age_seconds < -_CLOCK_SKEW_TOLERANCE_SECONDS:
        return AccessDecision.deny("acl synced_at is implausibly in the future")
    if age_seconds > max_stale:
        return AccessDecision.deny(
            f"acl stale: age {age_seconds:.0f}s exceeds max {max_stale}s"
        )
    return AccessDecision.allow("acl fresh")
