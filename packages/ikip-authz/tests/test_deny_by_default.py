"""Deny-by-default is the contract. These tests assert the failure modes, not just success."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from ikip_authz import AuthorizationContext, authorize_scope, filter_candidates
from ikip_authz.filter import evaluate_document


@dataclass
class FakeAcl:
    document_id: str
    sites: tuple[str, ...] = ()
    roles_allowed: tuple[str, ...] = ()
    synced_at: str | None = None
    max_staleness_seconds: int | None = None


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
    acl = FakeAcl("d1", roles_allowed=("admin",))
    assert not evaluate_document(ctx, acl).allowed


def test_site_mismatch_denied() -> None:
    ctx = _ctx(roles=frozenset({"eng"}), sites=frozenset({"site-a"}))
    acl = FakeAcl("d1", sites=("site-b",), roles_allowed=("eng",))
    assert not evaluate_document(ctx, acl).allowed


def test_filter_removes_unauthorized() -> None:
    ctx = _ctx(roles=frozenset({"eng"}), sites=frozenset({"site-a"}))
    allowed = FakeAcl("d1", sites=("site-a",), roles_allowed=("eng",))
    blocked = FakeAcl("d2", sites=("site-b",), roles_allowed=("eng",))
    out = filter_candidates(ctx, [(allowed, "keep"), (blocked, "drop")])
    assert out == ["keep"]
