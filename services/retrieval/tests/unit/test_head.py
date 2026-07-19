"""Retrieval head: merge_rerank + assemble + full run_query wiring.

The load-bearing test is `test_unauthorized_candidate_never_ranked`: a candidate the
subject may not see must be dropped BEFORE ranking, so it can never reach the model,
citations, or the ranked set. The others cover authority ranking, superseded exclusion,
evidence bounding, and the end-to-end scope-denial short-circuit.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ikip_authz import AuthorizationContext
from ikip_contracts import (
    AbstentionReason,
    Answer,
    Authority,
    Citation,
    Claim,
    Outcome,
    ProcessingVersions,
    Provenance,
    RetrievalChannel,
    StatementClass,
)

from ikip_retrieval.pipeline.assemble_evidence import assemble
from ikip_retrieval.pipeline.merge_rerank import merge_and_rank
from ikip_retrieval.pipeline.run import run_query
from ikip_retrieval.pipeline.types import Candidate, CandidateAcl, RetrievalQuery

CONFIG = "cfg@1"


def _ctx(roles=("eng",), sites=("site-a",)) -> AuthorizationContext:
    return AuthorizationContext(
        subject_id="u1",
        roles=frozenset(roles),
        sites=frozenset(sites),
        identity_verified=True,
    )


def _cand(
    eid,
    doc,
    *,
    authority=Authority.APPROVED,
    acl_sites=("site-a",),
    acl_roles=("eng",),
    score=0.5,
    channel=RetrievalChannel.LEXICAL,
    applicability=None,
    revision_ordinal=0,
) -> Candidate:
    pv = ProcessingVersions(parser="p@1", chunker="c@1", embedding_model="e@1")
    prov = Provenance(source_document_id=doc, source_revision="r1", processing_versions=pv)
    return Candidate(
        evidence_id=eid,
        document_id=doc,
        text=f"text for {eid}",
        provenance=prov,
        authority=authority,
        acl=CandidateAcl(
            document_id=doc,
            sites=acl_sites,
            roles_allowed=acl_roles,
            synced_at=datetime.now(timezone.utc).isoformat(),
            max_staleness_seconds=3600,
        ),
        channel=channel,
        retrieval_score=score,
        applicability=applicability or {},
        revision_ordinal=revision_ordinal,
    )


def test_unauthorized_candidate_never_ranked() -> None:
    # A high-scoring candidate the subject may NOT see must not survive to ranking.
    allowed = _cand("e1", "d1", acl_sites=("site-a",), score=0.1)
    restricted = _cand("e2", "d2", acl_sites=("site-b",), score=0.99)
    ranked = merge_and_rank(_ctx(sites=("site-a",)), [[allowed, restricted]])
    ids = [c.evidence_id for c in ranked]
    assert ids == ["e1"]
    assert "e2" not in ids


def test_superseded_excluded_from_ranking() -> None:
    current = _cand("e1", "d1", authority=Authority.APPROVED)
    old = _cand("e2", "d2", authority=Authority.SUPERSEDED)
    withdrawn = _cand("e3", "d3", authority=Authority.WITHDRAWN)
    ranked = merge_and_rank(_ctx(), [[current, old, withdrawn]])
    assert [c.evidence_id for c in ranked] == ["e1"]


def test_authority_outranks_score() -> None:
    # Draft with a huge score must still rank below an approved source.
    approved = _cand("e1", "d1", authority=Authority.APPROVED, score=0.10)
    draft = _cand("e2", "d2", authority=Authority.DRAFT, score=0.95)
    ranked = merge_and_rank(_ctx(), [[draft, approved]])
    assert [c.evidence_id for c in ranked] == ["e1", "e2"]


def test_dedup_keeps_single_copy() -> None:
    # Same evidence_id from two channels collapses to one.
    a = _cand("e1", "d1", channel=RetrievalChannel.EXACT, score=0.4)
    b = _cand("e1", "d1", channel=RetrievalChannel.SEMANTIC, score=0.9)
    ranked = merge_and_rank(_ctx(), [[a], [b]])
    assert len(ranked) == 1
    assert ranked[0].evidence_id == "e1"


def test_assemble_bounds_evidence_and_per_document() -> None:
    # 5 candidates from one doc, cap per-document at 2.
    cands = [_cand(f"e{i}", "d1", score=1.0 - i / 10) for i in range(5)]
    ranked = merge_and_rank(_ctx(), [cands])
    evidence = assemble(ranked, max_evidence=10, max_per_document=2)
    assert len(evidence) == 2


class _FakeChannel:
    def __init__(self, cands):
        self._cands = cands

    def search(self, query, *, limit):
        return self._cands[:limit]


class _FakeGateway:
    """Echoes the first evidence back as a well-formed grounded claim."""

    def synthesize(self, *, request_id, question, evidence, config_version) -> Answer:
        first = evidence[0]
        claim = Claim(
            claim_id="c1",
            text="grounded",
            citation=Citation(
                claim_id="c1",
                evidence_ids=[first.evidence_id],
                statement_class=StatementClass.HISTORICAL_OBSERVATION,
            ),
        )
        return Answer(
            request_id=request_id, outcome=Outcome.ANSWERED, config_version=config_version, claims=[claim]
        )


def test_run_query_end_to_end_grounded() -> None:
    channel = _FakeChannel([_cand("e1", "d1"), _cand("e2", "d2", acl_sites=("site-b",))])
    ans = run_query(
        request_id="r1",
        ctx=_ctx(sites=("site-a",)),
        query=RetrievalQuery(question="why did pump-7 trip?"),
        channels=[channel],
        gateway=_FakeGateway(),
        config_version=CONFIG,
    )
    assert ans.outcome is Outcome.ANSWERED
    # Only the authorized evidence (e1) could have been cited.
    assert ans.claims[0].citation.evidence_ids == ["e1"]


def test_run_query_scope_denial_short_circuits() -> None:
    # No roles -> scope denied -> abstain, gateway/channels never consulted.
    class _Boom:
        def search(self, *_a, **_k):
            raise AssertionError("channels must not run on scope denial")

    ctx = AuthorizationContext(subject_id="u1", roles=frozenset(), identity_verified=True)
    ans = run_query(
        request_id="r1",
        ctx=ctx,
        query=RetrievalQuery(question="q"),
        channels=[_Boom()],
        gateway=_FakeGateway(),
        config_version=CONFIG,
    )
    assert ans.outcome is Outcome.ABSTAINED
    assert ans.abstention.reason is AbstentionReason.UNAUTHORIZED_SCOPE


def test_run_query_all_restricted_abstains_insufficient() -> None:
    # Every candidate is out of scope -> no evidence -> insufficient (not scope-leaking).
    channel = _FakeChannel([_cand("e1", "d1", acl_sites=("site-b",))])
    ans = run_query(
        request_id="r1",
        ctx=_ctx(sites=("site-a",)),
        query=RetrievalQuery(question="q"),
        channels=[channel],
        gateway=_FakeGateway(),
        config_version=CONFIG,
    )
    assert ans.outcome is Outcome.ABSTAINED
    assert ans.abstention.reason is AbstentionReason.INSUFFICIENT
