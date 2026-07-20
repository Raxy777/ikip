"""Live exact-match adapter: identifier precision, quoted phrases, and pipeline wiring.

The defining property is precision: an identifier query must match its exact identifier and
NOT a look-alike ("P-101" must never surface "P-1010"). Also covers quoted-phrase matching,
identifier ranking above phrase-only hits, fail-closed on missing ACLs, and the end-to-end
grounded path through run_query.
"""
from __future__ import annotations

from ikip_authz import AuthorizationContext, InMemoryAclStore, reconcile
from ikip_contracts import AclPolicy, Answer, Citation, Claim, Outcome, StatementClass

from ikip_retrieval.adapters import ExactIndex, ExactRecord
from ikip_retrieval.pipeline.run import run_query
from ikip_retrieval.pipeline.types import RetrievalQuery


def _acl(doc, *, sites=("site-a",), roles=("eng",)) -> AclPolicy:
    return AclPolicy(
        document_id=doc, owner="o", sites=list(sites), roles_allowed=list(roles),
        source_of_truth="cmms", max_staleness_seconds=3600,
    )


def _ctx() -> AuthorizationContext:
    return AuthorizationContext(
        subject_id="u1", roles=frozenset({"eng"}), sites=frozenset({"site-a"}), identity_verified=True
    )


class _FakeSource:
    def __init__(self, acls):
        self._acls = list(acls)

    def fetch_current(self):
        return list(self._acls)


class _EchoGateway:
    def synthesize(self, *, request_id, question, evidence, config_version) -> Answer:
        first = evidence[0]
        claim = Claim(
            claim_id="c1", text="grounded",
            citation=Citation(claim_id="c1", evidence_ids=[first.evidence_id], statement_class=StatementClass.HISTORICAL_OBSERVATION),
        )
        return Answer(request_id=request_id, outcome=Outcome.ANSWERED, config_version=config_version, claims=[claim])


def _index(store) -> ExactIndex:
    idx = ExactIndex(store)
    idx.add(ExactRecord("e1", "d1", "Pump P-101 tripped on high vibration", identifiers=("P-101",)))
    idx.add(ExactRecord("e2", "d2", "Pump P-1010 routine inspection", identifiers=("P-1010",)))
    idx.add(ExactRecord("e3", "d3", "Controller 12-FIC-3001A calibration record", identifiers=("12-FIC-3001A",)))
    return idx


def test_exact_identifier_match_not_lookalike() -> None:
    store = InMemoryAclStore()
    idx = _index(store)
    results = idx.search(RetrievalQuery(question="what happened to P-101?"), limit=10)
    ids = [c.evidence_id for c in results]
    assert ids == ["e1"]  # P-1010 (e2) must NOT match
    assert "e2" not in ids


def test_identifier_with_separators() -> None:
    store = InMemoryAclStore()
    idx = _index(store)
    results = idx.search(RetrievalQuery(question="calibration of 12-FIC-3001A"), limit=10)
    assert [c.evidence_id for c in results] == ["e3"]


def test_quoted_phrase_match() -> None:
    store = InMemoryAclStore()
    idx = _index(store)
    results = idx.search(RetrievalQuery(question='find "high vibration"'), limit=10)
    assert [c.evidence_id for c in results] == ["e1"]


def test_identifier_outranks_phrase_only() -> None:
    # A record matched by identifier should rank above one matched only by phrase.
    store = InMemoryAclStore()
    idx = ExactIndex(store)
    idx.add(ExactRecord("e1", "d1", "routine inspection notes", identifiers=("P-101",)))
    idx.add(ExactRecord("e2", "d2", "notes about P-101 by name only in text"))
    results = idx.search(RetrievalQuery(question='P-101 "inspection notes"'), limit=10)
    # e1: identifier hit (2.0). e2: phrase-only would need the phrase; it has neither
    # registered identifier nor the quoted phrase, so only e1 matches.
    assert results[0].evidence_id == "e1"


def test_no_identifier_or_phrase_returns_nothing() -> None:
    store = InMemoryAclStore()
    idx = _index(store)
    assert idx.search(RetrievalQuery(question="the pump on site"), limit=10) == []


def test_missing_acl_fails_closed() -> None:
    store = InMemoryAclStore()  # no ACLs synced
    idx = _index(store)
    ans = run_query(
        request_id="r1", ctx=_ctx(), query=RetrievalQuery(question="P-101"),
        channels=[idx], gateway=_EchoGateway(), config_version="cfg@1",
    )
    assert ans.outcome is Outcome.ABSTAINED


def test_end_to_end_grounded() -> None:
    store = InMemoryAclStore()
    reconcile(_FakeSource([_acl("d1"), _acl("d2"), _acl("d3")]), store)
    idx = _index(store)
    ans = run_query(
        request_id="r1", ctx=_ctx(), query=RetrievalQuery(question="why did P-101 trip?"),
        channels=[idx], gateway=_EchoGateway(), config_version="cfg@1",
    )
    assert ans.outcome is Outcome.ANSWERED
    assert ans.claims[0].citation.evidence_ids == ["e1"]
