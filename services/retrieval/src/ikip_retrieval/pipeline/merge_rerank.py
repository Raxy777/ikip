"""Merge candidates from all channels, authorize-filter, deduplicate, then rank.

ORDER IS THE SAFETY PROPERTY. This stage:

  1. Authorization-filters EVERY candidate through ikip_authz, identically across channels,
     BEFORE anything is ranked. Restricted content never enters ranking (Security #1).
  2. Deduplicates the same evidence surfaced by multiple channels, keeping the best signal.
  3. Ranks by authority first, then applicability, then revision recency, then score —
     the ordering from docs/safety/conflict-and-authority-ranking.md. Current guidance
     (approved/draft) outranks superseded/withdrawn, which are excluded from ranking here
     (they may still be shown as clearly-labelled history elsewhere).

Superseded/withdrawn sources are dropped from the ranked set: they must never be presented
as current guidance. Keeping them out of the evidence handed to the model is the simplest
way to guarantee that.
"""
from __future__ import annotations

from collections.abc import Iterable

from ikip_authz import AuthorizationContext
from ikip_authz.filter import evaluate_document
from ikip_contracts import Authority

from ikip_retrieval.pipeline.types import Candidate


def merge_and_rank(
    ctx: AuthorizationContext,
    channel_results: Iterable[list[Candidate]],
) -> list[Candidate]:
    """Return authorized, deduplicated candidates ranked best-first.

    Requires a verified AuthorizationContext; a channel result cannot be ranked without
    one, so ranking can never precede authorization.
    """
    ctx.require_verified()

    # 1. Flatten and authorize-filter uniformly, before any ranking.
    authorized: list[Candidate] = []
    for results in channel_results:
        for cand in results:
            # Exclude non-current guidance from the ranked set entirely.
            if not cand.authority.is_current_guidance:
                continue
            if evaluate_document(ctx, cand.acl).allowed:
                authorized.append(cand)

    # 2. Deduplicate by evidence_id, keeping the highest-authority / highest-score copy.
    best: dict[str, Candidate] = {}
    for cand in authorized:
        existing = best.get(cand.evidence_id)
        if existing is None or _rank_key(cand) > _rank_key(existing):
            best[cand.evidence_id] = cand

    # 3. Rank best-first.
    return sorted(best.values(), key=_rank_key, reverse=True)


# Higher tuple = better. Authority weight dominates, then applicability specificity,
# then revision recency, then raw retrieval score as the final tie-break.
_AUTHORITY_WEIGHT = {
    Authority.APPROVED: 2,
    Authority.DRAFT: 1,
}


def _rank_key(c: Candidate) -> tuple[int, int, int, float]:
    applicability_specificity = len(c.applicability.get("scope", []))
    return (
        _AUTHORITY_WEIGHT.get(c.authority, 0),
        applicability_specificity,
        c.revision_ordinal,
        c.retrieval_score,
    )
