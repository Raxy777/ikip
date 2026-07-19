"""ACL sync: reconcile (pull) and apply_event (push) into the local store.

The load-bearing tests are the revocation paths — `test_reconcile_revokes_missing` and
`test_push_revoke_deletes` — because a document dropped upstream must stop being served
here. The freshness integration test proves reconcile stamps `synced_at` so a synced ACL
actually passes the gate, and that an un-reconciled document is denied by freshness.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ikip_authz import (
    AclEvent,
    EventType,
    InMemoryAclStore,
    apply_event,
    check_freshness,
    reconcile,
)
from ikip_contracts import AclPolicy


def _acl(doc, *, sites=("site-a",), roles=("eng",), owner="o", max_stale=3600) -> AclPolicy:
    return AclPolicy(
        document_id=doc,
        owner=owner,
        sites=list(sites),
        roles_allowed=list(roles),
        source_of_truth="edms",
        max_staleness_seconds=max_stale,
    )


class _FakeSource:
    def __init__(self, acls):
        self._acls = list(acls)

    def set(self, acls):
        self._acls = list(acls)

    def fetch_current(self):
        return list(self._acls)


def test_reconcile_upserts_current_acls() -> None:
    source = _FakeSource([_acl("d1"), _acl("d2")])
    store = InMemoryAclStore()
    report = reconcile(source, store)
    assert report.upserted == 2
    assert store.all_document_ids() == {"d1", "d2"}


def test_reconcile_stamps_synced_at_so_freshness_passes() -> None:
    source = _FakeSource([_acl("d1")])
    store = InMemoryAclStore()
    reconcile(source, store)
    acl = store.get("d1")
    assert acl.synced_at is not None
    # A just-reconciled ACL must be fresh.
    assert check_freshness(acl).allowed


def test_reconcile_revokes_missing() -> None:
    # d2 disappears upstream (revoked). Reconcile must delete it locally.
    source = _FakeSource([_acl("d1"), _acl("d2")])
    store = InMemoryAclStore()
    reconcile(source, store)
    assert "d2" in store.all_document_ids()

    source.set([_acl("d1")])  # d2 revoked upstream
    report = reconcile(source, store)
    assert report.revoked == 1
    assert store.all_document_ids() == {"d1"}
    assert store.get("d2") is None


def test_reconcile_reports_unchanged_but_restamps() -> None:
    source = _FakeSource([_acl("d1")])
    store = InMemoryAclStore()
    # Seed with an old stamp so we can prove reconcile refreshes it.
    old = _acl("d1").model_copy(update={"synced_at": datetime.now(timezone.utc) - timedelta(days=2)})
    store.upsert(old)

    report = reconcile(source, store)
    assert report.unchanged == 1
    assert report.upserted == 0
    # Re-stamped to fresh even though scope was identical.
    assert check_freshness(store.get("d1")).allowed


def test_reconcile_detects_scope_change_as_upsert() -> None:
    source = _FakeSource([_acl("d1", roles=("eng",))])
    store = InMemoryAclStore()
    reconcile(source, store)

    source.set([_acl("d1", roles=("eng", "admin"))])  # role added
    report = reconcile(source, store)
    assert report.upserted == 1
    assert set(store.get("d1").roles_allowed) == {"eng", "admin"}


def test_push_upsert_writes_fresh() -> None:
    store = InMemoryAclStore()
    apply_event(store, AclEvent(EventType.UPSERT, "d1", acl=_acl("d1")))
    assert check_freshness(store.get("d1")).allowed


def test_push_revoke_deletes() -> None:
    store = InMemoryAclStore()
    apply_event(store, AclEvent(EventType.UPSERT, "d1", acl=_acl("d1")))
    apply_event(store, AclEvent(EventType.REVOKE, "d1"))
    assert store.get("d1") is None


def test_unreconciled_document_denied_by_freshness() -> None:
    # A document never reconciled has no synced_at -> freshness denies (fail closed).
    store = InMemoryAclStore()
    store.upsert(_acl("d1"))  # no synced_at
    assert not check_freshness(store.get("d1")).allowed
