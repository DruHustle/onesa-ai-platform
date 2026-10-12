"""Bounded text/PDF ingestion and owner-scoped versioned pgvector retrieval."""

import hashlib
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

import httpx
from fastapi import APIRouter, File, Query, Request, UploadFile
from pydantic import Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth import DB, Auth
from app.cloudflare import embeddings as cloudflare_embeddings
from app.config import Settings
from app.errors import fail
from app.models import Document, DocumentChunk
from app.responses import DocumentDetail, DocumentList, DocumentMetadata, KnowledgeResults
from app.schemas import Strict

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])
DIMENSIONS = 256


class Search(Strict):
    query: str = Field(min_length=1, max_length=4000)
    document_ids: list[UUID] = Field(default_factory=list, max_length=20)
    limit: int = Field(default=5, ge=1, le=10)


def version(config: Settings) -> str:
    return f"{config.embedding_backend}:{config.embedding_name}:{config.embedding_revision}:256"


def embed(texts: list[str], config: Settings, *, query: bool = False) -> list[list[float]]:
    if config.embedding_backend == "cloudflare":
        try:
            return cloudflare_embeddings(texts, config, query=query)
        except Exception:
            fail(503, "embedding_unavailable", "Embedding service unavailable or incompatible")
    if config.embedding_backend == "http":
        try:
            inputs = (
                [
                    f"Instruct: {config.embedding_query_instruction}\nQuery:{value}"
                    for value in texts
                ]
                if query and config.embedding_query_instruction
                else texts
            )
            response = httpx.post(
                config.embedding_base_url.rstrip("/") + "/embeddings",
                headers={"Authorization": "Bearer " + config.embedding_api_key},
                json={"model": config.embedding_name, "input": inputs, "dimensions": DIMENSIONS},
                timeout=30,
            )
            response.raise_for_status()
            rows = sorted(response.json()["data"], key=lambda r: r["index"])
            if [r["index"] for r in rows] != list(range(len(texts))):
                raise ValueError("Embedding indices do not match")
            result = [[float(v) for v in row["embedding"]] for row in rows]
            if any(len(v) != DIMENSIONS or not all(math.isfinite(x) for x in v) for v in result):
                raise ValueError("Embedding dimensions/values are invalid")
            if any(not any(v) for v in result):
                raise ValueError("Zero embedding")
            return result
        except Exception:
            fail(503, "embedding_unavailable", "Embedding service unavailable or incompatible")
    # Stable lexical hashing baseline, not semantic model embeddings.
    result = []
    for text in texts:
        vector = [0.0] * DIMENSIONS
        for word in re.findall(r"\w+", text.casefold()):
            slot = int.from_bytes(hashlib.sha256(word.encode()).digest()[:4], "big") % DIMENSIONS
            vector[slot] += 1
        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0:
            fail(422, "empty_document", "Content must contain searchable text")
        result.append([v / norm for v in vector])
    return result


def owned_document(db: Session, identifier: UUID, user_id: UUID) -> Document:
    row = db.scalar(select(Document).where(Document.id == identifier, Document.user_id == user_id))
    if row is None:
        fail(404, "not_found", "Document not found")
    return row


def metadata(row: Document) -> dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title,
        "media_type": row.media_type,
        "embedding_version": row.embedding_version,
        "created_at": row.created_at,
    }


def index(db: Session, row: Document, config: Settings) -> None:
    chunks = [row.text[start : start + 1200] for start in range(0, len(row.text), 1000)]
    if len(chunks) > 256:
        fail(413, "document_too_large", "Extracted document exceeds 256 chunks")
    # Compute before deleting: external embedding failure leaves old index intact.
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), 16):
        vectors.extend(embed(chunks[start : start + 16], config))
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == row.id))
    row.embedding_version = version(config)
    for position, (text, vector) in enumerate(zip(chunks, vectors, strict=True)):
        db.add(
            DocumentChunk(
                document_id=row.id,
                position=position,
                text=text,
                embedding=vector,
                embedding_version=row.embedding_version,
            )
        )


def extract(data: bytes, filename: str, media: str) -> str:
    if filename.lower().endswith(".txt") and media in {"text/plain", "application/octet-stream"}:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            fail(422, "invalid_text", "Text documents must use UTF-8")
    elif (
        filename.lower().endswith(".pdf")
        and media == "application/pdf"
        and data.startswith(b"%PDF-")
    ):
        try:
            with tempfile.TemporaryDirectory(prefix="onesa-pdf-") as directory:
                result = subprocess.run(
                    [sys.executable, "-I", str(Path(__file__).with_name("pdf_worker.py"))],
                    input=data,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    env={},
                    cwd=directory,
                    timeout=10,
                    check=True,
                )
            text = result.stdout.decode("utf-8")
        except Exception:
            fail(422, "invalid_pdf", "Provide an unencrypted PDF with at most 100 text pages")
    else:
        fail(415, "unsupported_document", "Upload a UTF-8 .txt or a text-based .pdf")
    if not text.strip() or "\x00" in text:
        fail(422, "empty_document", "Document contains no usable text")
    if len(text) > 256000:
        fail(413, "document_too_large", "Extracted text exceeds 256,000 characters")
    return text.strip()


