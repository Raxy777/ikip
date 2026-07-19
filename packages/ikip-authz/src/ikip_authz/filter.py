"""Deny-by-default authorization filtering.

`authorize_scope` gates the whole request. `filter_candidates` removes any retrieval
candidate the subject is not authorized to see — applied identically across exact,
lexical, semantic, and relationship results (Query-flow invariant #2).

Both functions treat a stale or unresolved ACL as a denial. This is where the
ACL-freshness design (docs/safety/acl-sync-and-freshness.md) plugs in.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol

from ikip_authz.context import AuthorizationContext
from ikip_authz.decision import AccessDecision
from ikip_authz.freshness import check_freshness


class HasAcl(Protocol):
    document_id: str
    # Populated from acl-policy.schema.json.
    sites: Sequence[str]
    roles_allowed: Sequence[str]
    synced_at: str | None
    max_staleness_seconds: int | None


def authorize_scope(ctx: AuthorizationContext) -> AccessDecision:
    """Gate the request itself before any retrieval happens."""
    ctx.require_verified()
    if not ctx.roles:
        return AccessDecision.deny("subject has no roles")
    return AccessDecision.allow()


def evaluate_document(ctx: AuthorizationContext, acl: HasAcl) -> AccessDecision:
    """Decide whether the subject may see a single document. Deny-by-default.

    Freshness is checked FIRST: a stale ACL cannot be trusted for its site/role data
    either, so a stale cache denies outright rather than evaluating scope against data
    that may no longer reflect upstream permissions (docs/safety/acl-sync-and-freshness.md).
    """
    freshness = check_freshness(acl)
    if not freshness.allowed:
        return freshness  # already a DENY with a safe, audit-only reason
    if ctx.sites and acl.sites and not (ctx.sites & set(acl.sites)):
        return AccessDecision.deny("site scope mismatch")
    if acl.roles_allowed and not (ctx.roles & set(acl.roles_allowed)):
        return AccessDecision.deny("role not permitted")
    return AccessDecision.allow()


def filter_candidates(
    ctx: AuthorizationContext,
    candidates: Iterable[tuple[HasAcl, object]],
) -> list[object]:
    """Return only the payloads whose ACL authorizes the subject.

    Applied to EVERY retrieval channel with the same rules so no channel can leak what
    another would block.
    """
    ctx.require_verified()
    return [payload for acl, payload in candidates if evaluate_document(ctx, acl).allowed]
