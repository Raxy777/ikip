"""The SearchChannel port — one interface for all four retrieval strategies.

Exact, lexical, semantic, and relationship search each implement this. Keeping them behind
one port means merge_rerank and authorization filtering treat every channel identically,
so no channel can leak what another would block (Query-flow invariant #2).

A channel returns raw Candidates. It does NOT authorize them — authorization is applied
uniformly downstream in merge_rerank via ikip_authz, before any ranking. This keeps the
"authorize before ranking" ordering in one place instead of trusting each channel.
"""
from __future__ import annotations

from typing import Protocol

from ikip_retrieval.pipeline.types import Candidate, RetrievalQuery


class SearchChannel(Protocol):
    def search(self, query: RetrievalQuery, *, limit: int) -> list[Candidate]:
        """Return up to `limit` candidates for this channel. Ordering is advisory."""
        ...
