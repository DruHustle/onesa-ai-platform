"""Independent owned security evidence, derivations and human decisions."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Record, now


class CyberOwned(Record):
    __abstract__ = True
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    sensitive: Mapped[bool] = mapped_column(default=False)


class CyberAsset(CyberOwned):
    __tablename__ = "cyber_assets"
    name: Mapped[str] = mapped_column(String(120))
    identity: Mapped[str] = mapped_column(String(128))
    zone: Mapped[str] = mapped_column(String(80))
    criticality: Mapped[str] = mapped_column(String(16))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB)
    __table_args__ = (UniqueConstraint("user_id", "identity"),)


class CyberSource(CyberOwned):
    __tablename__ = "cyber_sources"
    name: Mapped[str] = mapped_column(String(120))
    namespace: Mapped[str] = mapped_column(String(64))
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    scope: Mapped[str] = mapped_column(String(16), default="owner")
    config: Mapped[dict[str, Any]] = mapped_column(JSONB)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("user_id", "namespace"),)


class CyberMapping(CyberOwned):
    __tablename__ = "cyber_mappings"
    source_id: Mapped[UUID] = mapped_column(ForeignKey("cyber_sources.id", ondelete="CASCADE"))
    asset_id: Mapped[UUID] = mapped_column(ForeignKey("cyber_assets.id", ondelete="CASCADE"))
    external_namespace: Mapped[str] = mapped_column(String(128))
    external_asset: Mapped[str] = mapped_column(String(128))
    external_component: Mapped[str] = mapped_column(String(128), default="")
    review: Mapped[dict[str, Any]] = mapped_column(JSONB)
    __table_args__ = (
        UniqueConstraint("source_id", "external_namespace", "external_asset", "external_component"),
    )


class CyberPolicy(CyberOwned):
    __tablename__ = "cyber_policies"
    source_id: Mapped[UUID] = mapped_column(ForeignKey("cyber_sources.id", ondelete="CASCADE"))
    version: Mapped[int]
    config: Mapped[dict[str, Any]] = mapped_column(JSONB)
    sha256: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint("source_id", "version"),)


class CyberBaseline(CyberOwned):
    __tablename__ = "cyber_baselines"
    source_id: Mapped[UUID] = mapped_column(ForeignKey("cyber_sources.id", ondelete="CASCADE"))
    revision: Mapped[str] = mapped_column(String(128))
    config: Mapped[dict[str, Any]] = mapped_column(JSONB)
    __table_args__ = (UniqueConstraint("source_id", "revision"),)


class CyberEvent(CyberOwned):
    __tablename__ = "cyber_events"
    source_id: Mapped[UUID] = mapped_column(ForeignKey("cyber_sources.id", ondelete="CASCADE"))
    source_event_id: Mapped[str] = mapped_column(String(128))
    asset_id: Mapped[UUID | None] = mapped_column(ForeignKey("cyber_assets.id", ondelete="CASCADE"))
    mapping_id: Mapped[UUID | None] = mapped_column(ForeignKey("cyber_mappings.id"))
    event_type: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(16))
    run_id: Mapped[str] = mapped_column(String(128), default="")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sha256: Mapped[str] = mapped_column(String(64))
    wire: Mapped[dict[str, Any]] = mapped_column(JSONB)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB)
    __table_args__ = (
        UniqueConstraint("source_id", "source_event_id"),
        Index("ix_cyber_events_window", "source_id", "mode", "run_id", "event_type", "occurred_at"),
        Index("ix_cyber_events_owner_time", "user_id", "created_at", "id"),
    )


class CyberFinding(CyberOwned):
    __tablename__ = "cyber_findings"
    source_id: Mapped[UUID] = mapped_column(ForeignKey("cyber_sources.id", ondelete="CASCADE"))
    asset_id: Mapped[UUID | None] = mapped_column(ForeignKey("cyber_assets.id", ondelete="CASCADE"))
    dedupe_key: Mapped[str] = mapped_column(String(64), unique=True)
    rule: Mapped[str] = mapped_column(String(64))
    rule_version: Mapped[str] = mapped_column(String(32))
    mode: Mapped[str] = mapped_column(String(16))
    run_id: Mapped[str] = mapped_column(String(128))
    severity: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[str] = mapped_column(String(16))
    priority: Mapped[int]
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    occurrences: Mapped[int] = mapped_column(default=1)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB)


class CyberResult(CyberOwned):
    __tablename__ = "cyber_results"
    finding_id: Mapped[UUID] = mapped_column(ForeignKey("cyber_findings.id", ondelete="CASCADE"))
    evidence_key: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    sha256: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint("finding_id", "evidence_key"),)


class CyberInvestigation(CyberOwned):
    __tablename__ = "cyber_investigations"
    title: Mapped[str] = mapped_column(String(160))
    finding_id: Mapped[UUID] = mapped_column(ForeignKey("cyber_findings.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(24), default="open")
    priority: Mapped[int]
    revision: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    acceptance_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    sha256: Mapped[str] = mapped_column(String(64))


class CyberAction(CyberOwned):
    __tablename__ = "cyber_actions"
    investigation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cyber_investigations.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(48))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB)


class CyberReport(CyberOwned):
    __tablename__ = "cyber_reports"
    asset_id: Mapped[UUID] = mapped_column(ForeignKey("cyber_assets.id", ondelete="CASCADE"))
    sha256: Mapped[str] = mapped_column(String(64))
    profile: Mapped[str] = mapped_column(String(48))
    producer: Mapped[str] = mapped_column(String(160))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB)


class CyberSummary(CyberOwned):
    __tablename__ = "cyber_summaries"
    investigation_id: Mapped[UUID] = mapped_column(
        ForeignKey("cyber_investigations.id", ondelete="CASCADE")
    )
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    sha256: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)


OWNED_MODELS = (
    CyberAsset,
    CyberSource,
    CyberMapping,
    CyberPolicy,
    CyberBaseline,
    CyberEvent,
    CyberFinding,
    CyberResult,
    CyberInvestigation,
    CyberAction,
    CyberReport,
    CyberSummary,
)
