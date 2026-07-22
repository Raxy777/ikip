"""Phase 3 shape-similarity channel tests (§C).

Covers:
  - D2 descriptor invariance: rotated/translated/scaled copy of a mesh scores near-identical
    cosine similarity to the original.
  - Shape candidates pass through merge_and_rank's evaluate_document filter: a restricted
    part (wrong site) never surfaces in the ranked set.
  - Reference-part upload → similar parts ranked above dissimilar ones.
  - Empty descriptor → channel returns nothing (graceful no-op).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest
from ikip_authz import AuthorizationContext
from ikip_authz.sync import InMemoryAclStore
from ikip_contracts import AclPolicy, RetrievalChannel
from ikip_retrieval.pipeline.merge_rerank import merge_and_rank
from ikip_retrieval.pipeline.search_shape import ShapeRetrievalQuery, ShapeSearchChannel
from ikip_retrieval.pipeline.types import RetrievalQuery
from ikip_retrieval.ports.shape_store import InMemoryShapeStore, ShapeRecord

# ---------------------------------------------------------------------------
# D2 descriptor helpers (inline — no ingestion dep in retrieval tests)
# ---------------------------------------------------------------------------


def _box_vertices(sx: float, sy: float, sz: float) -> list[tuple[float, float, float]]:
    return [
        (0, 0, 0),
        (sx, 0, 0),
        (sx, sy, 0),
        (0, sy, 0),
        (0, 0, sz),
        (sx, 0, sz),
        (sx, sy, sz),
        (0, sy, sz),
    ]


def _box_faces() -> list[tuple[int, int, int]]:
    return [
        (0, 1, 2),
        (0, 2, 3),
        (4, 6, 5),
        (4, 7, 6),
        (0, 5, 1),
        (0, 4, 5),
        (2, 6, 3),
        (3, 6, 7),
        (0, 3, 7),
        (0, 7, 4),
        (1, 5, 6),
        (1, 6, 2),
    ]


def _translate(verts, dx, dy, dz):
    return [(x + dx, y + dy, z + dz) for x, y, z in verts]


def _scale(verts, s):
    return [(x * s, y * s, z * s) for x, y, z in verts]


def _rotate_z(verts, angle_rad):
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return [(c * x - s * y, s * x + c * y, z) for x, y, z in verts]


# Import the real descriptor from ingestion (cross-service; acceptable in tests).
try:
    from ikip_ingestion.extract.types import CanonicalMesh
    from ikip_ingestion.stages.enrich import compute_d2_descriptor

    _HAS_INGESTION = True
except ImportError:
    _HAS_INGESTION = False


@pytest.mark.skipif(not _HAS_INGESTION, reason="ikip-ingestion not installed")
def test_d2_descriptor_translation_invariant() -> None:
    verts = _box_vertices(10, 20, 30)
    faces = _box_faces()
    mesh_a = CanonicalMesh(vertices=verts, faces=faces)
    mesh_b = CanonicalMesh(vertices=_translate(verts, 100, 200, 300), faces=faces)
    da = compute_d2_descriptor(mesh_a)
    db = compute_d2_descriptor(mesh_b)
    sim = sum(x * y for x, y in zip(da, db, strict=True))
    assert sim > 0.99, f"translation invariance failed: cosine={sim:.4f}"


@pytest.mark.skipif(not _HAS_INGESTION, reason="ikip-ingestion not installed")
def test_d2_descriptor_scale_invariant() -> None:
    verts = _box_vertices(10, 20, 30)
    faces = _box_faces()
    mesh_a = CanonicalMesh(vertices=verts, faces=faces)
    mesh_b = CanonicalMesh(vertices=_scale(verts, 7.3), faces=faces)
    da = compute_d2_descriptor(mesh_a)
    db = compute_d2_descriptor(mesh_b)
    sim = sum(x * y for x, y in zip(da, db, strict=True))
    assert sim > 0.99, f"scale invariance failed: cosine={sim:.4f}"


@pytest.mark.skipif(not _HAS_INGESTION, reason="ikip-ingestion not installed")
def test_d2_descriptor_rotation_invariant() -> None:
    import math

    verts = _box_vertices(10, 20, 30)
    faces = _box_faces()
    mesh_a = CanonicalMesh(vertices=verts, faces=faces)
    mesh_b = CanonicalMesh(vertices=_rotate_z(verts, math.pi / 4), faces=faces)
    da = compute_d2_descriptor(mesh_a)
    db = compute_d2_descriptor(mesh_b)
    sim = sum(x * y for x, y in zip(da, db, strict=True))
    assert sim > 0.95, f"rotation invariance failed: cosine={sim:.4f}"


@pytest.mark.skipif(not _HAS_INGESTION, reason="ikip-ingestion not installed")
def test_similar_part_ranks_above_dissimilar() -> None:
    """A rotated copy of the reference part scores higher than a completely different shape."""
    verts_box = _box_vertices(10, 20, 30)
    faces_box = _box_faces()
    # Reference: a box.
    ref_mesh = CanonicalMesh(vertices=verts_box, faces=faces_box)
    ref_desc = compute_d2_descriptor(ref_mesh)

    # Similar: same box, rotated.
    sim_mesh = CanonicalMesh(vertices=_rotate_z(verts_box, 1.1), faces=faces_box)
    sim_desc = compute_d2_descriptor(sim_mesh)

    # Dissimilar: a flat sliver (very different shape distribution).
    sliver_verts = _box_vertices(100, 100, 0.1)
    dis_mesh = CanonicalMesh(vertices=sliver_verts, faces=faces_box)
    dis_desc = compute_d2_descriptor(dis_mesh)

    def cosine(a, b):
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert cosine(ref_desc, sim_desc) > cosine(ref_desc, dis_desc)


# ---------------------------------------------------------------------------
# Channel + merge_and_rank integration
# ---------------------------------------------------------------------------


def _acl_store_with(doc_id: str, site: str) -> InMemoryAclStore:
    store = InMemoryAclStore()
    store.upsert(
        AclPolicy(
            document_id=doc_id,
            owner="eng",
            sites=[site],
            roles_allowed=["eng"],
            source_of_truth="test",
            synced_at=datetime.now(UTC),
            max_staleness_seconds=3600,
        )
    )
    return store


def _flat_desc(val: float, n: int = 64) -> list[float]:
    """A synthetic L2-normalized descriptor for store seeding."""
    raw = [val] * n
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw]


def test_shape_channel_returns_empty_without_descriptor() -> None:
    store = InMemoryShapeStore()
    acls = _acl_store_with("doc-1", "site-a")
    ch = ShapeSearchChannel(store, acls)
    query = RetrievalQuery(question="find similar parts")
    assert ch.search(query, limit=10) == []


def test_shape_channel_returns_candidates_with_descriptor() -> None:
    store = InMemoryShapeStore()
    store.add(ShapeRecord("ev-1", "doc-1", "part-1", _flat_desc(1.0)))
    acls = _acl_store_with("doc-1", "site-a")
    ch = ShapeSearchChannel(store, acls)
    query = ShapeRetrievalQuery(question="find similar", shape_descriptor=_flat_desc(1.0))
    results = ch.search(query, limit=10)
    assert len(results) == 1
    assert results[0].channel is RetrievalChannel.SHAPE


def test_restricted_shape_candidate_never_ranked() -> None:
    """A shape candidate from a restricted document must not survive merge_and_rank."""
    store = InMemoryShapeStore()
    store.add(ShapeRecord("ev-allowed", "doc-allowed", "part-a", _flat_desc(1.0)))
    store.add(ShapeRecord("ev-restricted", "doc-restricted", "part-b", _flat_desc(1.0)))

    # Only doc-allowed is in site-a; doc-restricted is site-b only.
    acls = InMemoryAclStore()
    now = datetime.now(UTC)
    acls.upsert(
        AclPolicy(
            document_id="doc-allowed",
            owner="eng",
            sites=["site-a"],
            roles_allowed=["eng"],
            source_of_truth="test",
            synced_at=now,
            max_staleness_seconds=3600,
        )
    )
    acls.upsert(
        AclPolicy(
            document_id="doc-restricted",
            owner="eng",
            sites=["site-b"],
            roles_allowed=["eng"],
            source_of_truth="test",
            synced_at=now,
            max_staleness_seconds=3600,
        )
    )

    ch = ShapeSearchChannel(store, acls)
    query = ShapeRetrievalQuery(question="q", shape_descriptor=_flat_desc(1.0))
    candidates = ch.search(query, limit=10)

    ctx = AuthorizationContext(
        subject_id="u1",
        roles=frozenset({"eng"}),
        sites=frozenset({"site-a"}),
        identity_verified=True,
    )
    ranked = merge_and_rank(ctx, [candidates])
    ids = [c.evidence_id for c in ranked]
    assert "ev-allowed" in ids
    assert "ev-restricted" not in ids


def test_shape_store_filter_contract() -> None:
    store = InMemoryShapeStore()
    descriptor = _flat_desc(1.0)
    store.add(ShapeRecord("ev-a", "doc-a", "part-a", descriptor))
    store.add(ShapeRecord("ev-b", "doc-b", "part-b", descriptor))

    assert {
        record.document_id
        for record, _ in store.shape_search(descriptor, allowed_document_ids=None, limit=10)
    } == {"doc-a", "doc-b"}
    assert store.shape_search(descriptor, allowed_document_ids=frozenset(), limit=10) == []
    allowed = store.shape_search(descriptor, allowed_document_ids=frozenset({"doc-b"}), limit=10)
    assert [record.document_id for record, _ in allowed] == ["doc-b"]
    assert len(store.shape_search(descriptor, allowed_document_ids=None, limit=1)) == 1
