"""Persistent domain records; PostgreSQL is the acceptance database."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Record(Base):
    __abstract__ = True
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Record):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    display_name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="active")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (CheckConstraint("status IN ('active', 'disabled')"),)


class AuthSession(Record):
    __tablename__ = "auth_sessions"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Conversation(Record):
    __tablename__ = "conversations"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="New conversation")
    selected_model_id: Mapped[str] = mapped_column(String(80), default="default")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    active_run_id: Mapped[UUID | None]
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Message(Record):
    __tablename__ = "messages"
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="completed")
    sequence: Mapped[int] = mapped_column(Integer)
    model_id: Mapped[str | None] = mapped_column(String(80))
    __table_args__ = (
        UniqueConstraint("conversation_id", "sequence"),
        CheckConstraint("sequence > 0"),
        CheckConstraint("role IN ('user', 'assistant', 'system')"),
        CheckConstraint("status IN ('completed', 'failed', 'cancelled')"),
    )


class InferenceRun(Record):
    __tablename__ = "inference_runs"
    request_id: Mapped[UUID]
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    model_id: Mapped[str] = mapped_column(String(80), default="default")
    status: Mapped[str] = mapped_column(String(20), default="running")
    latency_ms: Mapped[int | None]
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    __table_args__ = (
        CheckConstraint("status IN ('running', 'completed', 'failed', 'cancelled')"),
        CheckConstraint("latency_ms >= 0 AND input_tokens >= 0 AND output_tokens >= 0"),
    )


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AccessGrant(Base):
    __tablename__ = "access_grants"
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IdentityToken(Record):
    __tablename__ = "identity_tokens"
    purpose: Mapped[str] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(254))
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    grant_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("purpose IN ('invitation', 'recovery')"),)


class IdentityMail(Base):
    __tablename__ = "identity_mail"
    token_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_tokens.id", ondelete="CASCADE"), primary_key=True
    )
    state: Mapped[str] = mapped_column(String(20), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_id: Mapped[UUID | None]
    provider_id: Mapped[str | None] = mapped_column(String(200))
    __table_args__ = (
        CheckConstraint("state IN ('queued', 'leased', 'accepted', 'failed', 'cancelled')"),
        CheckConstraint("attempts BETWEEN 0 AND 5"),
    )


class IdentityAudit(Record):
    __tablename__ = "identity_audit"
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    event: Mapped[str] = mapped_column(String(40))
    record_id: Mapped[UUID | None]


class BoundedUpload(Record):
    __tablename__ = "bounded_uploads"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(200))
    media_type: Mapped[str] = mapped_column(String(80))
    size: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    received: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    __table_args__ = (
        CheckConstraint("size BETWEEN 1 AND 5242880"),
        CheckConstraint("received BETWEEN 0 AND size"),
    )


class UploadChunk(Base):
    __tablename__ = "upload_chunks"
    upload_id: Mapped[UUID] = mapped_column(
        ForeignKey("bounded_uploads.id", ondelete="CASCADE"), primary_key=True
    )
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    __table_args__ = (
        CheckConstraint("sequence BETWEEN 0 AND 9"),
        CheckConstraint("octet_length(data) BETWEEN 1 AND 524288"),
    )


class ModelLease(Record):
    __tablename__ = "model_leases"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class IndustrialInvestigation(Record):
    __tablename__ = "industrial_investigations"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="ready")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    __table_args__ = (
        CheckConstraint("revision > 0"),
        CheckConstraint("status IN ('ready', 'running', 'completed', 'failed', 'cancelled')"),
    )


Index("conversation_owner_updated", Conversation.user_id, Conversation.updated_at)


class Document(Record):
    __tablename__ = "documents"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    media_type: Mapped[str] = mapped_column(String(80))
    text: Mapped[str]
    checksum: Mapped[str] = mapped_column(String(64))
    embedding_version: Mapped[str] = mapped_column(String(256))
    __table_args__ = (UniqueConstraint("user_id", "checksum"),)


class DocumentChunk(Record):
    __tablename__ = "document_chunks"
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    text: Mapped[str]
    embedding_version: Mapped[str] = mapped_column(String(256))
    embedding: Mapped[list[float]] = mapped_column(Vector(256))
    __table_args__ = (UniqueConstraint("document_id", "position"), CheckConstraint("position >= 0"))


class AgentRun(Record):
    __tablename__ = "agent_runs"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    goal: Mapped[str]
    status: Mapped[str] = mapped_column(String(20), default="running")
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    __table_args__ = (CheckConstraint("status IN ('running', 'completed', 'failed', 'cancelled')"),)


class Trip(Record):
    __tablename__ = "trips"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    destination: Mapped[str] = mapped_column(String(200))
    duration: Mapped[int]
    budget: Mapped[float]
    currency: Mapped[str] = mapped_column(String(3))
    preferences: Mapped[str]
    revision: Mapped[int] = mapped_column(default=1)
    itinerary: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (
        CheckConstraint("duration BETWEEN 1 AND 14"),
        CheckConstraint("budget > 0"),
        CheckConstraint("revision > 0"),
    )
