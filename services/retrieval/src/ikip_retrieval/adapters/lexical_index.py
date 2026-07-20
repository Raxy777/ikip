"""In-memory lexical (BM25) SearchChannel adapter.

A real, dependency-free implementation of the lexical channel: it builds an inverted index
over indexed document text and ranks with Okapi BM25. Unlike the semantic channel (which
needs a live pgvector store and an embedding model), lexical retrieval is pure computation,
so this adapter runs and is testable end to end here.

Two design points that keep the authorization invariant intact:

  1. Every indexed chunk is tied to a `document_id`, and the ACL for each candidate is
     pulled from the shared AclStore ([[reconcile]] keeps it fresh). The adapter does NOT
     authorize — it just attaches the ACL so merge_rerank can filter before ranking. If a
     document has no ACL in the store, the candidate carries an ACL that fails closed
     (empty scope, no synced_at) so the freshness/scope gate denies it rather than the
     adapter silently deciding.
  2. The adapter returns raw Candidates ranked by lexical score only. Authority ranking and
     authorization filtering are the pipeline's job, not the channel's.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from ikip_authz.sync import AclStore
from ikip_contracts import Authority, ProcessingVersions, Provenance, RetrievalChannel

from ikip_retrieval.adapters._acl_resolve import resolve_acl
from ikip_retrieval.pipeline.types import Candidate, RetrievalQuery

_TOKEN = re.compile(r"[a-z0-9]+")

# Standard Okapi BM25 parameters.
_K1 = 1.5
_B = 0.75


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass(frozen=True)
class IndexedChunk:
    """A unit of retrievable text with the provenance needed to build an Evidence later."""

    evidence_id: str
    document_id: str
    text: str
    source_revision: str = "r1"
    authority: Authority = Authority.APPROVED
    applicability: dict = field(default_factory=dict)
    revision_ordinal: int = 0


class LexicalIndex:
    """A BM25 inverted index that implements the SearchChannel port.

    Construct, `add` chunks, then `search`. ACLs are resolved at search time from the
    supplied AclStore so revocations/updates applied by the sync layer take effect without
    reindexing.
    """

    def __init__(self, acl_store: AclStore) -> None:
        self._acls = acl_store
        self._chunks: list[IndexedChunk] = []
        self._tokens: list[list[str]] = []
        self._df: dict[str, int] = {}
        self._total_len = 0

    def add(self, chunk: IndexedChunk) -> None:
        toks = _tokenize(chunk.text)
        self._chunks.append(chunk)
        self._tokens.append(toks)
        self._total_len += len(toks)
        for term in set(toks):
            self._df[term] = self._df.get(term, 0) + 1

    # -- SearchChannel port -------------------------------------------------------------
    def search(self, query: RetrievalQuery, *, limit: int) -> list[Candidate]:
        if not self._chunks:
            return []
        q_terms = _tokenize(query.question)
        if not q_terms:
            return []

        n = len(self._chunks)
        avgdl = self._total_len / n

        scored: list[tuple[float, int]] = []
        for i, toks in enumerate(self._tokens):
            score = self._bm25(q_terms, toks, n, avgdl)
            if score > 0.0:
                scored.append((score, i))

        scored.sort(key=lambda s: s[0], reverse=True)
        return [self._to_candidate(self._chunks[i], score) for score, i in scored[:limit]]

    # -- internals ----------------------------------------------------------------------
    def _bm25(self, q_terms: list[str], doc_toks: list[str], n: int, avgdl: float) -> float:
        if not doc_toks:
            return 0.0
        dl = len(doc_toks)
        freqs: dict[str, int] = {}
        for t in doc_toks:
            freqs[t] = freqs.get(t, 0) + 1

        score = 0.0
        for term in q_terms:
            f = freqs.get(term, 0)
            if f == 0:
                continue
            df = self._df.get(term, 0)
            # BM25 idf with the standard +0.5 smoothing; floored at 0 for common terms.
            idf = max(0.0, math.log((n - df + 0.5) / (df + 0.5) + 1.0))
            denom = f + _K1 * (1 - _B + _B * dl / avgdl)
            score += idf * (f * (_K1 + 1)) / denom
        return score

    def _to_candidate(self, chunk: IndexedChunk, score: float) -> Candidate:
        prov = Provenance(
            source_document_id=chunk.document_id,
            source_revision=chunk.source_revision,
            processing_versions=ProcessingVersions(parser="lexical", chunker="lexical", embedding_model="none"),
        )
        return Candidate(
            evidence_id=chunk.evidence_id,
            document_id=chunk.document_id,
            text=chunk.text,
            provenance=prov,
            authority=chunk.authority,
            acl=resolve_acl(self._acls, chunk.document_id),
            channel=RetrievalChannel.LEXICAL,
            retrieval_score=score,
            applicability=chunk.applicability,
            revision_ordinal=chunk.revision_ordinal,
        )
