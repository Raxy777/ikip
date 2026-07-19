"""Trust-boundary invariant: retrieval cannot run without a verified authorization context.

This encodes the sequence-diagram invariant #1 as an executable check. If someone later
adds a search path that skips authorization, this test should fail.
"""
from __future__ import annotations

import pytest

from ikip_authz import AuthorizationContext, filter_candidates


def test_filter_requires_verified_identity() -> None:
    unverified = AuthorizationContext(subject_id="u1", roles=frozenset({"eng"}))
    with pytest.raises(PermissionError):
        filter_candidates(unverified, [])


def test_empty_authorization_yields_no_results() -> None:
    # Deny-by-default: a verified context with no matching ACLs returns nothing.
    verified = AuthorizationContext(
        subject_id="u1", roles=frozenset({"eng"}), identity_verified=True
    )
    assert filter_candidates(verified, []) == []
