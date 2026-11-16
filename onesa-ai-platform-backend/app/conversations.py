from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth import DB, Auth
from app.errors import fail
from app.models import Conversation, InferenceRun, Message, now
from app.pagination import page
from app.schemas import (
    CancelGeneration,
    ConversationCreate,
    ConversationDetail,
    ConversationList,
    ConversationOut,
    MessageOut,
    Rename,
)

router = APIRouter(prefix="/api/v1", tags=["conversations"])


def owned(db: Session, identifier: UUID, user_id: UUID, lock: bool = False) -> Conversation:
    query = select(Conversation).where(
        Conversation.id == identifier, Conversation.user_id == user_id
    )
    if lock:
        query = query.with_for_update()
    row = db.scalar(query)
    if row is None:
        fail(404, "not_found", "Conversation not found")
    return row


def idle(row: Conversation) -> None:
    if row.active_run_id and row.lease_until and row.lease_until > now():
        fail(409, "conversation_busy", "A response is already being generated")


@router.post("/conversations", status_code=201, response_model=ConversationOut)
def create(body: ConversationCreate, db: DB, auth: Auth) -> Conversation:
    if body.selected_model_id != "default":
        fail(422, "unknown_model", "Select an available model")
    row = Conversation(user_id=auth[0].id, **body.model_dump())
    db.add(row)
    db.commit()
    return row


@router.get("/conversations", response_model=ConversationList)
def listing(
    db: DB,
    auth: Auth,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
) -> dict[str, Any]:
    query = select(Conversation).where(Conversation.user_id == auth[0].id)
    rows, following = page(
        db, Conversation, query, limit, offset, cursor, auth[0].id, "conversations"
    )
    total = db.scalar(
        select(func.count()).select_from(Conversation).where(Conversation.user_id == auth[0].id)
    )
    return {
        "items": [ConversationOut.model_validate(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "next_cursor": following,
    }


@router.get("/conversations/{identifier}", response_model=ConversationDetail)
def detail(identifier: UUID, db: DB, auth: Auth) -> dict[str, Any]:
    row = owned(db, identifier, auth[0].id)
    messages = db.scalars(
        select(Message).where(Message.conversation_id == row.id).order_by(Message.sequence)
    )
    return {
        "conversation": ConversationOut.model_validate(row),
        "messages": [MessageOut.model_validate(message) for message in messages],
    }


@router.patch("/conversations/{identifier}", response_model=ConversationOut)
def rename(identifier: UUID, body: Rename, db: DB, auth: Auth) -> Conversation:
    row = owned(db, identifier, auth[0].id, lock=True)
    idle(row)
    row.title = body.title
    db.commit()
    return row


@router.delete("/conversations/{identifier}", status_code=204)
def remove(identifier: UUID, db: DB, auth: Auth) -> None:
    row = owned(db, identifier, auth[0].id, lock=True)
    idle(row)
    db.execute(delete(Conversation).where(Conversation.id == row.id))
    db.commit()


@router.post("/conversations/{identifier}/cancel", status_code=204)
def cancel(identifier: UUID, body: CancelGeneration, db: DB, auth: Auth) -> None:
    row = owned(db, identifier, auth[0].id, lock=True)
    if row.active_run_id == body.run_id:
        run = db.get(InferenceRun, body.run_id)
        if run is not None:
            run.status = "cancelled"
        row.active_run_id, row.lease_until, row.updated_at = None, None, now()
        db.commit()
