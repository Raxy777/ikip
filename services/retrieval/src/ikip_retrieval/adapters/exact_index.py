"""In-memory exact-match SearchChannel adapter.

The exact channel answers a different question than lexical BM25: it finds chunks that
carry a specific identifier — an asset tag ("P-101"), equipment code, document number, or
a phrase the user quoted verbatim. Precision is the whole point, so matching is exact, not
fuzzy: "P-101" matches "P-101" but never "P-1010" or "P 101". Matching is case-insensitive
and whitespace-normalized only.

Two kinds of match, both exact:
  1. Identifier match — the query mentions a token that is a registered identifier for a
     chunk (asset tags, codes, doc numbers indexed alongside the text).
  2. Quoted-phrase match — a "double-quoted" span in the question that appears verbatim in
     the chunk text.

Like every channel it returns raw Candidates and does NOT authorize — ACLs are resolved
(fail-closed) from the shared AclStore and filtering happens in merge_rerank before ranking.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ikip_authz.sync import AclStore
from ikip_contracts import Authority, ProcessingVersions, Provenance, RetrievalChannel

from ikip_retrieval.adapters._acl_resolve import resolve_acl
from ikip_retrieval.pipeline.types import Candidate, RetrievalQuery

# Identifier-shaped tokens: alphanumerics with internal separators (P-101, 12-FIC-3001A,
# DOC-2024-0007). Kept deliberately broad on shape but matched EXACTLY, not by prefix.
_IDENT = re.compile(r"[A-Za-z0-9]+(?:[-_/][A-Za-z0-9]+)+|\b[A-Za-z]*\d[A-Za-z0-9]*\b")
_QUOTED = re.compile(r'"([^"]+)"')
_WS = re.compile(r"\s+")

# Ranking weights: an explicit identifier hit is a stronger signal than a phrase hit, and
# multiple distinct matches in one chunk rank above a single match.
_IDENT_WEIGHT = 2.0
_PHRASE_WEIGHT = 1.0


def _norm(s: str) -> str:
    return _WS.sub(" ", s).strip().lower()


@dataclass(frozen=True)
class ExactRecord:
    """A chunk plus the identifiers it should match exactly."""

    evidence_id: str
    document_id: str
    text: str
    identifiers: tuple[str, ...] = ()
    source_revision: str = "r1"
    authority: Authority = Authority.APPROVED
    applicability: dict = field(default_factory=dict)
    revision_ordinal: int = 0


class ExactIndex:
    """Exact identifier / quoted-phrase index implementing the SearchChannel port."""

    def __init__(self, acl_store: AclStore) -> None:
        self._acls = acl_store
        self._records: list[ExactRecord] = []
        # normalized identifier -> set of record indices holding it
        self._by_ident: dict[str, set[int]] = {}

    def add(self, record: ExactRecord) -> None:
        idx = len(self._records)
        self._records.append(record)
        for ident in record.identifiers:
            self._by_ident.setdefault(_norm(ident), set()).add(idx)

    # -- SearchChannel port -------------------------------------------------------------
    def search(self, query: RetrievalQuery, *, limit: int) -> list[Candidate]:
        if not self._records:
            return []

        idents = self._query_identifiers(query.question)
        phrases = [_norm(p) for p in _QUOTED.findall(query.question)]
        if not idents and not phrases:
            return []

        scores: dict[int, float] = {}

        # Identifier hits: exact match against the registered identifier set.
        for ident in idents:
            for rec_idx in self._by_ident.get(ident, ()):  # exact key lookup, no prefix
                scores[rec_idx] = scores.get(rec_idx, 0.0) + _IDENT_WEIGHT

        # Quoted-phrase hits: verbatim (normalized) substring of the chunk text.
        if phrases:
            for rec_idx, rec in enumerate(self._records):
                norm_text = _norm(rec.text)
                for phrase in phrases:
                    if phrase and phrase in norm_text:
                        scores[rec_idx] = scores.get(rec_idx, 0.0) + _PHRASE_WEIGHT

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return [self._to_candidate(self._records[i], s) for i, s in ranked[:limit]]

    # -- internals ----------------------------------------------------------------------
    def _query_identifiers(self, question: str) -> set[str]:
        """Extract identifier-shaped tokens from the query, normalized for exact lookup."""
        return {_norm(m.group(0)) for m in _IDENT.finditer(question)}

    def _to_candidate(self, rec: ExactRecord, score: float) -> Candidate:
        prov = Provenance(
            source_document_id=rec.document_id,
            source_revision=rec.source_revision,
            processing_versions=ProcessingVersions(parser="exact", chunker="exact", embedding_model="none"),
        )
        return Candidate(
            evidence_id=rec.evidence_id,
            document_id=rec.document_id,
            text=rec.text,
            provenance=prov,
            authority=rec.authority,
            acl=resolve_acl(self._acls, rec.document_id),
            channel=RetrievalChannel.EXACT,
            retrieval_score=score,
            applicability=rec.applicability,
            revision_ordinal=rec.revision_ordinal,
        )
