"""ACL synchronization — reconciling upstream truth into the local ACL store.

This is the layer that keeps cached ACLs in sync with the systems that actually own
permissions (CMMS / EDMS / QMS), addressing the open design in
docs/safety/acl-sync-and-freshness.md. It is the ONLY place `synced_at` is written, so the
freshness gate ([[freshness]]/`check_freshness`) has a single, trustworthy source for
"when was this last reconciled".

Two mechanisms, matching the spec:

  - `reconcile(...)` — PULL: fetch the full current ACL set from a source and make the
    local store match it. Bounds worst-case staleness even if push fails.
  - `apply_event(...)` — PUSH: apply a single upsert/revoke event (webhook) for low latency.

Both stamp `synced_at = now` on write, so a document only stays serve-able while a fresh
reconcile keeps proving it. The safety-critical case is REVOCATION: when a document is no
longer authorized upstream, `reconcile` DELETES it locally so it stops being served. If a
push revoke is missed, the freshness gate still fails the ACL closed once the staleness
bound is exceeded — sync and freshness are defense-in-depth for the same leak.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Protocol

from ikip_contracts import AclPolicy


class AclSource(Protocol):
    """An upstream system of record for ACLs (one per `source_of_truth`)."""

    def fetch_current(self) -> Iterable[AclPolicy]:
        """Return the CURRENT authorized ACL set. Absence of a document means revoked."""
        ...


class AclStore(Protocol):
    """The local cache of ACLs that retrieval authorizes against."""

    def get(self, document_id: str) -> AclPolicy | None: ...

    def upsert(self, acl: AclPolicy) -> None: ...

    def delete(self, document_id: str) -> None: ...

    def all_document_ids(self) -> set[str]: ...


class EventType(enum.Enum):
    UPSERT = "upsert"  # ACL created or its scope changed
    REVOKE = "revoke"  # access removed upstream — stop serving


@dataclass(frozen=True)
class AclEvent:
    """A single push notification from a source of truth."""

    type: EventType
    document_id: str
    acl: AclPolicy | None = None  # required for UPSERT; ignored for REVOKE


@dataclass(frozen=True)
class SyncReport:
    """Outcome of a reconcile, for audit and observability."""

    upserted: int = 0
    revoked: int = 0
    unchanged: int = 0

    @property
    def total_changed(self) -> int:
        return self.upserted + self.revoked


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamped(acl: AclPolicy, now: datetime) -> AclPolicy:
    """Return the ACL with `synced_at` set to the reconcile time.

    Reconcile time — not any timestamp the source supplied — is what freshness measures,
    so a source that reports a stale or missing time can't extend an ACL's trusted life.
    """
    return acl.model_copy(update={"synced_at": now})


def reconcile(source: AclSource, store: AclStore, *, now: datetime | None = None) -> SyncReport:
    """Make `store` match `source`. Upserts current ACLs; deletes revoked ones.

    Deletion of documents no longer present upstream is the revocation path: a user whose
    access was removed stops being served here as soon as the next reconcile runs (and no
    later than the staleness bound, via the freshness gate, if reconcile is delayed).
    """
    now = now or _now()

    upserted = unchanged = 0
    seen: set[str] = set()

    for acl in source.fetch_current():
        seen.add(acl.document_id)
        existing = store.get(acl.document_id)
        # Compare ignoring synced_at, so a pure re-stamp isn't counted as a scope change.
        if existing is not None and _scope_equal(existing, acl):
            # Still re-stamp freshness so an unchanged-but-reconfirmed ACL stays fresh.
            store.upsert(_stamped(acl, now))
            unchanged += 1
        else:
            store.upsert(_stamped(acl, now))
            upserted += 1

    # Anything in the store but NOT in the current upstream set has been revoked.
    revoked = 0
    for doc_id in store.all_document_ids() - seen:
        store.delete(doc_id)
        revoked += 1

    return SyncReport(upserted=upserted, revoked=revoked, unchanged=unchanged)


def apply_event(store: AclStore, event: AclEvent, *, now: datetime | None = None) -> None:
    """Apply a single push event. REVOKE deletes; UPSERT writes with a fresh stamp."""
    now = now or _now()
    if event.type is EventType.REVOKE:
        store.delete(event.document_id)
        return
    if event.acl is None:
        raise ValueError("UPSERT event requires an acl payload")
    store.upsert(_stamped(event.acl, now))


def _scope_equal(a: AclPolicy, b: AclPolicy) -> bool:
    """True if the authorization-relevant fields match (ignores synced_at)."""
    return (
        a.owner == b.owner
        and sorted(a.sites) == sorted(b.sites)
        and sorted(a.roles_allowed) == sorted(b.roles_allowed)
        and a.classification == b.classification
        and a.source_of_truth == b.source_of_truth
        and a.max_staleness_seconds == b.max_staleness_seconds
    )


class InMemoryAclStore:
    """Reference AclStore for tests and single-process use. Not for production scale."""

    def __init__(self) -> None:
        self._acls: dict[str, AclPolicy] = {}

    def get(self, document_id: str) -> AclPolicy | None:
        return self._acls.get(document_id)

    def upsert(self, acl: AclPolicy) -> None:
        self._acls[acl.document_id] = acl

    def delete(self, document_id: str) -> None:
        self._acls.pop(document_id, None)

    def all_document_ids(self) -> set[str]:
        return set(self._acls)
