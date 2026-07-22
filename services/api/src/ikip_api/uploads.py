"""Secure prototype upload, persistence and extraction pipeline.

The default ``memory`` profile keeps the existing zero-infrastructure developer experience.
``IKIP_STORAGE_PROFILE=durable`` selects PostgreSQL and S3-compatible object storage.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import tempfile
import threading
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from ikip_contracts import AclPolicy

_ALLOWED = {
    ".pdf": ("application/pdf", "PDF"),
    ".stl": ("model/stl", "STL"),
    ".step": ("model/step", "STEP"),
    ".stp": ("model/step", "STEP"),
}
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ ()-]{0,199}$")
TERMINAL = {"completed", "completed_with_warnings", "failed"}


@dataclass
class Document:
    document_id: str
    filename: str
    media_type: str
    format: str
    size_bytes: int
    checksum: str
    object_key: str
    owner: str
    sites: list[str]
    roles: list[str]
    state: str = "received"
    message: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("object_key")
        return value


class Repository(Protocol):
    def create(self, doc: Document) -> None: ...
    def update(
        self,
        document_id: str,
        state: str,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None: ...
    def get(self, document_id: str) -> Document | None: ...
    def list(self) -> list[Document]: ...
    def add_chunk(
        self, document_id: str, chunk_id: str, text: str, coordinates: dict[str, Any]
    ) -> None: ...
    def add_shape(
        self, document_id: str, part_id: str, descriptor: list[float], geometry: dict[str, Any]
    ) -> None: ...
    def iter_chunks(self) -> list[tuple[str, str, str]]: ...
    def iter_shapes(self) -> list[tuple[str, str, list[float]]]: ...


class MemoryRepository:
    def __init__(self) -> None:
        self.documents: dict[str, Document] = {}
        self.chunks: list[tuple[str, str, str, dict[str, Any]]] = []
        self.shapes: list[tuple[str, str, list[float], dict[str, Any]]] = []
        self._lock = threading.RLock()

    def create(self, doc: Document) -> None:
        with self._lock:
            self.documents[doc.document_id] = doc

    def update(
        self,
        document_id: str,
        state: str,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            doc = self.documents[document_id]
            doc.state, doc.message = state, message
            doc.updated_at = datetime.now(UTC).isoformat()
            if metadata is not None:
                doc.metadata = metadata

    def get(self, document_id: str) -> Document | None:
        return self.documents.get(document_id)

    def list(self) -> list[Document]:
        return sorted(self.documents.values(), key=lambda d: d.created_at, reverse=True)

    def add_chunk(
        self, document_id: str, chunk_id: str, text: str, coordinates: dict[str, Any]
    ) -> None:
        self.chunks.append((document_id, chunk_id, text, coordinates))

    def add_shape(
        self, document_id: str, part_id: str, descriptor: list[float], geometry: dict[str, Any]
    ) -> None:
        self.shapes.append((document_id, part_id, descriptor, geometry))

    def iter_chunks(self) -> list[tuple[str, str, str]]:
        return [(d, c, t) for d, c, t, _ in self.chunks]

    def iter_shapes(self) -> list[tuple[str, str, list[float]]]:
        return [(d, p, v) for d, p, v, _ in self.shapes]


class PostgresRepository:
    """Small connection-per-operation repository suitable for this prototype."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def _connect(self):
        import psycopg

        return psycopg.connect(self.dsn)

    def create(self, d: Document) -> None:
        with self._connect() as c:
            c.execute(
                """INSERT INTO uploaded_document(document_id,filename,media_type,format,size_bytes,checksum,object_key,owner,sites,roles,state,message,created_at,updated_at,metadata) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",  # noqa: E501
                (
                    d.document_id,
                    d.filename,
                    d.media_type,
                    d.format,
                    d.size_bytes,
                    d.checksum,
                    d.object_key,
                    d.owner,
                    d.sites,
                    d.roles,
                    d.state,
                    d.message,
                    d.created_at,
                    d.updated_at,
                    json.dumps(d.metadata),
                ),
            )

    def update(
        self,
        document_id: str,
        state: str,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as c:
            c.execute(
                "UPDATE uploaded_document SET state=%s,message=%s,metadata=COALESCE(%s,metadata),updated_at=now() WHERE document_id=%s",  # noqa: E501
                (
                    state,
                    message,
                    json.dumps(metadata) if metadata is not None else None,
                    document_id,
                ),
            )

    def get(self, document_id: str) -> Document | None:
        with self._connect() as c:
            row = c.execute(
                "SELECT document_id,filename,media_type,format,size_bytes,checksum,object_key,owner,sites,roles,state,message,created_at::text,updated_at::text,metadata FROM uploaded_document WHERE document_id=%s",  # noqa: E501
                (document_id,),
            ).fetchone()
        if not row:
            return None
        # updated_at is not material to public contract; normalize constructor fields.
        return Document(
            document_id=row[0],
            filename=row[1],
            media_type=row[2],
            format=row[3],
            size_bytes=row[4],
            checksum=row[5],
            object_key=row[6],
            owner=row[7],
            sites=list(row[8]),
            roles=list(row[9]),
            state=row[10],
            message=row[11],
            created_at=row[12],
            updated_at=row[13],
            metadata=row[14] or {},
        )

    def list(self) -> list[Document]:
        with self._connect() as c:
            ids = [
                r[0]
                for r in c.execute(
                    "SELECT document_id FROM uploaded_document ORDER BY created_at DESC"
                ).fetchall()
            ]
        return [d for i in ids if (d := self.get(i))]

    def add_chunk(
        self, document_id: str, chunk_id: str, text: str, coordinates: dict[str, Any]
    ) -> None:
        with self._connect() as c:
            c.execute(
                "INSERT INTO uploaded_chunk(chunk_id,document_id,text,source_coordinates) VALUES(%s,%s,%s,%s) ON CONFLICT(chunk_id) DO UPDATE SET text=excluded.text",  # noqa: E501
                (chunk_id, document_id, text, json.dumps(coordinates)),
            )

    def add_shape(
        self, document_id: str, part_id: str, descriptor: list[float], geometry: dict[str, Any]
    ) -> None:
        with self._connect() as c:
            c.execute(
                "INSERT INTO uploaded_shape(shape_id,document_id,part_id,descriptor,geometry) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(shape_id) DO NOTHING",  # noqa: E501
                (f"shape-{part_id}", document_id, part_id, descriptor, json.dumps(geometry)),
            )

    def iter_chunks(self) -> list[tuple[str, str, str]]:
        with self._connect() as c:
            return [
                (r[0], r[1], r[2])
                for r in c.execute(
                    "SELECT document_id,chunk_id,text FROM uploaded_chunk"
                ).fetchall()
            ]

    def iter_shapes(self) -> list[tuple[str, str, list[float]]]:
        with self._connect() as c:
            return [
                (r[0], r[1], list(r[2]))
                for r in c.execute(
                    "SELECT document_id,part_id,descriptor FROM uploaded_shape"
                ).fetchall()
            ]


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...


class MemoryObjectStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = bytes(data)

    def get(self, key: str) -> bytes:
        return self.objects[key]


class S3ObjectStore:
    def __init__(self) -> None:
        import boto3

        self.bucket = os.environ["IKIP_OBJECT_BUCKET"]
        self.client = boto3.client(
            "s3",
            endpoint_url=os.environ.get("IKIP_OBJECT_ENDPOINT"),
            aws_access_key_id=os.environ.get("IKIP_OBJECT_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("IKIP_OBJECT_SECRET_KEY"),
            region_name=os.environ.get("IKIP_OBJECT_REGION", "us-east-1"),
        )
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            self.client.create_bucket(Bucket=self.bucket)

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            Metadata={"sha256": hashlib.sha256(data).hexdigest()},
        )

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()


def validate(
    filename: str | None, content_type: str | None, data: bytes, max_bytes: int
) -> tuple[str, str, str]:
    if (
        not filename
        or filename != Path(filename).name
        or not _SAFE_NAME.fullmatch(filename)
        or ".." in filename
    ):
        raise ValueError("Unsafe filename. Use a simple name up to 200 characters.")
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED:
        raise ValueError("Only PDF, STL, STEP, and STP files are accepted.")
    expected, fmt = _ALLOWED[ext]
    aliases = {
        "application/octet-stream",
        "application/sla",
        "model/x.stl-binary",
        "model/x.stl-ascii",
        "application/step",
        "application/pdf",
        expected,
    }
    if content_type and content_type.lower() not in aliases:
        raise ValueError("Declared content type does not match the file type.")
    if not data:
        raise ValueError("The uploaded file is empty.")
    if len(data) > max_bytes:
        raise ValueError(f"File exceeds the {max_bytes // (1024 * 1024)} MiB limit.")
    head = data[:512].lstrip()
    valid = (fmt == "PDF" and head.startswith(b"%PDF-")) or (
        fmt == "STEP" and b"ISO-10303-21" in head.upper()
    )
    if fmt == "STL":
        ascii_ok = head[:5].lower() == b"solid" and b"facet" in data[:8192].lower()
        binary_ok = len(data) >= 84 and 84 + int.from_bytes(data[80:84], "little") * 50 == len(data)
        valid = ascii_ok or binary_ok
    if not valid:
        raise ValueError(f"File content is not valid {fmt} data.")
    return filename, expected, fmt


def _positive_env(name: str, default: int) -> int:
    """Read a positive integer limit, failing closed on invalid configuration."""
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be a positive integer")
    return value


class UploadManager:
    def __init__(
        self,
        repo: Repository,
        objects: ObjectStore,
        index_text: Callable[[str, str, str], None],
        index_shape: Callable[[str, str, list[float]], None],
        acl_store: Any,
    ) -> None:
        self.repo, self.objects, self.index_text, self.index_shape, self.acl_store = (
            repo,
            objects,
            index_text,
            index_shape,
            acl_store,
        )
        self.max_bytes = _positive_env("IKIP_UPLOAD_MAX_BYTES", 50 * 1024 * 1024)
        # Extraction limits are separate from upload size: a small, compressed PDF can
        # otherwise expand to an unbounded number of pages/chunks or text bytes.
        self.max_pdf_pages = _positive_env("IKIP_PDF_MAX_PAGES", 200)
        self.max_pdf_text_chars = _positive_env("IKIP_PDF_MAX_EXTRACTED_TEXT_CHARS", 2_000_000)
        self.max_pdf_chunks = _positive_env("IKIP_PDF_MAX_CHUNKS", 2_000)

    def accept(
        self,
        filename: str | None,
        content_type: str | None,
        data: bytes,
        owner: str,
        sites: list[str],
        roles: list[str],
    ) -> Document:
        filename, media_type, fmt = validate(filename, content_type, data, self.max_bytes)
        doc_id = str(uuid.uuid4())
        checksum = hashlib.sha256(data).hexdigest()
        key = f"originals/{doc_id}/{filename}"
        d = Document(
            doc_id, filename, media_type, fmt, len(data), checksum, key, owner, sites, roles
        )
        self.objects.put(key, data, media_type)
        self.repo.create(d)
        self.acl_store.upsert(
            AclPolicy(
                document_id=doc_id,
                owner=owner,
                sites=sites,
                roles_allowed=roles,
                source_of_truth="upload",
                synced_at=datetime.now(UTC),
                max_staleness_seconds=31536000,
            )
        )
        return d

    def process(self, document_id: str) -> None:
        d = self.repo.get(document_id)
        if not d:
            return
        self.repo.update(document_id, "processing", "Extracting and indexing")
        try:
            data = self.objects.get(d.object_key)
            chunks: list[tuple[str, dict[str, Any]]] = []
            metadata: dict[str, Any] = {}
            warning: str | None = None
            if d.format == "PDF":
                from pypdf import PdfReader

                reader = PdfReader(io.BytesIO(data), strict=False)
                if reader.is_encrypted:
                    raise ValueError("Encrypted PDFs are not supported by this prototype.")
                page_count = len(reader.pages)
                if page_count > self.max_pdf_pages:
                    raise ValueError(f"PDF has {page_count} pages; limit is {self.max_pdf_pages}.")
                metadata = {"pages": page_count}
                extracted_chars = 0
                for page_no, page in enumerate(reader.pages, 1):
                    text = (page.extract_text() or "").strip()
                    extracted_chars += len(text)
                    if extracted_chars > self.max_pdf_text_chars:
                        raise ValueError("PDF extracted text exceeds configured character limit.")
                    for start in range(0, len(text), 1400):
                        part = text[start : start + 1600].strip()
                        if part:
                            if len(chunks) >= self.max_pdf_chunks:
                                raise ValueError("PDF extracted chunks exceed configured limit.")
                            chunks.append((part, {"page": page_no, "character_start": start}))
                metadata["extracted_characters"] = extracted_chars
                if not chunks:
                    warning = "No machine-readable text was found (OCR is not included)."
            else:
                from ikip_ingestion.extract.registry import default_registry

                with tempfile.NamedTemporaryFile(suffix=Path(d.filename).suffix) as f:
                    f.write(data)
                    f.flush()
                    result = default_registry().handle(Path(f.name), data[:512], d.filename)
                model = getattr(result, "model", None) or getattr(result, "value", None)
                if model is None:
                    warning = (
                        getattr(result, "detail", None)
                        or "Geometry toolkit unavailable; original retained."
                    )
                    metadata = {
                        "format": d.format,
                        "geometry_available": False,
                        "representation": "metadata_only",
                    }
                    chunks.append(
                        (
                            f"Uploaded {d.format} model {d.filename}. {warning}",
                            {"cad_label": d.filename},
                        )
                    )
                else:
                    metadata = {
                        "format": model.source_format,
                        "tier": model.tier.value,
                        "geometry_available": model.geometry_available,
                        "properties": model.properties,
                        "warnings": model.warnings,
                    }
                    if model.metrics:
                        metadata["metrics"] = asdict(model.metrics)
                    chunks.append(
                        (
                            f"CAD model {d.filename}. Format {model.source_format}. Properties {json.dumps(model.properties)}. Metrics {json.dumps(metadata.get('metrics', {}))}.",  # noqa: E501
                            {"cad_label": d.filename},
                        )
                    )
                    for p in model.parts:
                        chunks.append(
                            (
                                f"Part {p.name or p.part_ref}; part number {p.part_number or 'unknown'}; properties {json.dumps(p.properties)}",  # noqa: E501
                                {"cad_part_ref": p.part_ref},
                            )
                        )
                    if model.canonical_mesh:
                        from ikip_ingestion.stages.enrich import compute_d2_descriptor

                        descriptor = compute_d2_descriptor(model.canonical_mesh)
                        part_id = f"{d.document_id}-part-0"
                        geometry = asdict(model.canonical_mesh)
                        self.repo.add_shape(d.document_id, part_id, descriptor, geometry)
                        self.index_shape(d.document_id, part_id, descriptor)
            for n, (text, coord) in enumerate(chunks):
                cid = f"{d.document_id}-chunk-{n}"
                self.repo.add_chunk(d.document_id, cid, text, coord)
                self.index_text(d.document_id, cid, text)
            state = "completed_with_warnings" if warning else "completed"
            self.repo.update(d.document_id, state, warning, metadata)
        except Exception as exc:
            self.repo.update(
                d.document_id,
                "failed",
                f"Processing failed: {type(exc).__name__}: {str(exc)[:300]}",
            )


def build_persistence() -> tuple[Repository, ObjectStore]:
    profile = os.environ.get("IKIP_STORAGE_PROFILE", "memory").lower()
    if profile == "memory":
        return MemoryRepository(), MemoryObjectStore()
    if profile != "durable":
        raise RuntimeError("IKIP_STORAGE_PROFILE must be memory or durable")
    dsn = os.environ.get("IKIP_DATABASE_URL")
    if not dsn:
        raise RuntimeError("IKIP_DATABASE_URL is required for durable storage")
    return PostgresRepository(dsn), S3ObjectStore()
