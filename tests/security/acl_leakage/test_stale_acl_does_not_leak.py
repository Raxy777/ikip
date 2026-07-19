"""ACL leakage: revoked-upstream / stale-cache scenario.

The scenario from docs/safety/acl-sync-and-freshness.md: a user's access was revoked in
the source of truth, but this platform still holds a cached ACL that says allow. If that
cache is stale, the content must NOT surface — not in the ranked set, not in the evidence
sent to the model, and not in a citation.

These tests exercise the leak path at two levels: the authorization filter directly, and
the full query pipeline, to prove staleness closes the path end to end.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ikip_authz import AuthorizationContext, filter_candidates
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

from ikip_retrieval.pipeline.run import run_query
from ikip_retrieval.pipeline.types import Candidate, CandidateAcl, RetrievalQuery


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _verified_ctx() -> AuthorizationContext:
    return AuthorizationContext(
        subject_id="u1",
        roles=frozenset({"eng"}),
        sites=frozenset({"site-a"}),
        identity_verified=True,
    )


def _stale_but_matching_candidate() -> Candidate:
    """A candidate whose cached ACL still says allow, but was synced a day ago."""
    pv = ProcessingVersions(parser="p@1", chunker="c@1", embedding_model="e@1")
    prov = Provenance(source_document_id="d-secret", source_revision="r1", processing_versions=pv)
    day_old = _iso(datetime.now(timezone.utc) - timedelta(days=1))
    return Candidate(
        evidence_id="e-secret",
        document_id="d-secret",
        text="restricted content the user was revoked from",
        provenance=prov,
        authority=Authority.APPROVED,
        acl=CandidateAcl(
            document_id="d-secret",
            sites=("site-a",),  # cache still says the user's site is allowed
            roles_allowed=("eng",),  # ...and their role
            synced_at=day_old,  # ...but it hasn't been re-synced since revocation
            max_staleness_seconds=3600,
        ),
        channel=RetrievalChannel.SEMANTIC,
        retrieval_score=0.99,
    )


class _ExplodingGateway:
    """If the pipeline reaches synthesis with the stale evidence, that is already a leak."""

    def synthesize(self, *, request_id, question, evidence, config_version) -> Answer:
        assert not evidence, f"stale content leaked into synthesis: {[e.evidence_id for e in evidence]}"
        claim = Claim(
            claim_id="c1",
            text="x",
            citation=Citation(
                claim_id="c1", evidence_ids=["e-secret"], statement_class=StatementClass.HISTORICAL_OBSERVATION
            ),
        )
        return Answer(
            request_id=request_id, outcome=Outcome.ANSWERED, config_version=config_version, claims=[claim]
        )


class _StaleChannel:
    def search(self, query, *, limit):
        return [_stale_but_matching_candidate()]


def test_stale_acl_filtered_out_directly() -> None:
    ctx = _verified_ctx()
    cand = _stale_but_matching_candidate()
    out = filter_candidates(ctx, [(cand.acl, "leaked")])
    assert out == []


def test_stale_content_never_reaches_model_or_citation() -> None:
    ans = run_query(
        request_id="r1",
        ctx=_verified_ctx(),
        query=RetrievalQuery(question="what happened to the secret asset?"),
        channels=[_StaleChannel()],
        gateway=_ExplodingGateway(),
        config_version="cfg@1",
    )
    # No fresh authorized evidence -> abstain, and phrased as insufficient (not scope) so
    # the abstention itself doesn't reveal that restricted content exists.
    assert ans.outcome is Outcome.ABSTAINED
    assert ans.abstention.reason is AbstentionReason.INSUFFICIENT
    assert ans.claims is None
