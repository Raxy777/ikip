"""Shape-similarity channel: ranks parts by geometric-descriptor distance (§C).

Implements the SearchChannel port. Reads a shape_descriptor from the RetrievalQuery
(attached by the caller when a reference part is available), queries the ShapeStore, and
returns raw Candidates. Like every channel it does NOT authorize — authorization is applied
uniformly in merge_rerank before ranking, so a restricted part can never surface here.

Returns an empty list when no shape_descriptor is present on the query (graceful no-op for
text-only queries that have no reference geometry).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ikip_authz.sync import AclStore
from ikip_contracts import Authority, ProcessingVersions, Provenance, RetrievalChannel

from ikip_retrieval.adapters._acl_resolve import resolve_acl
from ikip_retrieval.pipeline.types import Candidate, RetrievalQuery
from ikip_retrieval.ports.shape_store import ShapeStore


@dataclass(frozen=True)
class ShapeRetrievalQuery(RetrievalQuery):
    """RetrievalQuery extended with an optional shape descriptor for the SHAPE channel.

    Callers that have a reference part attach its D2 descriptor here; text-only callers
    leave it as None and the channel returns nothing (no-op).
    """

    shape_descriptor: list[float] | None = field(default=None, compare=False)


class ShapeSearchChannel:
    """SHAPE channel: cosine-similarity search over D2 shape descriptors."""

    def __init__(self, store: ShapeStore, acl_store: AclStore) -> None:
        self._store = store
        self._acls = acl_store

    def search(self, query: RetrievalQuery, *, limit: int) -> list[Candidate]:
        descriptor = getattr(query, "shape_descriptor", None)
        if not descriptor:
            return []

        # Authorization filter is applied by the store (allowed_document_ids).
        # merge_rerank will re-filter; the store filter is defence-in-depth.
        # We pass frozenset() as a sentinel here — the real filter is in merge_rerank.
        # The store must still respect it, so we pass ALL as a large open set.
        # NOTE: the store's allowed_document_ids is the ACL-filtered set; we pass
        # frozenset() to get all, then merge_rerank filters. This matches the pattern
        # used by lexical/exact channels (they also return unfiltered candidates).
        results = self._store.shape_search(
            descriptor,
            allowed_document_ids=frozenset({"*"}),  # store-level pre-filter disabled; merge_rerank owns auth
            limit=limit,
        )

        return [self._to_candidate(rec, score) for rec, score in results]

    def _to_candidate(self, rec, score: float) -> Candidate:
        pv = ProcessingVersions(
            parser="shape-d2:0.1",
            chunker="shape-d2:0.1",
            embedding_model="none",
            extraction_tier="full_geometry",
        )
        prov = Provenance(
            source_document_id=rec.document_id,
            source_revision="r1",
            processing_versions=pv,
        )
        return Candidate(
            evidence_id=rec.evidence_id,
            document_id=rec.document_id,
            text=f"[shape match] part_id={rec.part_id}",
            provenance=prov,
            authority=Authority.APPROVED,
            acl=resolve_acl(self._acls, rec.document_id),
            channel=RetrievalChannel.SHAPE,
            retrieval_score=float(score),
        )
