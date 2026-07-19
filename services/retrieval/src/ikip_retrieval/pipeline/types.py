"""Shared types for the retrieval head.

`RetrievalQuery` is the authorized-and-parsed request handed to the search channels.
`Candidate` is what a channel returns: a potential piece of evidence plus everything
needed to (a) authorize it and (b) rank it, without yet committing to it being shown.

A Candidate carries its own ACL so authorization filtering can run BEFORE ranking — the
invariant that restricted content never enters ranking, prompts, or citations depends on
the filter seeing an ACL for every candidate.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ikip_contracts import Authority, Provenance, RetrievalChannel


@dataclass(frozen=True)
class RetrievalQuery:
    """A parsed, already-scope-authorized query. Channels receive this, not raw input."""

    question: str
    asset_ids: frozenset[str] = frozenset()
    sites: frozenset[str] = frozenset()


@dataclass(frozen=True)
class CandidateAcl:
    """The subset of an AclPolicy needed to authorize a candidate (satisfies ikip_authz.HasAcl).

    Kept on the Candidate so merge_rerank can deny-by-default filter before ranking.
    """

    document_id: str
    sites: tuple[str, ...] = ()
    roles_allowed: tuple[str, ...] = ()
    synced_at: str | None = None
    max_staleness_seconds: int | None = None


@dataclass(frozen=True)
class Candidate:
    """A retrieval hit from one channel, not yet authorized or ranked."""

    evidence_id: str
    document_id: str
    text: str
    provenance: Provenance
    authority: Authority
    acl: CandidateAcl
    channel: RetrievalChannel
    retrieval_score: float = 0.0
    applicability: dict = field(default_factory=dict)
    # Higher ordinal = newer revision; used only as a ranking tie-break.
    revision_ordinal: int = 0
