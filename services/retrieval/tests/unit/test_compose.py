"""End-to-end wiring of the answer-composition tail: gateway -> validate -> answer|abstain.

A fake gateway lets us drive every branch deterministically. The point of these tests is
that an unvalidated or hallucinated draft can NEVER reach the user — the pipeline abstains.
"""
from __future__ import annotations

from ikip_contracts import (
    AbstentionReason,
    Answer,
    Authority,
    Citation,
    Claim,
    Conflict,
    Evidence,
    Outcome,
    ProcessingVersions,
    Provenance,
    StatementClass,
)

from ikip_retrieval.pipeline.compose import compose_answer
from ikip_retrieval.ports.answer_gateway import GatewayError

CONFIG = "cfg@1"


def _evidence(eid: str, doc: str, applicability=None) -> Evidence:
    pv = ProcessingVersions(parser="p@1", chunker="c@1", embedding_model="e@1")
    prov = Provenance(source_document_id=doc, source_revision="r1", processing_versions=pv)
    return Evidence(
        evidence_id=eid,
        document_id=doc,
        text="text",
        provenance=prov,
        authority=Authority.APPROVED,
        applicability=applicability or {},
    )


def _grounded_answer(request_id: str, evidence_ids, conflicts=None) -> Answer:
    claim = Claim(
        claim_id="c1",
        text="a grounded claim",
        citation=Citation(
            claim_id="c1",
            evidence_ids=evidence_ids,
            statement_class=StatementClass.HISTORICAL_OBSERVATION,
        ),
    )
    return Answer(
        request_id=request_id,
        outcome=Outcome.ANSWERED,
        config_version=CONFIG,
        claims=[claim],
        conflicts=conflicts,
    )


class _FakeGateway:
    """Returns a preset draft, or raises, to drive each pipeline branch."""

    def __init__(self, draft: Answer | None = None, error: bool = False) -> None:
        self._draft = draft
        self._error = error

    def synthesize(self, *, request_id, question, evidence, config_version) -> Answer:
        if self._error:
            raise GatewayError("provider down")
        assert self._draft is not None
        return self._draft


def test_no_evidence_abstains_without_calling_gateway() -> None:
    class _Boom:
        def synthesize(self, **_kw):
            raise AssertionError("gateway must not be called when there is no evidence")

    ans = compose_answer(
        request_id="r1", question="q", authorized_evidence=[], gateway=_Boom(), config_version=CONFIG
    )
    assert ans.outcome is Outcome.ABSTAINED
    assert ans.abstention.reason is AbstentionReason.INSUFFICIENT


def test_well_supported_draft_is_returned() -> None:
    ev = [_evidence("e1", "d1")]
    gw = _FakeGateway(_grounded_answer("r1", ["e1"]))
    ans = compose_answer(
        request_id="r1", question="q", authorized_evidence=ev, gateway=gw, config_version=CONFIG
    )
    assert ans.outcome is Outcome.ANSWERED
    assert ans.claims[0].citation.evidence_ids == ["e1"]


def test_hallucinated_citation_forces_abstention() -> None:
    ev = [_evidence("e1", "d1")]
    # Model cites evidence that is not in the authorized set.
    gw = _FakeGateway(_grounded_answer("r1", ["e-ghost"]))
    ans = compose_answer(
        request_id="r1", question="q", authorized_evidence=ev, gateway=gw, config_version=CONFIG
    )
    assert ans.outcome is Outcome.ABSTAINED
    assert ans.abstention.reason is AbstentionReason.INSUFFICIENT


def test_gateway_error_abstains_unavailable() -> None:
    ev = [_evidence("e1", "d1")]
    gw = _FakeGateway(error=True)
    ans = compose_answer(
        request_id="r1", question="q", authorized_evidence=ev, gateway=gw, config_version=CONFIG
    )
    assert ans.outcome is Outcome.ABSTAINED
    assert ans.abstention.reason is AbstentionReason.UNAVAILABLE


def test_undisclosed_conflict_abstains_conflicting() -> None:
    ev = [
        _evidence("e1", "docA:v1", {"scope": ["pump-7"], "position": "replace"}),
        _evidence("e2", "docA:v2", {"scope": ["pump-7"], "position": "repair"}),
    ]
    gw = _FakeGateway(_grounded_answer("r1", ["e1"]))  # no conflict disclosed
    ans = compose_answer(
        request_id="r1", question="q", authorized_evidence=ev, gateway=gw, config_version=CONFIG
    )
    assert ans.outcome is Outcome.ABSTAINED
    assert ans.abstention.reason is AbstentionReason.CONFLICTING


def test_disclosed_conflict_is_returned() -> None:
    ev = [
        _evidence("e1", "docA:v1", {"scope": ["pump-7"], "position": "replace"}),
        _evidence("e2", "docA:v2", {"scope": ["pump-7"], "position": "repair"}),
    ]
    draft = _grounded_answer("r1", ["e1"], conflicts=[Conflict(description="replace vs repair")])
    gw = _FakeGateway(draft)
    ans = compose_answer(
        request_id="r1", question="q", authorized_evidence=ev, gateway=gw, config_version=CONFIG
    )
    assert ans.outcome is Outcome.ANSWERED
