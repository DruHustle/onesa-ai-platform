"""Owned twin metadata. Binaries live exclusively in the private durable file adapter."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Record, now


class TwinOwned(Record):
    __abstract__ = True
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class TwinTemplate(TwinOwned):
    __tablename__ = "twin_templates"
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(80))
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)


class TwinAsset(TwinOwned):
    __tablename__ = "twin_assets"
    template_id: Mapped[UUID] = mapped_column(ForeignKey("twin_templates.id"))
    name: Mapped[str] = mapped_column(String(120))
    serial: Mapped[str] = mapped_column(String(120))
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)
    active_model_id: Mapped[UUID | None]
    revision: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (CheckConstraint("revision > 0"), UniqueConstraint("user_id", "serial"))


class TwinFile(TwinOwned):
    __tablename__ = "twin_files"
    filename: Mapped[str] = mapped_column(String(200))
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int]
    details: Mapped[dict[str, Any]] = mapped_column(JSONB)
    __table_args__ = (CheckConstraint("size BETWEEN 1 AND 4194304"),)


class TwinModel(TwinOwned):
    __tablename__ = "twin_models"
    template_id: Mapped[UUID] = mapped_column(ForeignKey("twin_templates.id"))
    file_id: Mapped[UUID] = mapped_column(ForeignKey("twin_files.id"))
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)


class TwinSource(TwinOwned):
    __tablename__ = "twin_sources"
    asset_id: Mapped[UUID] = mapped_column(ForeignKey("twin_assets.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TwinReading(Record):
    __tablename__ = "twin_readings"
    source_id: Mapped[UUID] = mapped_column(ForeignKey("twin_sources.id", ondelete="CASCADE"))
    asset_id: Mapped[UUID] = mapped_column(ForeignKey("twin_assets.id", ondelete="CASCADE"))
    component_id: Mapped[UUID]
    message_id: Mapped[str] = mapped_column(String(160))
    tag: Mapped[str] = mapped_column(String(80))
    mode: Mapped[str] = mapped_column(String(16))
    unit: Mapped[str] = mapped_column(String(24))
    value: Mapped[float] = mapped_column(Float)
    quality: Mapped[str] = mapped_column(String(16))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB)
    __table_args__ = (
        UniqueConstraint("source_id", "message_id", "tag", "mode"),
        CheckConstraint("mode IN ('live', 'simulated', 'replay')"),
        CheckConstraint("quality IN ('good', 'bad', 'unknown')"),
        Index("ix_twin_readings_history", "asset_id", "mode", "observed_at", "id"),
    )


class TwinEvent(Record):
    __tablename__ = "twin_events"
    asset_id: Mapped[UUID] = mapped_column(ForeignKey("twin_assets.id", ondelete="CASCADE"))
    source_id: Mapped[UUID] = mapped_column(ForeignKey("twin_sources.id", ondelete="CASCADE"))
    component_id: Mapped[UUID]
    reading_id: Mapped[UUID] = mapped_column(ForeignKey("twin_readings.id", ondelete="CASCADE"))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB)
    __table_args__ = (Index("ix_twin_events_asset_id", "asset_id", "created_at"),)


class TwinNote(TwinOwned):
    __tablename__ = "twin_notes"
    asset_id: Mapped[UUID] = mapped_column(ForeignKey("twin_assets.id", ondelete="CASCADE"))
    component_id: Mapped[UUID | None]
    kind: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    __table_args__ = (CheckConstraint("kind IN ('annotation', 'viewpoint', 'inspection')"),)