@router.post("/documents", status_code=201, response_model=DocumentMetadata)
async def upload(
    request: Request, db: DB, auth: Auth, file: Annotated[UploadFile, File()]
) -> dict[str, Any]:
    async with request.app.state.ingestion_semaphore:
        return await ingest(request, db, auth, file)


async def ingest(
    request: Request, db: DB, auth: Auth, file: UploadFile, *, commit: bool = True
) -> dict[str, Any]:
    data = await file.read(5 * 1024 * 1024 + 1)
    await file.close()
    if len(data) > 5 * 1024 * 1024:
        fail(413, "document_too_large", "Document upload limit is 5 MiB")
    filename = (file.filename or "document").replace("\\", "/").rsplit("/", 1)[-1][:200]
    text = await run_in_threadpool(extract, data, filename, file.content_type or "")
    if (
        db.scalar(
            select(Document.id).where(
                Document.user_id == auth[0].id,
                Document.checksum == hashlib.sha256(text.encode()).hexdigest(),
            )
        )
        is not None
    ):
        fail(409, "duplicate_document", "This document is already indexed")
    from sqlalchemy import func
    from sqlalchemy import text as sql_text

    config = request.app.state.settings
    db.execute(sql_text("SELECT pg_advisory_xact_lock(757838)"))
    count = (
        db.scalar(select(func.count()).select_from(Document).where(Document.user_id == auth[0].id))
        or 0
    )
    own_bytes = (
        db.scalar(
            select(func.coalesce(func.sum(func.octet_length(Document.text)), 0)).where(
                Document.user_id == auth[0].id
            )
        )
        or 0
    )
    total_bytes = (
        db.scalar(select(func.coalesce(func.sum(func.octet_length(Document.text)), 0))) or 0
    )
    incoming = len(text.encode())
    if (
        count >= config.knowledge_max_documents
        or own_bytes + incoming > config.knowledge_user_text_bytes
        or total_bytes + incoming > config.knowledge_global_text_bytes
    ):
        fail(429, "knowledge_quota", "Knowledge storage budget is exhausted")
    row = Document(
        user_id=auth[0].id,
        title=filename,
        media_type=file.content_type or "text/plain",
        text=text,
        checksum=hashlib.sha256(text.encode()).hexdigest(),
        embedding_version=version(request.app.state.settings),
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        fail(409, "duplicate_document", "This document is already indexed")
    await run_in_threadpool(index, db, row, request.app.state.settings)
    if commit:
        db.commit()
    return metadata(row)


@router.get("/documents", response_model=DocumentList)
def documents(
    db: DB,
    auth: Auth,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    rows = db.scalars(
        select(Document)
        .where(Document.user_id == auth[0].id)
        .order_by(Document.created_at.desc(), Document.id)
        .offset(offset)
        .limit(limit)
    )
    return {"items": [metadata(row) for row in rows], "limit": limit, "offset": offset}


@router.get("/documents/{identifier}", response_model=DocumentDetail)
def document(identifier: UUID, db: DB, auth: Auth) -> dict[str, Any]:
    row = owned_document(db, identifier, auth[0].id)
    return {**metadata(row), "text": row.text}


@router.delete("/documents/{identifier}", status_code=204)
def remove(identifier: UUID, db: DB, auth: Auth) -> None:
    row = owned_document(db, identifier, auth[0].id)
    from sqlalchemy import delete

    from app.models import BoundedUpload

    db.execute(
        delete(BoundedUpload).where(
            BoundedUpload.user_id == auth[0].id,
            BoundedUpload.result["id"].astext == str(identifier),
        )
    )
    db.delete(row)
    db.commit()


@router.post("/documents/{identifier}/reindex", response_model=DocumentMetadata)
def reindex(identifier: UUID, request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    row = owned_document(db, identifier, auth[0].id)
    index(db, row, request.app.state.settings)
    db.commit()
    return metadata(row)


def retrieve(body: Search, config: Settings, db: Session, user_id: UUID) -> list[dict[str, Any]]:
    for identifier in body.document_ids:
        owned_document(db, identifier, user_id)
    vector = embed([body.query], config, query=True)[0]
    distance = DocumentChunk.embedding.cosine_distance(vector)
    query = select(DocumentChunk, Document, distance.label("distance")).join(Document)
    query = query.where(
        Document.user_id == user_id, DocumentChunk.embedding_version == version(config)
    )
    if body.document_ids:
        query = query.where(Document.id.in_(body.document_ids))
    rows = db.execute(query.order_by(distance, DocumentChunk.id).limit(body.limit))
    return [
        {
            "document_id": str(doc.id),
            "title": doc.title,
            "chunk": chunk.position,
            "text": chunk.text,
            "distance": float(score),
            "embedding_version": chunk.embedding_version,
        }
        for chunk, doc, score in rows
        if score < 0.95
    ]


@router.post("/search", response_model=KnowledgeResults)
def search(body: Search, request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    return {
        "sources": retrieve(body, request.app.state.settings, db, auth[0].id),
        "backend": request.app.state.settings.embedding_backend,
    }
