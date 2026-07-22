"""FastAPI application for the Industrial Knowledge Intelligence Platform.

This is the runnable surface over the tested core. It wires the identity boundary, the
retrieval pipeline, and the ACL sync layer into HTTP endpoints:

    POST /search        authorized evidence for a query (head only; no model call)
    POST /answer        grounded answer or safe abstention (full pipeline)
    POST /admin/acl/revoke   revoke a document's ACL (demonstrates live revocation)
    GET  /healthz       liveness

SECURITY: identity here is a DEV STUB (see identity.py). It trusts request headers instead
of verifying a signed token, so it must never run outside local development. Every other
guarantee — authorize-before-retrieval, freshness fail-closed, claim validation — is the
real implementation from the core packages; only identity verification is faked.
"""
from __future__ import annotations

import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from ikip_authz import AuthorizationContext
from ikip_authz.sync import AclEvent, EventType, apply_event
from ikip_contracts import Answer, Outcome
from ikip_retrieval.pipeline.assemble_evidence import assemble
from ikip_retrieval.pipeline.merge_rerank import merge_and_rank
from ikip_retrieval.pipeline.run import run_query
from ikip_retrieval.pipeline.types import RetrievalQuery

from ikip_api.identity import dev_identity
from ikip_api.schemas import (
    EvidenceView,
    QueryRequest,
    RevokeRequest,
    RevokeResponse,
    SearchResponse,
)
from ikip_api.services import Services, build_services


def create_app(services: Services | None = None) -> FastAPI:
    """Build the app. Pass `services` in tests; otherwise the dev composition is built."""
    svc = services or build_services()
    app = FastAPI(
        title="Industrial Knowledge Intelligence Platform — API (dev)",
        version="0.0.0",
        description="Decision-support only. Never controls equipment. Dev identity is stubbed.",
    )
    app.state.services = svc

    @app.exception_handler(PermissionError)
    def _on_permission_error(_request: Request, _exc: PermissionError) -> JSONResponse:
        """An unverified/again-invalid authorization context must be a clean 403.

        The message is deliberately generic so it never reveals whether content exists.
        """
        return JSONResponse(status_code=403, content={"detail": "Not authorized."})

    def _query(req: QueryRequest) -> RetrievalQuery:
        return RetrievalQuery(
            question=req.question,
            asset_ids=frozenset(req.asset_ids),
            sites=frozenset(req.sites),
        )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/search", response_model=SearchResponse)
    def search(req: QueryRequest, ctx: AuthorizationContext = Depends(dev_identity)) -> SearchResponse:
        """Run the retrieval head only: authorize -> channels -> filter -> rank -> assemble.

        Returns the authorized evidence with no model call. Restricted content the caller
        may not see is filtered before ranking and never appears here.
        """
        results = [ch.search(_query(req), limit=50) for ch in svc.channels]
        ranked = merge_and_rank(ctx, results)
        evidence = assemble(ranked)
        return SearchResponse(
            evidence=[EvidenceView.from_evidence(e) for e in evidence],
            count=len(evidence),
        )

    @app.post("/answer", response_model=Answer)
    def answer(req: QueryRequest, ctx: AuthorizationContext = Depends(dev_identity)) -> Answer:
        """Run the full pipeline and return a grounded answer or a safe abstention.

        The domain Answer is returned unchanged — the API never reshapes it, so the client
        consumes exactly what the pipeline produced and validated.
        """
        return run_query(
            request_id=str(uuid.uuid4()),
            ctx=ctx,
            query=_query(req),
            channels=svc.channels,
            gateway=svc.gateway,
            config_version=svc.config_version,
        )

    @app.post("/admin/acl/revoke", response_model=RevokeResponse)
    def revoke_acl(req: RevokeRequest, ctx: AuthorizationContext = Depends(dev_identity)) -> RevokeResponse:
        """Revoke a document's ACL via the sync layer, then confirm it is gone.

        Demonstrates that revocation takes effect immediately with no reindexing: a
        subsequent /search or /answer for that document abstains or omits it.
        """
        apply_event(svc.acl_store, AclEvent(type=EventType.REVOKE, document_id=req.document_id))
        return RevokeResponse(
            document_id=req.document_id,
            revoked=svc.acl_store.get(req.document_id) is None,
        )

    return app


# Module-level app for `uvicorn ikip_api.app:app`.
app = create_app()

# Re-exported for tests that want to assert on outcomes without importing contracts.
__all__ = ["app", "create_app", "Outcome"]
