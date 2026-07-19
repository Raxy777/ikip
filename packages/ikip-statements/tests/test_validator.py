"""The validator is the gate between an LLM draft and the user. Test the failure modes
hardest: a claim that cites nothing, a fabricated evidence ID, and a hidden conflict must
all block the answer.
"""
from __future__ import annotations

from ikip_contracts import (
    Abstention,
    AbstentionReason,
    Answer,
    Authority,
    Citation,
    Claim,
    Evidence,
    Outcome,
    ProcessingVersions,
    Provenance,
    StatementClass,
)

from ikip_statements import ViolationCode, validate_answer


def _evidence(eid: str, doc: str, *, authority=Authority.APPROVED, applicability=None) -> Evidence:
    pv = ProcessingVersions(parser="p@1", chunker="c@1", embedding_model="e@1")
    prov = Provenance(source_document_id=doc, source_revision="r1", processing_versions=pv)
    return Evidence(
        evidence_id=eid,
        document_id=doc,
        text="text",
        provenance=prov,
        authority=authority,
        applicability=applicability or {},
    )


def _answer(claims, conflicts=None) -> Answer:
    return Answer(
        request_id="rq",
        outcome=Outcome.ANSWERED,
        config_version="cfg@1",
        claims=claims,
        conflicts=conflicts,
    )


def _claim(cid: str, evidence_ids, sc=StatementClass.HISTORICAL_OBSERVATION) -> Claim:
    return Claim(
        claim_id=cid,
        text="a claim",
        citation=Citation(claim_id=cid, evidence_ids=evidence_ids, statement_class=sc),
    )


def test_well_supported_answer_passes() -> None:
    ev = [_evidence("e1", "d1")]
    ans = _answer([_claim("c1", ["e1"])])
    assert validate_answer(ans, ev).ok


def test_fabricated_evidence_id_blocks() -> None:
    ev = [_evidence("e1", "d1")]
    ans = _answer([_claim("c1", ["e-does-not-exist"])])
    result = validate_answer(ans, ev)
    assert not result.ok
    assert any(v.code is ViolationCode.UNKNOWN_EVIDENCE_ID for v in result.violations)


def test_citation_to_unauthorized_evidence_blocks() -> None:
    # e2 exists in reality but was NOT in the authorized set handed to the validator.
    authorized = [_evidence("e1", "d1")]
    ans = _answer([_claim("c1", ["e2"])])
    result = validate_answer(ans, authorized)
    assert not result.ok
    assert any(v.code is ViolationCode.UNKNOWN_EVIDENCE_ID for v in result.violations)


def test_abstention_always_passes() -> None:
    ans = Answer(
        request_id="rq",
        outcome=Outcome.ABSTAINED,
        config_version="cfg@1",
        abstention=Abstention(reason=AbstentionReason.INSUFFICIENT, message="No accessible evidence."),
    )
    assert validate_answer(ans, []).ok


def test_undisclosed_conflict_blocks() -> None:
    # Two current-guidance sources, same scope, opposing positions, no conflict disclosed.
    ev = [
        _evidence("e1", "docA:v1", applicability={"scope": ["pump-7"], "position": "replace"}),
        _evidence("e2", "docA:v2", applicability={"scope": ["pump-7"], "position": "repair"}),
    ]
    ans = _answer([_claim("c1", ["e1"])])
    result = validate_answer(ans, ev)
    assert not result.ok
    assert any(v.code is ViolationCode.UNDISCLOSED_CONFLICT for v in result.violations)


def test_disclosed_conflict_passes() -> None:
    from ikip_contracts import Conflict

    ev = [
        _evidence("e1", "docA:v1", applicability={"scope": ["pump-7"], "position": "replace"}),
        _evidence("e2", "docA:v2", applicability={"scope": ["pump-7"], "position": "repair"}),
    ]
    ans = _answer(
        [_claim("c1", ["e1"])],
        conflicts=[Conflict(description="Sources disagree: replace vs repair.")],
    )
    assert validate_answer(ans, ev).ok
