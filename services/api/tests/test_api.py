"""End-to-end API tests over the wired dev composition.

These drive the real pipeline through HTTP: authorize-before-retrieval, freshness, ranking,
claim validation, and abstention are all exercised. Only identity is stubbed. The
security-relevant assertions are that restricted content never surfaces to an
unauthorized caller and that revocation takes effect immediately.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

# Dev auth must be enabled before the app's identity dependency is exercised.
os.environ["IKIP_ENV"] = "development"
os.environ["IKIP_DEV_AUTH"] = "1"

from ikip_api.app import create_app  # noqa: E402
from ikip_api.services import build_services  # noqa: E402


def _client() -> TestClient:
    return TestClient(create_app(build_services()))


_REPOSITORY = Path(__file__).resolve().parents[3]
_SCHEMA_DIRECTORY = _REPOSITORY / "contracts" / "schemas"
_SCHEMAS = [
    json.loads(path.read_text(encoding="utf-8")) for path in _SCHEMA_DIRECTORY.glob("*.json")
]
_SCHEMA_REGISTRY = Registry().with_resources(
    (schema["$id"], Resource.from_contents(schema)) for schema in _SCHEMAS
)
_ANSWER_VALIDATOR = Draft202012Validator(
    next(schema for schema in _SCHEMAS if schema["title"] == "Answer"),
    registry=_SCHEMA_REGISTRY,
)


def _assert_static_answer_contract(payload: dict[str, Any]) -> None:
    """Validate a real HTTP payload against the separately authored static contract."""
    _ANSWER_VALIDATOR.validate(payload)


# An engineer at site-a: sees the two site-a documents, never the site-b incident.
_SITE_A_ENG = {"X-Dev-Subject": "eng-a", "X-Dev-Roles": "engineer", "X-Dev-Sites": "site-a"}
# A technician at site-a: allowed the pump manual, not the valve procedure (engineer-only).
_SITE_A_TECH = {"X-Dev-Subject": "tech-a", "X-Dev-Roles": "technician", "X-Dev-Sites": "site-a"}
_ADMIN = {"X-Dev-Subject": "admin-a", "X-Dev-Roles": "admin", "X-Dev-Sites": "site-a"}


def test_healthz() -> None:
    assert _client().get("/healthz").json() == {"status": "ok"}


def test_static_and_generated_docs_require_explicit_dev_identity_headers() -> None:
    static = yaml.safe_load(
        (_REPOSITORY / "contracts" / "openapi" / "api.v1.yaml").read_text(encoding="utf-8")
    )
    assert static["paths"]["/answer"]["post"]["security"] == [
        {"devSubject": [], "devRoles": [], "devSites": []}
    ]

    generated = _client().get("/openapi.json").json()
    parameters = generated["paths"]["/answer"]["post"]["parameters"]
    required_headers = {item["name"].lower() for item in parameters if item.get("required")}
    assert {"x-dev-subject", "x-dev-roles", "x-dev-sites"} <= required_headers


def test_search_returns_authorized_evidence() -> None:
    r = _client().post(
        "/search", json={"question": "pump P-101 seal inspection"}, headers=_SITE_A_ENG
    )
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
    r = _client().post(
        "/search", json={"question": "isolation valve V-12 lockout"}, headers=_SITE_A_TECH
    )
    ids = {e["evidence_id"] for e in r.json()["evidence"]}
    assert "ev-valve-1" not in ids


def test_answer_grounded_and_cited() -> None:
    r = _client().post(
        "/answer", json={"question": "pump P-101 seal inspection"}, headers=_SITE_A_ENG
    )
    body = r.json()
    assert body["outcome"] == "answered"
    _assert_static_answer_contract(body)
    assert "abstention" not in body and "conflicts" not in body
    cited = {eid for c in body["claims"] for eid in c["citation"]["evidence_ids"]}
    assert cited <= {"ev-pump-1", "ev-valve-1"}  # only authorized evidence cited
    assert "ev-restricted-1" not in cited


def test_answer_abstains_when_no_evidence() -> None:
    r = _client().post(
        "/answer", json={"question": "something entirely unrelated xyz"}, headers=_SITE_A_ENG
    )
    body = r.json()
    assert body["outcome"] == "abstained"
    _assert_static_answer_contract(body)
    assert "claims" not in body and "conflicts" not in body
    assert body["abstention"]["reason"] == "insufficient"


def test_answer_hallucination_is_blocked() -> None:
    # Dev gateway cites a fabricated evidence id; the validator must force abstention.
    r = _client().post(
        "/answer", json={"question": "pump P-101 [[hallucinate]]"}, headers=_SITE_A_ENG
    )
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
    denied = client.post(
        "/admin/acl/revoke", json={"document_id": "pump-manual"}, headers=_SITE_A_ENG
    )
    assert denied.status_code == 403
    assert client.post("/answer", json=q, headers=_SITE_A_ENG).json()["outcome"] == "answered"

    rev = client.post("/admin/acl/revoke", json={"document_id": "pump-manual"}, headers=_ADMIN)
    assert rev.status_code == 200
    assert rev.json()["revoked"] is True
    after = client.post("/answer", json=q, headers=_SITE_A_ENG).json()
    assert after["outcome"] == "abstained"


@pytest.mark.parametrize("missing", ["X-Dev-Subject", "X-Dev-Roles", "X-Dev-Sites"])
def test_every_identity_header_is_required(missing: str) -> None:
    headers = dict(_SITE_A_ENG)
    del headers[missing]
    r = _client().post("/answer", json={"question": "pump P-101"}, headers=headers)
    assert r.status_code == 422


def test_protected_request_never_synthesizes_identity() -> None:
    r = _client().post("/search", json={"question": "pump P-101"})
    assert r.status_code == 422


def test_blank_identity_scope_is_rejected() -> None:
    headers = {**_SITE_A_ENG, "X-Dev-Roles": "   "}
    r = _client().post("/answer", json={"question": "pump P-101"}, headers=headers)
    assert r.status_code == 400


def test_unverified_identity_is_rejected() -> None:
    # Simulate an unverified token: the pipeline must refuse rather than serve.
    headers = {**_SITE_A_ENG, "X-Dev-Verified": "0"}
    r = _client().post("/answer", json={"question": "pump P-101"}, headers=headers)
    assert r.status_code == 403


def test_dev_auth_flag_gates_access(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IKIP_DEV_AUTH", raising=False)
    r = _client().post("/answer", json={"question": "pump P-101"}, headers=_SITE_A_ENG)
    assert r.status_code == 503


def test_dev_auth_is_rejected_outside_development_even_with_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IKIP_ENV", "production")
    monkeypatch.setenv("IKIP_DEV_AUTH", "1")
    r = _client().post("/answer", json={"question": "pump P-101"}, headers=_SITE_A_ENG)
    assert r.status_code == 503
    assert "production identity verifier" in r.json()["detail"]


def test_unverified_admin_cannot_revoke() -> None:
    headers = {**_ADMIN, "X-Dev-Verified": "0"}
    r = _client().post("/admin/acl/revoke", json={"document_id": "pump-manual"}, headers=headers)
    assert r.status_code == 403


class _CountingChannel:
    def __init__(self) -> None:
        self.calls = 0

    def search(self, query: object, *, limit: int) -> list[object]:
        self.calls += 1
        return []


class _CountingRepository:
    def __init__(self) -> None:
        self.list_calls = 0

    def list(self) -> list[object]:
        self.list_calls += 1
        return []


def test_search_gates_unverified_and_invalid_scope_before_channels() -> None:
    from ikip_api.identity import development_identity
    from ikip_authz import AuthorizationContext

    for context in (
        AuthorizationContext(subject_id="unverified", roles=frozenset({"engineer"})),
        AuthorizationContext(subject_id="no-roles", identity_verified=True),
    ):
        services = build_services()
        channel = _CountingChannel()
        services.channels = [channel]  # type: ignore[assignment]
        app = create_app(services)
        app.dependency_overrides[development_identity] = lambda context=context: context
        response = TestClient(app).post("/search", json={"question": "pump P-101"})
        assert response.status_code == 403
        assert channel.calls == 0


def test_list_documents_verifies_identity_before_repository_access() -> None:
    from ikip_api.identity import development_identity
    from ikip_authz import AuthorizationContext

    services = build_services()
    repository = _CountingRepository()
    services.upload_repository = repository  # type: ignore[assignment]
    app = create_app(services)
    app.dependency_overrides[development_identity] = lambda: AuthorizationContext(
        subject_id="unverified", roles=frozenset({"engineer"})
    )
    response = TestClient(app).get("/documents")
    assert response.status_code == 403
    assert repository.list_calls == 0
