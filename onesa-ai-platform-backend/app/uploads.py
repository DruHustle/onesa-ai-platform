"""Resumable bounded transport feeding the existing private parser/index pipeline."""

import base64
import binascii
import hashlib
from datetime import timedelta
from io import BytesIO
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, UploadFile
from pydantic import Field
from sqlalchemy import delete, func, select, text
from starlette.datastructures import Headers

from app.auth import DB, Auth, throttle
from app.errors import fail
from app.knowledge import ingest
from app.models import BoundedUpload, UploadChunk, now
from app.responses import DocumentMetadata
from app.schemas import Strict

router = APIRouter(prefix="/api/v1/knowledge/uploads", tags=["bounded ingestion"])
CHUNK_BYTES = 512 * 1024


class Start(Strict):
    filename: str = Field(min_length=1, max_length=200, pattern=r"^[^/\\]+\.(txt|pdf)$")
    media_type: str = Field(pattern=r"^(text/plain|application/pdf)$")
    size: int = Field(ge=1, le=5 * 1024 * 1024)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class Chunk(Strict):
    sequence: int = Field(ge=0, le=9)
    base64: str = Field(min_length=4, max_length=699052)


class Receipt(Strict):
    id: UUID
    chunk_bytes: int = CHUNK_BYTES


class Progress(Strict):
    received: int


def owned(db: DB, auth: Auth, identifier: UUID) -> BoundedUpload:
    row = db.scalar(
        select(BoundedUpload)
        .where(
            BoundedUpload.id == identifier,
            BoundedUpload.user_id == auth[0].id,
            BoundedUpload.expires_at > now(),
        )
        .with_for_update()
    )
    if row is None:
        fail(404, "upload_not_found", "Upload not found or expired")
    return row


@router.post("", status_code=201, response_model=Receipt)
def start(body: Start, request: Request, db: DB, auth: Auth) -> Receipt:
    throttle(request, db, "upload:" + str(auth[0].id))
    # Serialize capacity across replicas. A user's request may only clean their
    # own expired fragments; another account's cleanup belongs to the owner worker.
    db.execute(text("SELECT pg_advisory_xact_lock(757835)"))
    instant = now()
    db.execute(
        delete(BoundedUpload).where(
            BoundedUpload.user_id == auth[0].id, BoundedUpload.expires_at <= instant
        )
    )
    count = (
        db.scalar(
            select(func.count())
            .select_from(BoundedUpload)
            .where(
                BoundedUpload.user_id == auth[0].id,
                BoundedUpload.result.is_(None),
                BoundedUpload.expires_at > instant,
            )
        )
        or 0
    )
    total = (
        db.scalar(
            select(func.count())
            .select_from(BoundedUpload)
            .where(BoundedUpload.result.is_(None), BoundedUpload.expires_at > instant)
        )
        or 0
    )
    if count >= 2 or total >= 100:
        fail(429, "upload_quota", "Too many unfinished uploads; cancel or wait for expiry")
    row = BoundedUpload(
        user_id=auth[0].id,
        filename=body.filename,
        media_type=body.media_type,
        size=body.size,
        checksum=body.sha256,
        expires_at=now() + timedelta(minutes=20),
    )
    db.add(row)
    db.commit()
    return Receipt(id=row.id)


@router.post("/{identifier}/chunks", response_model=Progress)
def chunk(identifier: UUID, body: Chunk, request: Request, db: DB, auth: Auth) -> Progress:
    throttle(request, db, "upload:" + str(auth[0].id))
    row = owned(db, auth, identifier)
    try:
        data = base64.b64decode(body.base64, validate=True)
    except (ValueError, binascii.Error):
        fail(400, "invalid_chunk", "Invalid upload chunk")
    if not data or len(data) > CHUNK_BYTES:
        fail(413, "invalid_chunk", "Upload chunk exceeds the bounded transport limit")
    previous = db.get(UploadChunk, (identifier, body.sequence))
    if previous is not None and previous.data == data:
        return Progress(received=row.received)
    count = (
        db.scalar(
            select(func.count()).select_from(UploadChunk).where(UploadChunk.upload_id == identifier)
        )
        or 0
    )
    if row.result is not None or body.sequence != count or row.received + len(data) > row.size:
        fail(409, "chunk_order", "Upload chunk is out of order or exceeds the declared size")
    # All non-final chunks have the announced size, preventing sequence/size ambiguity.
    if row.received + len(data) < row.size and len(data) != CHUNK_BYTES:
        fail(400, "chunk_size", "Non-final chunks must match the announced chunk size")
    db.add(UploadChunk(upload_id=identifier, sequence=body.sequence, data=data))
    row.received += len(data)
    db.commit()
    return Progress(received=row.received)


@router.post("/{identifier}/complete", response_model=DocumentMetadata)
async def complete(identifier: UUID, request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    throttle(request, db, "upload:" + str(auth[0].id))
    row = owned(db, auth, identifier)
    if row.result is not None:
        return row.result
    if row.received != row.size:
        fail(409, "upload_incomplete", "Upload is incomplete")
    chunks = db.scalars(
        select(UploadChunk)
        .where(UploadChunk.upload_id == identifier)
        .order_by(UploadChunk.sequence)
    )
    data = b"".join(part.data for part in chunks)
    if hashlib.sha256(data).hexdigest() != row.checksum:
        fail(400, "upload_checksum", "Upload integrity check failed")
    file = UploadFile(
        BytesIO(data), filename=row.filename, headers=Headers({"content-type": row.media_type})
    )
    async with request.app.state.ingestion_semaphore:
        result = await ingest(request, db, auth, file, commit=False)
    row.result = DocumentMetadata.model_validate(result).model_dump(mode="json")
    db.execute(delete(UploadChunk).where(UploadChunk.upload_id == identifier))
    db.commit()
    return result


@router.delete("/{identifier}", status_code=204)
def cancel(identifier: UUID, db: DB, auth: Auth) -> None:
    row = owned(db, auth, identifier)
    if row.result is not None:
        fail(409, "upload_complete", "Upload already finalized; delete the document explicitly")
    db.delete(row)
    db.commit()
