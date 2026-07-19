"""Live lexical BM25 adapter, standalone and through the full pipeline.

Covers real ranking (term relevance, rarer terms weigh more), the fail-closed behaviour
when a document has no ACL, and — the connective test — that a REVOKE applied via the sync
layer immediately drops content from `run_query` results without reindexing.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ikip_authz import (
    AclEvent,
    AuthorizationContext,
    EventType,
    InMemoryAclStore,
    apply_event,
    reconcile,
)
from ikip_contracts import AclPolicy, Answer, Citation, Claim, Outcome, StatementClass

from ikip_retrieval.adapters import IndexedChunk, LexicalIndex
from ikip_retrieval.pipeline.run import run_query
from ikip_retrieval.pipeline.types import RetrievalQuery


def _acl(doc, *, sites=("site-a",), roles=("eng",)) -> AclPolicy:
    return AclPolicy(
        document_id=doc,
        owner="o",
        sites=list(sites),
        roles_allowed=list(roles),
        source_of_truth="edms",
        max_staleness_seconds=3600,
    )


def _ctx() -> AuthorizationContext:
    return AuthorizationContext(
        subject_id="u1",
        roles=frozenset({"eng"}),
        sites=frozenset({"site-a"}),
        identity_verified=True,
    )


class _FakeSource:
    def __init__(self, acls):
        self._acls = list(acls)

    def set(self, acls):
        self._acls = list(acls)

    def fetch_current(self):
        return list(self._acls)


class _EchoGateway:
    def synthesize(self, *, request_id, question, evidence, config_version) -> Answer:
        first = evidence[0]
        claim = Claim(
            claim_id="c1",
            text="grounded",
            citation=Citation(
                claim_id="c1", evidence_ids=[first.evidence_id], statement_class=StatementClass.HISTORICAL_OBSERVATION
            ),
        )
        return Answer(
            request_id=request_id, outcome=Outcome.ANSWERED, config_version=config_version, claims=[claim]
        )


def _index(store) -> LexicalIndex:
    idx = LexicalIndex(store)
    idx.add(IndexedChunk("e1", "d1", "the centrifugal pump tripped on high vibration"))
    idx.add(IndexedChunk("e2", "d2", "routine lubrication schedule for the gearbox"))
    idx.add(IndexedChunk("e3", "d3", "vibration analysis of the compressor bearing"))
    return idx


def test_bm25_ranks_relevant_first() -> None:
    store = InMemoryAclStore()
    idx = _index(store)
    results = idx.search(RetrievalQuery(question="pump vibration trip"), limit=10)
    assert results[0].evidence_id == "e1"
    # Every result must have scored > 0 on a query term.
    assert all(c.retrieval_score > 0 for c in results)
    # The lubrication doc shares no query terms -> not returned.
    assert "e2" not in [c.evidence_id for c in results]


def test_missing_acl_fails_closed() -> None:
    # No ACL in the store -> candidate carries no synced_at -> denied downstream.
    store = InMemoryAclStore()
    idx = _index(store)
    ans = run_query(
        request_id="r1",
        ctx=_ctx(),
        query=RetrievalQuery(question="pump vibration"),
        channels=[idx],
        gateway=_EchoGateway(),
        config_version="cfg@1",
    )
    assert ans.outcome is Outcome.ABSTAINED  # nothing authorized


def test_end_to_end_grounded_with_synced_acls() -> None:
    store = InMemoryAclStore()
    reconcile(_FakeSource([_acl("d1"), _acl("d2"), _acl("d3")]), store)
    idx = _index(store)
    ans = run_query(
        request_id="r1",
        ctx=_ctx(),
        query=RetrievalQuery(question="pump vibration trip"),
        channels=[idx],
        gateway=_EchoGateway(),
        config_version="cfg@1",
    )
    assert ans.outcome is Outcome.ANSWERED
    assert ans.claims[0].citation.evidence_ids == ["e1"]


def test_revocation_via_sync_drops_content_without_reindex() -> None:
    # d1 is the top hit. Revoke it upstream; the SAME index must stop returning it.
    store = InMemoryAclStore()
    reconcile(_FakeSource([_acl("d1")]), store)
    idx = _index(store)

    before = run_query(
        request_id="r1", ctx=_ctx(), query=RetrievalQuery(question="pump vibration trip"),
        channels=[idx], gateway=_EchoGateway(), config_version="cfg@1",
    )
    assert before.outcome is Outcome.ANSWERED

    # Revoke d1 via a push event — no reindexing.
    apply_event(store, AclEvent(EventType.REVOKE, "d1"))

    after = run_query(
        request_id="r2", ctx=_ctx(), query=RetrievalQuery(question="pump vibration trip"),
        channels=[idx], gateway=_EchoGateway(), config_version="cfg@1",
    )
    assert after.outcome is Outcome.ABSTAINED
