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
from typing import Annotated

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse, Response
from ikip_authz import AuthorizationContext, evaluate_document
from ikip_authz.sync import AclEvent, EventType, apply_event
from ikip_contracts import Answer, Outcome
from ikip_retrieval.pipeline.assemble_evidence import assemble
from ikip_retrieval.pipeline.authorize import gate_request
from ikip_retrieval.pipeline.merge_rerank import merge_and_rank
from ikip_retrieval.pipeline.run import run_query
from ikip_retrieval.pipeline.types import RetrievalQuery

from ikip_api.identity import development_identity
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
        version="0.1.0-pilot",
        description=(
            "Decision-support only. Pilot uses explicitly enabled, insecure "
            "development identity; no production token verifier is included."
        ),
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
    def search(
        req: QueryRequest, ctx: Annotated[AuthorizationContext, Depends(development_identity)]
    ) -> SearchResponse:
        """Run the retrieval head only: authorize -> channels -> filter -> rank -> assemble.

        Returns the authorized evidence with no model call. Restricted content the caller
        may not see is filtered before ranking and never appears here.
        """
        # Gate the request before any channel observes the query.  Filtering in
        # merge_and_rank is defense in depth, not a substitute for this boundary.
        if not gate_request(ctx).allowed:
            raise HTTPException(status_code=403, detail="Not authorized.")
        results = [ch.search(_query(req), limit=50) for ch in svc.channels]
        ranked = merge_and_rank(ctx, results)
        evidence = assemble(ranked)
        return SearchResponse(
            evidence=[EvidenceView.from_evidence(e) for e in evidence],
            count=len(evidence),
        )

    @app.post("/answer", response_model=Answer, response_model_exclude_none=True)
    def answer(
        req: QueryRequest, ctx: Annotated[AuthorizationContext, Depends(development_identity)]
    ) -> Answer:
        """Run the full pipeline and return a grounded answer or a safe abstention.

        The validated domain Answer is serialized with unset optional fields omitted, matching
        the authoritative static JSON Schema contract.
        """
        return run_query(
            request_id=str(uuid.uuid4()),
            ctx=ctx,
            query=_query(req),
            channels=svc.channels,
            gateway=svc.gateway,
            config_version=svc.config_version,
        )

    def _authorized_document(document_id: str, ctx: AuthorizationContext):
        ctx.require_verified()
        doc = svc.upload_repository.get(document_id) if svc.upload_repository else None
        acl = svc.acl_store.get(document_id)
        if doc is None or acl is None or not evaluate_document(ctx, acl).allowed:
            raise HTTPException(status_code=404, detail="Document not found.")
        return doc

    @app.post("/documents", status_code=status.HTTP_202_ACCEPTED, tags=["uploads"])
    async def upload_document(
        background: BackgroundTasks,
        ctx: Annotated[AuthorizationContext, Depends(development_identity)],
        file: UploadFile = File(...),  # noqa: B008
        sites: str | None = Form(None),
        roles: str | None = Form(None),
    ) -> dict:
        ctx.require_verified()
        if not svc.uploads:
            raise HTTPException(status_code=503, detail="Upload service unavailable.")
        selected_sites = sorted(
            {x.strip() for x in (sites or ",".join(ctx.sites)).split(",") if x.strip()}
        )
        selected_roles = sorted(
            {x.strip() for x in (roles or ",".join(ctx.roles)).split(",") if x.strip()}
        )
        if (
            not selected_sites
            or not selected_roles
            or not set(selected_sites) <= set(ctx.sites)
            or not set(selected_roles) <= set(ctx.roles)
        ):
            raise HTTPException(status_code=403, detail="Upload ACL must be within caller scope.")
        chunks = []
        total = 0
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > svc.uploads.max_bytes:
                raise HTTPException(status_code=413, detail="Upload exceeds configured size limit.")
            chunks.append(chunk)
        try:
            doc = svc.uploads.accept(
                file.filename,
                file.content_type,
                b"".join(chunks),
                ctx.subject_id,
                selected_sites,
                selected_roles,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        background.add_task(svc.uploads.process, doc.document_id)
        return doc.public()

    @app.get("/documents", tags=["uploads"])
    def list_documents(ctx: Annotated[AuthorizationContext, Depends(development_identity)]) -> dict:
        # Do not even enumerate document metadata until identity verification succeeds.
        ctx.require_verified()
        docs = svc.upload_repository.list() if svc.upload_repository else []
        visible = [
            d.public()
            for d in docs
            if (acl := svc.acl_store.get(d.document_id)) is not None
            and evaluate_document(ctx, acl).allowed
        ]
        return {"documents": visible, "count": len(visible)}

    @app.get("/documents/{document_id}", tags=["uploads"])
    def document_status(
        document_id: str, ctx: Annotated[AuthorizationContext, Depends(development_identity)]
    ) -> dict:
        return _authorized_document(document_id, ctx).public()

    @app.get("/documents/{document_id}/content", tags=["uploads"])
    def document_content(
        document_id: str, ctx: Annotated[AuthorizationContext, Depends(development_identity)]
    ) -> Response:
        doc = _authorized_document(document_id, ctx)
        if not svc.object_store:
            raise HTTPException(status_code=503, detail="Object store unavailable.")
        return Response(
            content=svc.object_store.get(doc.object_key),
            media_type=doc.media_type,
            headers={
                "Content-Disposition": f'inline; filename="{doc.filename}"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.post("/admin/acl/revoke", response_model=RevokeResponse)
    def revoke_acl(
        req: RevokeRequest, ctx: Annotated[AuthorizationContext, Depends(development_identity)]
    ) -> RevokeResponse:
        """Revoke a document's ACL via the sync layer, then confirm it is gone.

        Demonstrates that revocation takes effect immediately with no reindexing: a
        subsequent /search or /answer for that document abstains or omits it.
        """
        ctx.require_verified()
        if "admin" not in ctx.roles:
            raise PermissionError("ACL revocation requires the admin role.")
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
