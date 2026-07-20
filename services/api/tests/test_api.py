"""End-to-end API tests over the wired dev composition.

These drive the real pipeline through HTTP: authorize-before-retrieval, freshness, ranking,
claim validation, and abstention are all exercised. Only identity is stubbed. The
security-relevant assertions are that restricted content never surfaces to an
unauthorized caller and that revocation takes effect immediately.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Dev auth must be enabled before the app's identity dependency is exercised.
os.environ["IKIP_DEV_AUTH"] = "1"

from ikip_api.app import create_app  # noqa: E402
from ikip_api.services import build_services  # noqa: E402


def _client() -> TestClient:
    return TestClient(create_app(build_services()))


# An engineer at site-a: sees the two site-a documents, never the site-b incident.
_SITE_A_ENG = {"X-Dev-Subject": "eng-a", "X-Dev-Roles": "engineer", "X-Dev-Sites": "site-a"}
# A technician at site-a: allowed the pump manual, not the valve procedure (engineer-only).
_SITE_A_TECH = {"X-Dev-Subject": "tech-a", "X-Dev-Roles": "technician", "X-Dev-Sites": "site-a"}


def test_healthz() -> None:
    assert _client().get("/healthz").json() == {"status": "ok"}


def test_search_returns_authorized_evidence() -> None:
    r = _client().post("/search", json={"question": "pump P-101 seal inspection"}, headers=_SITE_A_ENG)
    assert r.status_code == 200
    ids = {e["evidence_id"] for e in r.json()["evidence"]}
    assert "ev-pump-1" in ids


def test_search_never_surfaces_restricted_content() -> None:
    # Ask directly for the restricted content; a site-a engineer must get nothing back.
    r = _client().post(
        "/search",
        json={"question": "confidential incident detail restricted personnel"},
        headers=_SITE_A_ENG,
    )
    assert r.status_code == 200
    ids = {e["evidence_id"] for e in r.json()["evidence"]}
    assert "ev-restricted-1" not in ids


def test_role_scoping_within_a_site() -> None:
    # Technician is not permitted the engineer-only valve procedure.
    r = _client().post("/search", json={"question": "isolation valve V-12 lockout"}, headers=_SITE_A_TECH)
    ids = {e["evidence_id"] for e in r.json()["evidence"]}
    assert "ev-valve-1" not in ids


def test_answer_grounded_and_cited() -> None:
    r = _client().post("/answer", json={"question": "pump P-101 seal inspection"}, headers=_SITE_A_ENG)
    body = r.json()
    assert body["outcome"] == "answered"
    cited = {eid for c in body["claims"] for eid in c["citation"]["evidence_ids"]}
    assert cited <= {"ev-pump-1", "ev-valve-1"}  # only authorized evidence cited
    assert "ev-restricted-1" not in cited


def test_answer_abstains_when_no_evidence() -> None:
    r = _client().post("/answer", json={"question": "something entirely unrelated xyz"}, headers=_SITE_A_ENG)
    body = r.json()
    assert body["outcome"] == "abstained"
    assert body["abstention"]["reason"] == "insufficient"


def test_answer_hallucination_is_blocked() -> None:
    # Dev gateway cites a fabricated evidence id; the validator must force abstention.
    r = _client().post("/answer", json={"question": "pump P-101 [[hallucinate]]"}, headers=_SITE_A_ENG)
    body = r.json()
    assert body["outcome"] == "abstained"
    assert body["abstention"]["reason"] == "insufficient"


def test_answer_gateway_outage_degrades_gracefully() -> None:
    r = _client().post("/answer", json={"question": "pump P-101 [[boom]]"}, headers=_SITE_A_ENG)
    body = r.json()
    assert body["outcome"] == "abstained"
    assert body["abstention"]["reason"] == "unavailable"


def test_revocation_takes_effect_immediately() -> None:
    client = _client()
    q = {"question": "pump P-101 seal inspection"}
    # Present before revocation.
    before = client.post("/answer", json=q, headers=_SITE_A_ENG).json()
    assert before["outcome"] == "answered"
    # Revoke, then the same query must abstain with no reindexing.
    rev = client.post("/admin/acl/revoke", json={"document_id": "pump-manual"}, headers=_SITE_A_ENG)
    assert rev.json()["revoked"] is True
    after = client.post("/answer", json=q, headers=_SITE_A_ENG).json()
    assert after["outcome"] == "abstained"


def test_no_roles_is_denied_scope() -> None:
    # A verified user with no roles fails scope authorization -> safe abstention.
    r = _client().post(
        "/answer",
        json={"question": "pump P-101"},
        headers={"X-Dev-Subject": "nobody", "X-Dev-Sites": "site-a"},
    )
    assert r.json()["outcome"] == "abstained"


def test_unverified_identity_is_rejected() -> None:
    # Simulate an unverified token: the pipeline must refuse rather than serve.
    headers = {**_SITE_A_ENG, "X-Dev-Verified": "0"}
    r = _client().post("/answer", json={"question": "pump P-101"}, headers=headers)
    # require_verified() raises PermissionError inside the pipeline -> 500-class, not a leak.
    assert r.status_code >= 400


def test_dev_auth_flag_gates_access(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IKIP_DEV_AUTH", raising=False)
    r = _client().post("/answer", json={"question": "pump P-101"}, headers=_SITE_A_ENG)
    assert r.status_code == 501
