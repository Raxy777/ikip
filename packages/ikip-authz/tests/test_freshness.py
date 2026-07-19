"""ACL freshness gate. Fail closed: an ACL that can't be proven fresh must deny.

This is the highest-risk leak path (docs/safety/acl-sync-and-freshness.md), so the tests
lead with the denial cases — never synced, unparseable, and stale-past-bound — and confirm
a stale ACL is denied even when its site/role would otherwise authorize.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ikip_authz import AuthorizationContext
from ikip_authz.filter import evaluate_document
from ikip_authz.freshness import DEFAULT_MAX_STALENESS_SECONDS, check_freshness


@dataclass
class FakeAcl:
    document_id: str = "d1"
    sites: tuple[str, ...] = ()
    roles_allowed: tuple[str, ...] = ()
    synced_at: object = None
    max_staleness_seconds: int | None = None


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def test_never_synced_denies() -> None:
    assert not check_freshness(FakeAcl(synced_at=None)).allowed


def test_unparseable_synced_at_denies() -> None:
    assert not check_freshness(FakeAcl(synced_at="not-a-timestamp")).allowed


def test_fresh_within_bound_allows() -> None:
    acl = FakeAcl(synced_at=_iso(_now() - timedelta(seconds=30)), max_staleness_seconds=3600)
    assert check_freshness(acl).allowed


def test_stale_past_bound_denies() -> None:
    acl = FakeAcl(synced_at=_iso(_now() - timedelta(seconds=7200)), max_staleness_seconds=3600)
    assert not check_freshness(acl).allowed


def test_default_bound_applied_when_absent() -> None:
    # No max_staleness_seconds -> default applies; just past it must deny.
    stale = FakeAcl(synced_at=_iso(_now() - timedelta(seconds=DEFAULT_MAX_STALENESS_SECONDS + 60)))
    fresh = FakeAcl(synced_at=_iso(_now() - timedelta(seconds=10)))
    assert not check_freshness(stale).allowed
    assert check_freshness(fresh).allowed


def test_future_timestamp_within_skew_allows() -> None:
    # Small clock skew (30s ahead) is tolerated.
    acl = FakeAcl(synced_at=_iso(_now() + timedelta(seconds=30)), max_staleness_seconds=3600)
    assert check_freshness(acl).allowed


def test_implausible_future_timestamp_denies() -> None:
    acl = FakeAcl(synced_at=_iso(_now() + timedelta(hours=1)), max_staleness_seconds=3600)
    assert not check_freshness(acl).allowed


def test_naive_timestamp_treated_as_utc() -> None:
    naive = (datetime.now(timezone.utc) - timedelta(seconds=10)).replace(tzinfo=None)
    acl = FakeAcl(synced_at=_iso(naive), max_staleness_seconds=3600)
    assert check_freshness(acl).allowed


def test_stale_acl_denied_even_when_scope_matches() -> None:
    # The load-bearing case: revoked-upstream / stale cache. Site + role match, but the
    # ACL is stale, so evaluate_document must still deny.
    ctx = AuthorizationContext(
        subject_id="u1",
        roles=frozenset({"eng"}),
        sites=frozenset({"site-a"}),
        identity_verified=True,
    )
    stale = FakeAcl(
        document_id="d1",
        sites=("site-a",),
        roles_allowed=("eng",),
        synced_at=_iso(_now() - timedelta(days=1)),
        max_staleness_seconds=3600,
    )
    assert not evaluate_document(ctx, stale).allowed
