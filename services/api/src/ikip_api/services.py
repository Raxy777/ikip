"""Composition root for the API service — builds the stores, adapters, and gateway.

This is the ONE place concrete implementations are chosen and wired. Swapping the
in-memory store for a durable one, or the dev gateway for the real Model Gateway, happens
here without touching route handlers or the pipeline. Everything below the ports stays put.

The dev profile seeds a tiny demo corpus across two sites and two authority states so the
authorization, freshness, ranking, and abstention behaviours are all exercisable from a
running server. The seed data is obviously synthetic and lives only in memory.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ikip_authz.sync import AclStore, InMemoryAclStore
from ikip_contracts import AclPolicy
from ikip_retrieval.adapters.exact_index import ExactIndex, ExactRecord
from ikip_retrieval.adapters.lexical_index import IndexedChunk, LexicalIndex
from ikip_retrieval.pipeline.search_shape import ShapeSearchChannel
from ikip_retrieval.ports.answer_gateway import AnswerGateway
from ikip_retrieval.ports.search_channel import SearchChannel
from ikip_retrieval.ports.shape_store import InMemoryShapeStore, ShapeRecord

from ikip_api.dev_gateway import DevAnswerGateway
from ikip_api.uploads import ObjectStore, Repository, UploadManager, build_persistence


@dataclass
class Services:
    """The wired-together dependencies a request handler needs."""

    acl_store: AclStore
    channels: list[SearchChannel]
    gateway: AnswerGateway
    config_version: str
    uploads: UploadManager | None = None
    upload_repository: Repository | None = None
    object_store: ObjectStore | None = None


def _now_iso() -> datetime:
    return datetime.now(UTC)


def _seed_acls(store: AclStore) -> None:
    """Seed fresh, in-scope ACLs so seeded documents are actually authorizable."""
    now = _now_iso()
    store.upsert(
        AclPolicy(
            document_id="pump-manual",
            owner="reliability",
            sites=["site-a"],
            roles_allowed=["engineer", "technician"],
            source_of_truth="dev-seed",
            synced_at=now,
            max_staleness_seconds=86_400,
        )
    )
    store.upsert(
        AclPolicy(
            document_id="valve-procedure",
            owner="operations",
            sites=["site-a"],
            roles_allowed=["engineer"],
            source_of_truth="dev-seed",
            synced_at=now,
            max_staleness_seconds=86_400,
        )
    )
    # Restricted to site-b only: a site-a user must never see this surface.
    store.upsert(
        AclPolicy(
            document_id="restricted-incident",
            owner="safety",
            sites=["site-b"],
            roles_allowed=["engineer"],
            source_of_truth="dev-seed",
            synced_at=now,
            max_staleness_seconds=86_400,
        )
    )


def _seed_indexes(
    acl_store: AclStore,
) -> tuple[list[SearchChannel], ExactIndex, LexicalIndex, InMemoryShapeStore]:
    lexical = LexicalIndex(acl_store)
    exact = ExactIndex(acl_store)

    lexical.add(
        IndexedChunk(
            evidence_id="ev-pump-1",
            document_id="pump-manual",
            text="Pump P-101 requires seal inspection every 2000 operating hours.",
        )
    )
    lexical.add(
        IndexedChunk(
            evidence_id="ev-valve-1",
            document_id="valve-procedure",
            text="Isolation valve V-12 must be locked out before maintenance begins.",
        )
    )
    lexical.add(
        IndexedChunk(
            evidence_id="ev-restricted-1",
            document_id="restricted-incident",
            text="Confidential incident detail restricted to site-b personnel only.",
        )
    )

    exact.add(
        ExactRecord(
            evidence_id="ev-pump-1",
            document_id="pump-manual",
            text="Pump P-101 requires seal inspection every 2000 operating hours.",
            identifiers=("P-101",),
        )
    )
    exact.add(
        ExactRecord(
            evidence_id="ev-valve-1",
            document_id="valve-procedure",
            text="Isolation valve V-12 must be locked out before maintenance begins.",
            identifiers=("V-12",),
        )
    )
    shape_store = InMemoryShapeStore()
    shape_channel = ShapeSearchChannel(shape_store, acl_store)
    return [exact, lexical, shape_channel], exact, lexical, shape_store


def build_services(config_version: str = "dev-0") -> Services:
    """Build the dev composition. Seeds a synthetic in-memory corpus."""
    acl_store = InMemoryAclStore()
    _seed_acls(acl_store)
    channels, exact, lexical, shape_store = _seed_indexes(acl_store)
    repo, objects = build_persistence()

    def index_text(document_id: str, evidence_id: str, text: str) -> None:
        lexical.add(IndexedChunk(evidence_id=evidence_id, document_id=document_id, text=text))
        exact.add(
            ExactRecord(evidence_id=evidence_id, document_id=document_id, text=text, identifiers=())
        )

    def index_shape(document_id: str, part_id: str, descriptor: list[float]) -> None:
        shape_store.add(
            ShapeRecord(
                evidence_id=f"shape-{part_id}",
                document_id=document_id,
                part_id=part_id,
                descriptor=descriptor,
            )
        )

    # A durable process restart rehydrates ACLs and derived indexes before serving queries.
    for doc in repo.list():
        acl_store.upsert(
            AclPolicy(
                document_id=doc.document_id,
                owner=doc.owner,
                sites=doc.sites,
                roles_allowed=doc.roles,
                source_of_truth="upload",
                synced_at=_now_iso(),
                max_staleness_seconds=31536000,
            )
        )
    for document_id, chunk_id, text in repo.iter_chunks():
        index_text(document_id, chunk_id, text)
    for document_id, part_id, descriptor in repo.iter_shapes():
        index_shape(document_id, part_id, descriptor)
    manager = UploadManager(repo, objects, index_text, index_shape, acl_store)
    return Services(
        acl_store=acl_store,
        channels=channels,
        gateway=DevAnswerGateway(),
        config_version=config_version,
        uploads=manager,
        upload_repository=repo,
        object_store=objects,
    )
