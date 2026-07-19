"""Deny-by-default is the contract. These tests assert the failure modes, not just success."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from ikip_authz import AuthorizationContext, authorize_scope, filter_candidates
from ikip_authz.filter import evaluate_document


@dataclass
class FakeAcl:
    document_id: str
    sites: tuple[str, ...] = ()
    roles_allowed: tuple[str, ...] = ()
    # Default to freshly synced so scope tests isolate site/role, not staleness.
    synced_at: str | None = None
    max_staleness_seconds: int | None = 3600


def _fresh() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ctx(**kw) -> AuthorizationContext:
    kw.setdefault("identity_verified", True)
    return AuthorizationContext(subject_id="u1", **kw)


def test_unverified_context_raises() -> None:
    ctx = AuthorizationContext(subject_id="u1", roles=frozenset({"eng"}))
    with pytest.raises(PermissionError):
        authorize_scope(ctx)


def test_no_roles_denied() -> None:
    assert not authorize_scope(_ctx()).allowed


def test_role_mismatch_denied() -> None:
    ctx = _ctx(roles=frozenset({"viewer"}))
    acl = FakeAcl("d1", roles_allowed=("admin",), synced_at=_fresh())
    assert not evaluate_document(ctx, acl).allowed


def test_site_mismatch_denied() -> None:
    ctx = _ctx(roles=frozenset({"eng"}), sites=frozenset({"site-a"}))
    acl = FakeAcl("d1", sites=("site-b",), roles_allowed=("eng",), synced_at=_fresh())
    assert not evaluate_document(ctx, acl).allowed


def test_authorized_when_fresh_and_in_scope() -> None:
    ctx = _ctx(roles=frozenset({"eng"}), sites=frozenset({"site-a"}))
    acl = FakeAcl("d1", sites=("site-a",), roles_allowed=("eng",), synced_at=_fresh())
    assert evaluate_document(ctx, acl).allowed


def test_filter_removes_unauthorized() -> None:
    ctx = _ctx(roles=frozenset({"eng"}), sites=frozenset({"site-a"}))
    allowed = FakeAcl("d1", sites=("site-a",), roles_allowed=("eng",), synced_at=_fresh())
    blocked = FakeAcl("d2", sites=("site-b",), roles_allowed=("eng",), synced_at=_fresh())
    out = filter_candidates(ctx, [(allowed, "keep"), (blocked, "drop")])
    assert out == ["keep"]
