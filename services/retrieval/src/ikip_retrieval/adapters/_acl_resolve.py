"""Shared, fail-closed ACL resolution for search adapters.

Every channel adapter attaches an ACL to each Candidate so merge_rerank can authorize
before ranking. This is the single place that mapping happens, so all adapters fail closed
identically: a document with no ACL in the store gets a CandidateAcl with empty scope and
no synced_at, which the downstream freshness/scope gate denies. An adapter never fabricates
an allow.
"""
from __future__ import annotations

from ikip_authz.sync import AclStore
from ikip_contracts import AclPolicy

from ikip_retrieval.pipeline.types import CandidateAcl


def resolve_acl(store: AclStore, document_id: str) -> CandidateAcl:
    """Return the document's ACL from the store, or a fail-closed ACL if absent."""
    acl = store.get(document_id)
    if acl is None:
        return CandidateAcl(document_id=document_id)  # no synced_at -> fails closed
    return CandidateAcl(
        document_id=acl.document_id,
        sites=tuple(acl.sites),
        roles_allowed=tuple(acl.roles_allowed),
        synced_at=acl.synced_at.isoformat() if acl.synced_at is not None else None,
        max_staleness_seconds=acl.max_staleness_seconds,
    )
