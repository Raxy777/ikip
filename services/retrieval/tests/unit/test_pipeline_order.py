"""Assert the ordering invariant: a denied request never reaches search."""
from __future__ import annotations

from ikip_authz import AuthorizationContext

from ikip_retrieval.pipeline.authorize import gate_request


def test_verified_but_no_roles_is_denied() -> None:
    ctx = AuthorizationContext(subject_id="u1", identity_verified=True)
    assert not gate_request(ctx).allowed


def test_authorized_request_passes_gate() -> None:
    ctx = AuthorizationContext(
        subject_id="u1", roles=frozenset({"eng"}), identity_verified=True
    )
    assert gate_request(ctx).allowed
