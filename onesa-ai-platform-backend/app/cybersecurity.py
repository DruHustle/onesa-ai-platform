"""Independent security workspace. All collection is passive or explicit import."""

import asyncio
import hashlib
import json
import secrets
from datetime import timedelta
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import Response
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app import capacity
from app.auth import DB, Auth, authenticated, digest
from app.cyber_models import (
    OWNED_MODELS,
    CyberAction,
    CyberAsset,
    CyberBaseline,
    CyberEvent,
    CyberFinding,
    CyberInvestigation,
    CyberMapping,
    CyberPolicy,
    CyberReport,
    CyberResult,
    CyberSource,
    CyberSummary,
)
from app.cyber_reports import CycloneDX
from app.cyber_schemas import (
    AssetCreate,
    BaselineCreate,
    Decision,
    Demonstration,
    EvidenceRequest,
    InvestigationCreate,
    MappingCreate,
    PolicyCreate,
    SecurityEvent,
    SourceCreate,
    SummaryRequest,
    bounded_json,
    event_request_contract,
    inline_schema,
    parse_batch,
    utc,
)
from app.cyber_service import (
    RULE_VERSION,
    action_history,
    audit,
    canonical,
    control_coverage,
    evidence_snapshots,
    find,
    ingest,
    list_output,
    lock_owner,
    operator,
    output,
    owned,
    quota,
    scrub,
    sha,
    snapshot,
    visible,
)
from app.errors import fail
from app.inference import ModelMessage
from app.models import Document, User, now

router = APIRouter(prefix="/api/v1/cybersecurity", tags=["cybersecurity v1"])


def enabled(request: Request, db: Session) -> None:
    if not request.app.state.settings.cybersecurity_enabled:
        fail(404, "cybersecurity_disabled", "Cybersecurity is not enabled")
    if not db.scalar(text("SELECT to_regclass('cyber_sources') IS NOT NULL")):
        fail(503, "security_schema_unavailable", "Cybersecurity schema requires owner migration")


@router.get("/readiness")
def readiness(request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    enabled(request, db)
    return {
        "enabled": True,
        "schema": "ot-security-evidence/v1",
        "rules": RULE_VERSION,
        "operator": operator(request, auth[0].id),
        "provider_required": False,
        "native_capture_configured": bool(
            request.app.state.settings.cybersecurity_operator_user_ids
        ),
        "ai_enabled": request.app.state.settings.cybersecurity_ai_enabled,
        "demo_enabled": request.app.state.settings.cybersecurity_demo_enabled,
        "scope": "Owned imports and explicitly configured operator evidence; no "
        "active probing or actuation",
    }


@router.get("/sources/{identifier}")
def source_detail(identifier: UUID, request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    enabled(request, db)
    return output(owned(request, db, CyberSource, identifier, auth[0].id))


@router.get("/policies/{identifier}")
def policy_detail(identifier: UUID, request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    enabled(request, db)
    return output(owned(request, db, CyberPolicy, identifier, auth[0].id))


@router.get("/baselines/{identifier}")
def baseline_detail(identifier: UUID, request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    enabled(request, db)
    return output(owned(request, db, CyberBaseline, identifier, auth[0].id))


@router.get("/workspace")
def workspace(
    request: Request, db: DB, auth: Auth, mode: Literal["live", "simulated", "replay"] = "live"
) -> dict[str, Any]:
    enabled(request, db)
    owner = auth[0].id
    sources = db.scalars(
        visible(request, CyberSource, owner).order_by(CyberSource.created_at).limit(50)
    ).all()
    assets = db.scalars(
        visible(request, CyberAsset, owner).order_by(CyberAsset.name).limit(100)
    ).all()
    events = db.scalars(
        visible(request, CyberEvent, owner)
        .where(CyberEvent.mode == mode)
        .order_by(CyberEvent.created_at.desc(), CyberEvent.id.desc())
        .limit(100)
    ).all()
    findings = db.scalars(
        visible(request, CyberFinding, owner)
        .where(CyberFinding.mode == mode)
        .order_by(CyberFinding.priority.desc(), CyberFinding.last_seen.desc())
        .limit(300)
    ).all()
    cases = db.scalars(
        visible(request, CyberInvestigation, owner)
        .join(CyberFinding)
        .where(CyberFinding.mode == mode)
        .order_by(CyberInvestigation.updated_at.desc())
        .limit(100)
    ).all()
    receipt_times = {
        source_id: received
        for source_id, received in db.execute(
            select(CyberEvent.source_id, func.max(CyberEvent.created_at))
            .where(
                CyberEvent.user_id == owner,
                CyberEvent.mode == mode,
                CyberEvent.source_id.in_([source.id for source in sources]),
            )
            .group_by(CyberEvent.source_id)
        ).all()
    }
    health = []
    for source in sources:
        received = receipt_times.get(source.id)
        latest_health = db.scalar(
            select(CyberEvent)
            .where(
                CyberEvent.source_id == source.id,
                CyberEvent.mode == mode,
                CyberEvent.event_type == "collector.health",
            )
            .order_by(CyberEvent.occurred_at.desc(), CyberEvent.id.desc())
            .limit(1)
        )
        health.append(
            {
                "source_id": str(source.id),
                "revoked": source.revoked_at is not None,
                "state": "revoked"
                if source.revoked_at
                else "unknown"
                if received is None
                else "stale"
                if (now() - received).total_seconds()
                > source.config["expected_interval_seconds"] * 2
                else "fresh",
                "last_received": received.isoformat() if received else None,
                "mode": mode,
                "reported_state": latest_health.wire["attributes"]["state"]
                if latest_health
                and latest_health.expires_at > now()
                and latest_health.wire["quality"] != "bad"
                else None,
            }
        )
    policies = db.scalars(
        visible(request, CyberPolicy, owner).order_by(CyberPolicy.created_at.desc()).limit(200)
    ).all()
    baselines = db.scalars(
        visible(request, CyberBaseline, owner).order_by(CyberBaseline.created_at.desc()).limit(100)
    ).all()
    mappings = db.scalars(
        visible(request, CyberMapping, owner).order_by(CyberMapping.created_at.desc()).limit(200)
    ).all()
    assessed = {
        e.asset_id
        for e in events
        if e.asset_id and e.expires_at > now() and e.wire["quality"] == "good"
    }
    stale = {e.asset_id for e in events if e.asset_id and e.expires_at <= now()} - assessed
    return {
        "assets": [list_output(a) for a in assets],
        "sources": [list_output(s) for s in sources],
        "events": [output(e) for e in events],
        "findings": [list_output(f) for f in findings],
        "investigations": [list_output(c) for c in cases],
        "source_health": health,
        "policies": [list_output(p) for p in policies],
        "baselines": [list_output(b) for b in baselines],
        "mappings": [list_output(m) for m in mappings],
        "coverage": {
            "assets": len(assets),
            "assessed": len(assessed),
            "stale": len(stale),
            "unknown": max(0, len(assets) - len(assessed) - len(stale)),
            "definition": "At least one unexpired good-quality mapped observation in the "
            "selected mode; not control compliance",
            "window": "Most recent 100 events; bounded view, not a complete historical assessment",
        },
        "control_coverage": control_coverage(db, request, owner, assets, sources, baselines, mode),
        "counts": {
            "findings": len(findings),
            "affected_assets": len({f.asset_id for f in findings if f.asset_id}),
            "open_investigations": sum(c.status not in {"resolved", "dismissed"} for c in cases),
        },
        "bounded": {"events": 100, "findings": 300, "investigations": 100},
        "mode": mode,
    }


@router.post("/assets", status_code=201)
def create_asset(body: AssetCreate, request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    enabled(request, db)
    lock_owner(db, auth[0].id)
    quota(db, CyberAsset, auth[0].id, 100)
    twin_link = None
    if body.twin_component_id is not None and body.twin_asset_id is None:
        fail(422, "twin_mapping_required", "Select an owned Twin asset before its component")
    if body.twin_asset_id:
        from app.twin_models import TwinAsset
        from app.twins import component
        from app.twins import owned as twin_owned

        twin = twin_owned(db, TwinAsset, body.twin_asset_id, auth[0].id)
        if body.twin_component_id:
            component(twin, body.twin_component_id)
        twin_link = {
            "asset_id": str(twin.id),
            "component_id": str(body.twin_component_id) if body.twin_component_id else None,
            "asset_revision": twin.revision,
            "model_revision_id": str(twin.active_model_id)
            if twin.active_model_id
            else twin.definition.get("review_model_id"),
        }
    row = CyberAsset(
        user_id=auth[0].id,
        name=body.name,
        identity=body.identity,
        zone=body.zone,
        criticality=body.criticality,
        details=scrub(
            {"review_note": body.review_note, "reviewer": "owner_self_review", "twin": twin_link}
        ),
    )
    db.add(row)
    try:
        db.flush()
        audit(db, auth[0].id, "asset_reviewed", {"asset_id": str(row.id)})
        db.commit()
    except IntegrityError:
        db.rollback()
        fail(409, "asset_identity_conflict", "This local asset identity already exists")
    return output(row)


@router.post("/sources", status_code=201)
def create_source(body: SourceCreate, request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    enabled(request, db)
    lock_owner(db, auth[0].id)
    quota(db, CyberSource, auth[0].id, 30)
    if body.namespace in {
        "onesa-application",
        "onesa-owned-configuration",
        "onesa-security-demonstration",
    }:
        fail(422, "reserved_producer", "The native application namespace is operator configured")
    token = secrets.token_urlsafe(32)
    row = CyberSource(
        user_id=auth[0].id,
        name=body.name,
        namespace=body.namespace,
        token_hash=digest(token),
        config=body.model_dump(exclude={"name", "namespace"}),
    )
    db.add(row)
    try:
        db.flush()
        config = PolicyCreate(review_note=body.review_note).model_dump()
        db.add(
            CyberPolicy(
                user_id=auth[0].id, source_id=row.id, version=1, config=config, sha256=sha(config)
            )
        )
        audit(
            db,
            auth[0].id,
            "source_created",
            {"source_id": str(row.id), "review": "owner_self_review"},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        fail(409, "source_identity_conflict", "This producer namespace already exists")
    return {
        **output(row),
        "ingestion_token": token,
        "credential_notice": "Shown once; keep in the collector's private credential store",
    }


@router.post("/sources/{identifier}/revoke")
def revoke_source(identifier: UUID, request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    enabled(request, db)
    lock_owner(db, auth[0].id)
    row = owned(request, db, CyberSource, identifier, auth[0].id, lock=True)
    if row.scope != "owner":
        fail(
            409,
            "native_source_configuration",
            "Disable native collection through reviewed operator configuration",
        )
    row.revoked_at = row.revoked_at or now()
    row.token_hash = None
    audit(db, auth[0].id, "source_revoked", {"source_id": str(row.id)})
    db.commit()
    return output(row)


@router.post("/sources/{identifier}/mappings", status_code=201)
def create_mapping(
    identifier: UUID, body: MappingCreate, request: Request, db: DB, auth: Auth
) -> dict[str, Any]:
    enabled(request, db)
    lock_owner(db, auth[0].id)
    source = owned(request, db, CyberSource, identifier, auth[0].id, lock=True)
    owned(request, db, CyberAsset, body.asset_id, auth[0].id)
    quota(db, CyberMapping, auth[0].id, 200)
    if source.scope == "operator":
        fail(
            422,
            "native_asset_scope",
            "Global application evidence cannot be mapped to arbitrary equipment",
        )
    row = CyberMapping(
        user_id=auth[0].id,
        source_id=source.id,
        asset_id=body.asset_id,
        external_namespace=body.namespace,
        external_asset=body.external_asset,
        external_component=body.external_component or "",
        review=scrub({"note": body.review_note, "reviewer": "owner_self_review"}),
    )
    db.add(row)
    try:
        db.flush()
        audit(db, auth[0].id, "mapping_reviewed", {"mapping_id": str(row.id)})
        db.commit()
    except IntegrityError:
        db.rollback()
        fail(
            409,
            "mapping_conflict",
            "Reviewed mappings are immutable; register a new external identity",
        )
    return output(row)


@router.post("/sources/{identifier}/policies", status_code=201)
def create_policy(
    identifier: UUID, body: PolicyCreate, request: Request, db: DB, auth: Auth
) -> dict[str, Any]:
    enabled(request, db)
    lock_owner(db, auth[0].id)
    source = owned(request, db, CyberSource, identifier, auth[0].id, lock=True)
    quota(db, CyberPolicy, auth[0].id, 200)
    previous = db.scalar(
        select(CyberPolicy)
        .where(CyberPolicy.source_id == source.id)
        .order_by(CyberPolicy.version.desc())
        .limit(1)
    )
    config = scrub(body.model_dump())
    row = CyberPolicy(
        user_id=auth[0].id,
        sensitive=source.sensitive,
        source_id=source.id,
        version=previous.version + 1 if previous else 1,
        config=config,
        sha256=sha(config),
    )
    db.add(row)
    db.flush()
    audit(
        db,
        auth[0].id,
        "policy_reviewed",
        {"source_id": str(source.id), "sha256": row.sha256},
        sensitive=source.sensitive,
    )
    db.commit()
    if not source.sensitive:
        request.state.security_change = {
            "owner": str(auth[0].id),
            "revision": row.sha256,
            "changed_keys": ["security_detection_policy"],
        }
    return output(row)


@router.post("/sources/{identifier}/baselines", status_code=201)
def create_baseline(
    identifier: UUID, body: BaselineCreate, request: Request, db: DB, auth: Auth
) -> dict[str, Any]:
    enabled(request, db)
    lock_owner(db, auth[0].id)
    source = owned(request, db, CyberSource, identifier, auth[0].id, lock=True)
    quota(db, CyberBaseline, auth[0].id, 100)
    row = CyberBaseline(
        user_id=auth[0].id,
        sensitive=source.sensitive,
        source_id=source.id,
        revision=body.revision,
        config=body.model_dump(exclude={"revision"}),
    )
    db.add(row)
    try:
        db.flush()
        audit(
            db,
            auth[0].id,
            "baseline_reviewed",
            {"source_id": str(source.id), "revision": row.revision},
            sensitive=source.sensitive,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        fail(409, "baseline_conflict", "Baseline revisions are immutable")
    return output(row)


async def read_events(request: Request) -> list[SecurityEvent]:
    content = request.headers.get("content-type", "").split(";", 1)[0]
    if content not in {"application/json", "application/x-ndjson"}:
        fail(415, "security_format", "Use application/json or application/x-ndjson")
    try:
        return parse_batch(await request.body(), content == "application/x-ndjson")
    except (ValueError, UnicodeError, RecursionError):
        fail(
            422,
            "security_event_invalid",
            "Use the bounded ot-security-evidence/v1 profile and real UTC timestamps",
        )


@router.post("/sources/{identifier}/imports", openapi_extra=event_request_contract())
async def import_events(identifier: UUID, request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    enabled(request, db)
    source = owned(request, db, CyberSource, identifier, auth[0].id)
    if source.scope != "owner":
        fail(403, "native_source_scope", "External data cannot impersonate application decisions")
    events = await read_events(request)
    result = await run_in_threadpool(ingest, db, request, source, events, "session_import")
    db.commit()
    return result


@router.post("/ingest", openapi_extra=event_request_contract())
async def credential_ingest(
    request: Request, db: DB, authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    enabled(request, db)
    token = (authorization or "").removeprefix("Bearer ")
    if not authorization or not authorization.startswith("Bearer ") or not 40 <= len(token) <= 100:
        fail(401, "source_credential_required", "A scoped source credential is required")
    source = db.scalar(
        select(CyberSource).where(
            CyberSource.token_hash == digest(token), CyberSource.revoked_at.is_(None)
        )
    )
    if source is None or source.scope != "owner":
        fail(401, "source_credential_required", "A scoped source credential is required")
    events = await read_events(request)
    result = await run_in_threadpool(ingest, db, request, source, events, "scoped_collector")
    db.commit()
    return result


@router.get("/events")
def events(
    request: Request,
    db: DB,
    auth: Auth,
    q: str = Query(default="", max_length=128),
    mode: Literal["live", "simulated", "replay"] = "live",
    before: UUID | None = None,
    source_id: UUID | None = None,
    asset_id: UUID | None = None,
) -> dict[str, Any]:
    enabled(request, db)
    stmt = visible(request, CyberEvent, auth[0].id).where(CyberEvent.mode == mode)
    if source_id:
        owned(request, db, CyberSource, source_id, auth[0].id)
        stmt = stmt.where(CyberEvent.source_id == source_id)
    if asset_id:
        owned(request, db, CyberAsset, asset_id, auth[0].id)
        stmt = stmt.where(CyberEvent.asset_id == asset_id)
    if q:
        # SQLAlchemy contains(autoescape) makes wildcard input literal.
        stmt = stmt.where(CyberEvent.wire["summary"].astext.contains(q, autoescape=True))
    if before:
        cursor = owned(request, db, CyberEvent, before, auth[0].id)
        stmt = stmt.where(
            text("(cyber_events.created_at, cyber_events.id) < (:cursor_at, :cursor_id)")
        ).params(cursor_at=cursor.created_at, cursor_id=cursor.id)
    rows = db.scalars(
        stmt.order_by(CyberEvent.created_at.desc(), CyberEvent.id.desc()).limit(101)
    ).all()
    return {
        "items": [output(row) for row in rows[:100]],
        "next": str(rows[99].id) if len(rows) > 100 else None,
    }


@router.get("/findings/{identifier}")
def finding_detail(identifier: UUID, request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    enabled(request, db)
    row = owned(request, db, CyberFinding, identifier, auth[0].id)
    return {
        "finding": output(row),
        "source": output(owned(request, db, CyberSource, row.source_id, auth[0].id)),
        "asset": output(owned(request, db, CyberAsset, row.asset_id, auth[0].id))
        if row.asset_id
        else None,
        "results": [
            output(r)
            for r in db.scalars(
                visible(request, CyberResult, auth[0].id)
                .where(CyberResult.finding_id == row.id)
                .order_by(CyberResult.created_at.desc())
                .limit(20)
            )
        ],
    }


@router.post("/investigations", status_code=201)
def create_investigation(
    body: InvestigationCreate, request: Request, db: DB, auth: Auth
) -> dict[str, Any]:
    enabled(request, db)
    lock_owner(db, auth[0].id)
    finding = owned(request, db, CyberFinding, body.finding_id, auth[0].id, lock=True)
    quota(db, CyberInvestigation, auth[0].id, 100)
    saved = {
        "finding": output(finding),
        "source": output(owned(request, db, CyberSource, finding.source_id, auth[0].id)),
        "asset": output(owned(request, db, CyberAsset, finding.asset_id, auth[0].id))
        if finding.asset_id
        else None,
        "review": "owner_self_review",
        "captured_at": now().isoformat(),
    }
    if len(canonical(saved)) > 98304:
        fail(
            413,
            "investigation_snapshot_bound",
            "Investigation snapshot exceeds 96 KiB; narrow the reviewed scope",
        )
    row = CyberInvestigation(
        user_id=auth[0].id,
        sensitive=finding.sensitive,
        title=scrub(body.title),
        finding_id=finding.id,
        priority=finding.priority,
        snapshot=saved,
        sha256=sha(saved),
    )
    db.add(row)
    db.flush()
    audit(
        db,
        auth[0].id,
        "opened",
        {"snapshot_sha256": row.sha256, "assigned_to": "current_owner"},
        row,
    )
    db.commit()
    return output(row)


@router.get("/investigations/{identifier}")
def investigation_detail(identifier: UUID, request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    enabled(request, db)
    row = owned(request, db, CyberInvestigation, identifier, auth[0].id)
    return {
        "investigation": output(row),
        "evidence": snapshot(db, request, row),
        "summaries": [
            {
                "id": str(report.id),
                "created_at": report.created_at.isoformat(),
                "sha256": report.sha256,
                "result": report.result,
            }
            for report in db.scalars(
                visible(request, CyberSummary, auth[0].id)
                .where(CyberSummary.investigation_id == row.id)
                .order_by(CyberSummary.created_at.desc())
                .limit(100)
            )
        ],
        "acceptance_expired": row.status == "accepted_risk"
        and row.acceptance_until is not None
        and row.acceptance_until <= now(),
    }


@router.get("/investigations/{identifier}/actions")
def decisions_page(
    identifier: UUID, request: Request, db: DB, auth: Auth, before: UUID | None = None
) -> dict[str, Any]:
    enabled(request, db)
    row = owned(request, db, CyberInvestigation, identifier, auth[0].id)
    return action_history(db, request, row, before)


@router.get("/actions/{identifier}")
def decision_snapshot(identifier: UUID, request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    enabled(request, db)
    row = owned(request, db, CyberAction, identifier, auth[0].id)
    return output(row)


@router.get("/events/{identifier}")
def event_detail(identifier: UUID, request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    enabled(request, db)
    return output(owned(request, db, CyberEvent, identifier, auth[0].id))


@router.post("/investigations/{identifier}/decisions")
def decision(
    identifier: UUID, body: Decision, request: Request, db: DB, auth: Auth
) -> dict[str, Any]:
    enabled(request, db)
    lock_owner(db, auth[0].id)
    row = owned(request, db, CyberInvestigation, identifier, auth[0].id, lock=True)
    if row.revision != body.revision:
        fail(409, "investigation_revision", "Reload this investigation before recording a decision")
    finding = owned(request, db, CyberFinding, row.finding_id, auth[0].id)
    evidence = [
        owned(request, db, CyberEvent, identifier, auth[0].id) for identifier in body.evidence_ids
    ]
    if any(
        e.source_id != finding.source_id
        or e.asset_id != finding.asset_id
        or e.mode != finding.mode
        or e.run_id != finding.run_id
        for e in evidence
    ):
        fail(
            422,
            "decision_evidence_scope",
            "Decision evidence must match this finding's source, asset and mode",
        )
    if body.action == "resolve" and not evidence:
        fail(
            422,
            "resolution_evidence_required",
            "Resolution requires supporting evidence and a reason",
        )
    expires = None
    if body.action == "accept_risk":
        try:
            expires = utc(body.acceptance_until or "")
        except ValueError:
            fail(422, "risk_expiry", "Risk acceptance needs a real UTC expiry within 30 days")
        if not now() < expires <= now() + timedelta(days=30):
            fail(422, "risk_expiry", "Risk acceptance needs a real UTC expiry within 30 days")
    transitions = {
        "acknowledge": "acknowledged",
        "investigate": "investigating",
        "resolve": "resolved",
        "dismiss": "dismissed",
        "accept_risk": "accepted_risk",
        "reopen": "open",
    }
    previous = row.status
    if body.action != "note":
        row.status = transitions[body.action]
        row.acceptance_until = expires
    row.revision += 1
    row.updated_at = now()
    audit(
        db,
        auth[0].id,
        body.action,
        {
            "note": body.note,
            "previous": previous,
            "status": row.status,
            "acceptance_until": expires.isoformat() if expires else None,
            "evidence": evidence_snapshots(evidence),
            "evidence_references": [{"id": str(e.id), "sha256": e.sha256} for e in evidence],
            "finding_at_decision": output(finding),
            "review": "owner_self_review",
            "remediation_proven": False,
        },
        row,
    )
    db.commit()
    return output(row)


@router.get("/export")
def export_events(
    request: Request,
    db: DB,
    auth: Auth,
    mode: Literal["live", "simulated", "replay"] = "live",
    format: Literal["json", "ndjson"] = "json",
    source_id: UUID | None = None,
    before: UUID | None = None,
) -> Response:
    enabled(request, db)
    stmt = visible(request, CyberEvent, auth[0].id).where(CyberEvent.mode == mode)
    if source_id:
        owned(request, db, CyberSource, source_id, auth[0].id)
        stmt = stmt.where(CyberEvent.source_id == source_id)
    if before:
        cursor = owned(request, db, CyberEvent, before, auth[0].id)
        if cursor.mode != mode or (source_id and cursor.source_id != source_id):
            fail(404, "security_not_found", "Export cursor does not belong to this scope")
        stmt = stmt.where(text("(cyber_events.created_at,cyber_events.id)<(:at,:id)"))
        stmt = stmt.params(at=cursor.created_at, id=cursor.id)
    rows = db.scalars(
        stmt.order_by(CyberEvent.created_at.desc(), CyberEvent.id.desc()).limit(101)
    ).all()
    wire = [SecurityEvent.model_validate(row.wire).wire() for row in rows[:100]]
    raw = (
        b"\n".join(canonical(event) for event in wire)
        if format == "ndjson"
        else canonical({"events": wire})
    )
    return Response(
        raw,
        media_type="application/x-ndjson" if format == "ndjson" else "application/json",
        headers={
            "Content-Disposition": f'attachment; filename="onesa-security.{format}"',
            "X-Content-Type-Options": "nosniff",
            "X-Exported-Events": str(len(wire)),
            **({"X-Next-Cursor": str(rows[99].id)} if len(rows) > 100 else {}),
        },
    )


@router.get("/assets/{identifier}")
def asset_detail(identifier: UUID, request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    enabled(request, db)
    asset = owned(request, db, CyberAsset, identifier, auth[0].id)
    return {
        "asset": output(asset),
        "findings": [
            list_output(f)
            for f in db.scalars(
                visible(request, CyberFinding, auth[0].id)
                .where(CyberFinding.asset_id == asset.id)
                .limit(100)
            )
        ],
        "reports": [
            report_metadata(r)
            for r in db.scalars(
                visible(request, CyberReport, auth[0].id)
                .where(CyberReport.asset_id == asset.id)
                .limit(20)
            )
        ],
        "posture": "Evidence coverage only; unassessed controls remain unknown",
    }


def report_metadata(row: CyberReport) -> dict[str, Any]:
    document = row.details["document"]
    return {
        "id": str(row.id),
        "created_at": row.created_at.isoformat(),
        "asset_id": str(row.asset_id),
        "sha256": row.sha256,
        "profile": row.profile,
        "producer": row.producer,
        "mode": row.details["mode"],
        "component_count": len(document["components"]),
        "advisory_count": len(document["vulnerabilities"]),
        "exploitability": "unverified",
    }


@router.get("/reports/{identifier}")
def report_detail(identifier: UUID, request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    enabled(request, db)
    return output(owned(request, db, CyberReport, identifier, auth[0].id))


@router.get("/twins/{identifier}/summary")
def twin_summary(identifier: UUID, request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    enabled(request, db)
    from app.twin_models import TwinAsset
    from app.twins import owned as twin_owned

    twin = twin_owned(db, TwinAsset, identifier, auth[0].id)
    linked = [
        a
        for a in db.scalars(visible(request, CyberAsset, auth[0].id).limit(100))
        if (a.details.get("twin") or {}).get("asset_id") == str(twin.id)
    ]
    items = []
    for asset in linked:
        link = asset.details["twin"]
        valid = link["asset_revision"] == twin.revision and link["model_revision_id"] == (
            str(twin.active_model_id)
            if twin.active_model_id
            else twin.definition.get("review_model_id")
        )
        for finding in db.scalars(
            visible(request, CyberFinding, auth[0].id)
            .where(CyberFinding.asset_id == asset.id)
            .limit(100)
        ):
            items.append(
                {
                    "finding_id": str(finding.id),
                    "rule": finding.rule,
                    "severity": finding.severity,
                    "mode": finding.mode,
                    "component_id": link["component_id"] if valid else None,
                    "mapping_current": valid,
                    "last_seen": finding.last_seen.isoformat(),
                }
            )
    return {
        "items": items,
        "scope": "Reviewed links only; findings do not establish equipment compromise",
    }


def account_export(db: Session, owner: UUID) -> dict[str, Any]:
    # Global sanitized operator records are excluded from personal account exports.
    return {
        cls.__tablename__: [
            output(row)
            for row in db.scalars(
                select(cls)
                .where(cls.user_id == owner, cls.sensitive.is_(False))
                .order_by(cls.created_at, cls.id)
                .limit(10001)
            )
        ]
        for cls in OWNED_MODELS
    }


@router.post("/assess")
def assess(request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    """Explicit receiver-clock assessment. Coverage loss is never called compromise."""
    from app.cyber_service import evaluate

    enabled(request, db)
    lock_owner(db, auth[0].id)
    sources = db.scalars(
        visible(request, CyberSource, auth[0].id)
        .where(CyberSource.revoked_at.is_(None))
        .order_by(CyberSource.id)
        .with_for_update()
        .limit(50)
    ).all()
    for source in sources:
        reference = source.last_seen_at or source.created_at
        deadline = reference + timedelta(seconds=source.config["expected_interval_seconds"] * 2)
        policy = db.scalar(
            select(CyberPolicy)
            .where(CyberPolicy.source_id == source.id)
            .order_by(CyberPolicy.version.desc())
            .limit(1)
        )
        if source.scope == "owner" and "live" in source.config["modes"] and now() > deadline:
            find(
                db,
                source,
                "collector_freshness",
                "live",
                "",
                None,
                "low",
                [],
                "Expected source delivery is overdue at the receiver. This is a monitoring "
                "coverage gap, not proof of compromise.",
                {"expected_interval_seconds": source.config["expected_interval_seconds"]},
                {
                    "last_received": source.last_seen_at.isoformat()
                    if source.last_seen_at
                    else None,
                    "deadline": deadline.isoformat(),
                    "basis": "receiver_clock_and_reviewed_interval",
                },
                policy,
            )
        certificates = db.scalars(
            select(CyberEvent)
            .where(
                CyberEvent.source_id == source.id,
                CyberEvent.event_type == "tls.certificate_observed",
                CyberEvent.expires_at > now(),
            )
            .order_by(CyberEvent.occurred_at.desc())
            .limit(20)
        ).all()
        for event in certificates:
            evaluate(db, source, event)
    db.commit()
    return {
        "assessed_sources": len(sources),
        "scope": "Configured delivery intervals and retained certificate metadata only",
    }


@router.post("/demo")
def demonstration(body: Demonstration, request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    enabled(request, db)
    config = request.app.state.settings
    if not config.cybersecurity_demo_enabled or config.environment == "production":
        fail(404, "security_demo_disabled", "Explicit isolated demonstration is not enabled")
    lock_owner(db, auth[0].id)
    source = db.scalar(
        select(CyberSource).where(
            CyberSource.user_id == auth[0].id,
            CyberSource.namespace == "onesa-security-demonstration",
        )
    )
    if source is None:
        quota(db, CyberSource, auth[0].id, 30)
        source = CyberSource(
            user_id=auth[0].id,
            name="Explicitly simulated security demonstration",
            namespace="onesa-security-demonstration",
            scope="demonstration",
            token_hash=None,
            config={
                "modes": ["simulated", "replay"],
                "expected_interval_seconds": 3600,
                "endpoint_refs": [],
                "review": "Owner explicitly requested synthetic fixture",
            },
        )
        db.add(source)
        db.flush()
        policy = PolicyCreate(
            review_note="Explicit synthetic demonstration; no attack claim"
        ).model_dump()
        db.add(
            CyberPolicy(
                user_id=auth[0].id,
                source_id=source.id,
                version=1,
                config=policy,
                sha256=sha(policy),
            )
        )
        db.flush()
    prefix = "demo-" + sha([body.mode, body.run_id])[:32] + "-"
    existing = db.scalars(
        select(CyberEvent)
        .where(CyberEvent.source_id == source.id, CyberEvent.source_event_id.startswith(prefix))
        .order_by(CyberEvent.source_event_id)
    ).all()
    if existing:
        return {
            "created": False,
            "mode": body.mode,
            "run_id": body.run_id,
            "event_ids": [str(e.id) for e in existing],
        }
    events = [
        SecurityEvent.model_validate(
            {
                "schemaVersion": "ot-security-evidence/v1",
                "producerNamespace": source.namespace,
                "sourceEventId": prefix + str(index),
                "occurredAt": (now() - timedelta(seconds=index)).isoformat(),
                "mode": body.mode,
                **(
                    {"scenarioRunId": body.run_id}
                    if body.mode == "simulated"
                    else {"replayRunId": body.run_id}
                ),
                "eventType": "auth.authentication_failed",
                "assetRef": None,
                "summary": "Explicit synthetic failed-authentication example; not a real incident.",
                "quality": "good",
                "producerVersion": "onesa-demo/1",
                "attributes": {
                    "service": "isolated-demonstration",
                    "outcome": "denied",
                    "reasonCode": "SYNTHETIC_REJECTION",
                },
            }
        )
        for index in range(5)
    ]
    result = ingest(db, request, source, events, "explicit_demonstration")
    db.commit()
    return {"created": True, "mode": body.mode, "run_id": body.run_id, **result}


@router.post(
    "/sources/{identifier}/reports",
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": inline_schema(CycloneDX)}},
        }
    },
)
async def import_report(
    identifier: UUID,
    asset_id: UUID,
    request: Request,
    db: DB,
    auth: Auth,
    mode: Literal["live", "simulated", "replay"] = "live",
    run_id: str = Query(default="", max_length=128),
) -> dict[str, Any]:
    from app.cyber_reports import raw_sha

    enabled(request, db)
    lock_owner(db, auth[0].id)
    source = owned(request, db, CyberSource, identifier, auth[0].id, lock=True)
    asset = owned(request, db, CyberAsset, asset_id, auth[0].id)
    if (
        source.scope != "owner"
        or source.revoked_at is not None
        or mode not in source.config["modes"]
    ):
        fail(422, "report_scope", "Select an owned source with this mode enabled")
    if mode == "live" and run_id:
        fail(422, "report_mode", "Live inventory must not claim a simulated or replay run")
    if mode != "live":
        try:
            Demonstration(mode=mode, run_id=run_id)
        except ValueError:
            fail(422, "report_mode", "Simulated or replay inventory requires a nonblank run ID")
    mapping = db.scalar(
        select(CyberMapping)
        .where(CyberMapping.source_id == source.id, CyberMapping.asset_id == asset.id)
        .limit(1)
    )
    if mapping is None:
        fail(
            422,
            "mapping_review_required",
            "Review a source-to-asset mapping before importing an inventory",
        )
    raw = await request.body()
    try:
        report = CycloneDX.model_validate(bounded_json(raw, 2 * 1048576))
    except (ValueError, UnicodeError, RecursionError):
        fail(
            422,
            "inventory_profile",
            "Prepare the documented CycloneDX 1.6 flat subset: at most 250 "
            "components, 100 vulnerabilities, tool name/version and UTC "
            "timestamp; unsupported fields must be removed",
        )
    digest_value = raw_sha(raw)
    duplicate = db.scalar(
        select(CyberReport).where(
            CyberReport.user_id == auth[0].id,
            CyberReport.asset_id == asset.id,
            CyberReport.sha256 == digest_value,
            CyberReport.details["source_id"].astext == str(source.id),
            CyberReport.details["mode"].astext == mode,
            CyberReport.details["run_id"].astext == run_id,
        )
    )
    if duplicate:
        return {**output(duplicate), "duplicate": True}
    quota(db, CyberReport, auth[0].id, 20)
    producer = report.metadata.tools.components[0]
    row = CyberReport(
        user_id=auth[0].id,
        asset_id=asset.id,
        sha256=digest_value,
        profile="cyclonedx-1.6-flat/1",
        producer=f"{producer.name}/{producer.version}",
        details=scrub(
            {
                "document": report.model_dump(by_alias=True, exclude_none=True),
                "source_id": str(source.id),
                "matching": "explicit report bom-ref; reported applicability only",
                "catalog": "offline imported snapshot; no external feed",
                "mode": mode,
                "run_id": run_id,
                "exploitability": "unverified",
            }
        ),
    )
    db.add(row)
    db.flush()
    event = SecurityEvent.model_validate(
        {
            "schemaVersion": "ot-security-evidence/v1",
            "producerNamespace": source.namespace,
            "sourceEventId": "inventory-" + sha([digest_value, mode, run_id]),
            "occurredAt": report.metadata.timestamp,
            "mode": mode,
            **(
                {"scenarioRunId": run_id}
                if mode == "simulated"
                else {"replayRunId": run_id}
                if mode == "replay"
                else {}
            ),
            "eventType": "software.inventory_observed",
            "assetRef": {
                "namespace": mapping.external_namespace,
                "assetId": mapping.external_asset,
                "componentId": mapping.external_component or None,
            },
            "summary": "Owner-imported software inventory; reported vulnerabilities "
            "require review.",
            "quality": "uncertain",
            "producerVersion": producer.version,
            "attributes": {"inventoryRef": str(row.id), "sha256": digest_value},
        }
    )
    result = ingest(db, request, source, [event], "report_import")
    evidence = db.scalar(
        select(CyberEvent).where(
            CyberEvent.source_id == source.id, CyberEvent.source_event_id == event.sourceEventId
        )
    )
    policy = db.scalar(
        select(CyberPolicy)
        .where(CyberPolicy.source_id == source.id)
        .order_by(CyberPolicy.version.desc())
        .limit(1)
    )
    for vulnerability in report.vulnerabilities:
        matches = [c for c in report.components if c.ref in {a.ref for a in vulnerability.affects}]
        ratings = vulnerability.ratings
        rank = {"none": 0, "info": 0, "unknown": 0, "low": 1, "medium": 2, "high": 3, "critical": 3}
        severity = ["info", "low", "medium", "high"][
            max((rank[r.severity] for r in ratings), default=0)
        ]
        find(
            db,
            source,
            "reported_vulnerability:" + sha(vulnerability.id)[:16],
            mode,
            run_id,
            asset.id,
            severity,
            [evidence] if evidence else [],
            "The imported report explicitly associates an advisory with "
            "inventory references; exploitability is not verified.",
            "Reviewed applicability and remediation evidence",
            {
                "advisory": vulnerability.id,
                "components": [
                    {
                        "ref": c.ref,
                        "name": c.name,
                        "version": c.version,
                        "applicability": "reported_match"
                        if c.version
                        else "candidate_unknown_version",
                    }
                    for c in matches[:20]
                ],
                "reported_match_count": len(matches),
            },
            policy,
            {
                "report_id": str(row.id),
                "report_sha256": row.sha256,
                "advisory_ratings": [r.model_dump(exclude_none=True) for r in ratings],
                "exploitability": "unverified",
            },
        )
    audit(db, auth[0].id, "inventory_imported", {"report_id": str(row.id), "sha256": row.sha256})
    db.commit()
    return {**output(row), "ingestion": result}


def read_evidence(
    request: Request, db: Session, owner: UUID, body: EvidenceRequest
) -> dict[str, Any]:
    enabled(request, db)
    # Refresh eligibility and evidence after inference or a concurrent revocation.
    db.expire_all()
    identity = authenticated(request, db, request.cookies.get("onesa_session"))
    if identity[0].id != owner:
        fail(403, "source_access_denied", "Evidence access is no longer available")
    row = owned(request, db, CyberInvestigation, body.investigation_id, owner)
    if row.sha256 != body.expected_sha256:
        fail(409, "security_snapshot_changed", "Select the saved investigation evidence again")
    if sha(row.snapshot) != row.sha256:
        fail(503, "security_snapshot_integrity", "Saved evidence failed its checksum check")
    finding = owned(request, db, CyberFinding, row.finding_id, owner)
    source = owned(request, db, CyberSource, finding.source_id, owner)
    projection = output(finding)
    details = dict(finding.details)
    details["evidence"] = details["evidence"][-8:]
    references = details.get("evidence_references", [])
    details["evidence_references"] = references[-20:]
    details["omitted_reference_count"] = max(0, len(references) - 20)
    projection["details"] = details
    asset = owned(request, db, CyberAsset, finding.asset_id, owner) if finding.asset_id else None
    result: dict[str, Any] = {
        "investigation_id": str(row.id),
        "original_sha256": row.sha256,
        "finding": projection,
        "source": {
            "id": str(source.id),
            "namespace": source.namespace,
            "scope": source.scope,
            "revoked": source.revoked_at is not None,
            "last_received": source.last_seen_at.isoformat() if source.last_seen_at else None,
        },
        "asset": {
            "id": str(asset.id),
            "name": asset.name,
            "zone": asset.zone,
            "criticality": asset.criticality,
            "reviewed_twin": asset.details.get("twin"),
        }
        if asset
        else None,
        "mode": finding.mode,
        "rule_version": finding.rule_version,
        "original_evidence_sha256": sha(row.snapshot),
        "timeline": [
            {
                "kind": action.kind,
                "at": action.created_at.isoformat(),
                "note": str(action.details.get("note", ""))[:240],
            }
            for action in db.scalars(
                visible(request, CyberAction, owner)
                .where(CyberAction.investigation_id == row.id)
                .order_by(CyberAction.created_at.desc())
                .limit(8)
            )
        ],
        "missing": ["Device attestation", "Verified exploitability", "Independent review"],
        "checklist": [
            "Review source, mode and freshness",
            "Validate asset mapping and affected scope",
            "Compare against approved baseline",
            "Record a human decision with cited evidence",
        ],
        "cause": "not_established",
        "timeline_limit": 8,
    }
    while len(canonical(result)) > 16000 and details["evidence"]:
        details["evidence"] = details["evidence"][1:]
    if len(canonical(result)) > 16000:
        for key in ["observed", "expected"]:
            value = details[key]
            details[key] = {
                "omitted": True,
                "sha256": sha(value),
                "reason": "Tool fact budget; inspect the authorized finding detail",
            }
        result["missing"].append("Detailed facts exceed tool budget; model assistance must abstain")
    result["bounded_bytes"] = 16384
    return result


@router.post("/tools/evidence")
def evidence_tool(body: EvidenceRequest, request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    return read_evidence(request, db, auth[0].id, body)


@router.post("/summaries", status_code=201)
async def summary(body: SummaryRequest, request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    facts = await run_in_threadpool(read_evidence, request, db, auth[0].id, body)
    docs = []
    for identifier in body.document_ids:
        document = db.scalar(
            select(Document).where(Document.id == identifier, Document.user_id == auth[0].id)
        )
        if document is None:
            fail(404, "document_not_found", "Authorized ready guidance document not found")
        docs.append(
            {
                "document_id": str(document.id),
                "text": document.text[:3000],
                "sha256": hashlib.sha256(document.text.encode()).hexdigest(),
            }
        )
    context = {
        "evidence": facts,
        "guidance": docs,
        "question": scrub(body.question),
        "prompt_version": "onesa-cybersecurity-assistance/1",
    }
    if len(canonical(context)) > 65536:
        fail(
            413,
            "security_report_bound",
            "Reduce selected guidance to fit the 64 KiB report snapshot limit",
        )
    context_sha = sha(context)
    # No hidden fallback: deterministic checklist remains available without a provider.
    result: dict[str, Any] = {
        "status": "deterministic",
        "checklist": facts["checklist"],
        "observed": facts["finding"]["details"]["explanation"],
        "hypotheses": [],
        "provider": "not_requested",
        "human_review_required": True,
        "missing_information": facts["missing"],
        "evidence_context": {
            "sha256": context_sha,
            "mode": facts["mode"],
            "included_event_bodies": len(facts["finding"]["details"]["evidence"]),
            "omitted_references": facts["finding"]["details"]["omitted_reference_count"],
            "timeline_limit": facts["timeline_limit"],
        },
    }
    if body.assist:
        if not request.app.state.settings.cybersecurity_ai_enabled:
            result.update(status="abstained", provider="data_policy_not_enabled")
        elif len(canonical(context)) > 24000 or any(
            "Detailed facts exceed" in item for item in facts["missing"]
        ):
            result.update(status="abstained", provider="context_incomplete")
        else:
            lease = await run_in_threadpool(capacity.begin, request)
            try:
                raw = ""
                async with asyncio.timeout(30):
                    async for chunk in request.app.state.model_client.stream(
                        [
                            ModelMessage(
                                role="system",
                                content="Untrusted security evidence follows. Return only JSON "
                                '{"hypotheses":[{"statement":STRING,"citations":[ID]}]}. At '
                                "most 3 hypotheses. Cite only supplied event IDs or document "
                                "IDs. No commands, invented CVEs, confidence changes or "
                                "decisions. Recommendations remain unverified and require human"
                                " review.",
                            ),
                            ModelMessage(
                                role="user",
                                content=json.dumps(context),
                            ),
                        ]
                    ):
                        raw += chunk
                        if len(raw) > 4000:
                            raise ValueError("bounded output")
                proposed = bounded_json(raw.encode(), 4000)
                citations = {e["id"] for e in facts["finding"]["details"]["evidence"]} | {
                    d["document_id"] for d in docs
                }
                hypotheses = (
                    proposed.get("hypotheses")
                    if isinstance(proposed, dict) and set(proposed) == {"hypotheses"}
                    else None
                )
                if not isinstance(hypotheses, list) or len(hypotheses) > 3:
                    raise ValueError("invalid output")
                for hypothesis in hypotheses:
                    if (
                        not isinstance(hypothesis, dict)
                        or set(hypothesis) != {"statement", "citations"}
                        or not isinstance(hypothesis["statement"], str)
                        or not 1 <= len(hypothesis["statement"]) <= 600
                    ):
                        raise ValueError("invalid hypothesis")
                    refs = hypothesis["citations"]
                    if (
                        not isinstance(refs, list)
                        or not 1 <= len(refs) <= 5
                        or any(not isinstance(ref, str) or ref not in citations for ref in refs)
                    ):
                        raise ValueError("invented citation")
                    if "CVE-" in hypothesis["statement"] and hypothesis[
                        "statement"
                    ] not in json.dumps(context):
                        raise ValueError("invented advisory")
                await run_in_threadpool(read_evidence, request, db, auth[0].id, body)
                if not await run_in_threadpool(capacity.active, request, lease):
                    raise ValueError("revoked inference authority")
                result.update(
                    status="mock_assistance"
                    if request.app.state.settings.model_backend == "mock"
                    else "unverified_hypotheses",
                    hypotheses=scrub(hypotheses),
                    provider=request.app.state.settings.model_backend,
                    model=request.app.state.settings.model_name,
                    model_revision=request.app.state.settings.model_revision,
                )
            except Exception:
                result.update(status="abstained", provider="unavailable_or_ungrounded_output")
            finally:
                await run_in_threadpool(capacity.end, request, lease)
    await run_in_threadpool(read_evidence, request, db, auth[0].id, body)
    for guide in docs:
        current = db.scalar(
            select(Document.text).where(
                Document.id == UUID(guide["document_id"]), Document.user_id == auth[0].id
            )
        )
        if current is None or hashlib.sha256(current.encode()).hexdigest() != guide["sha256"]:
            fail(
                404,
                "guidance_access_changed",
                "Guidance access or source revision changed; review again",
            )
    lock_owner(db, auth[0].id)
    quota(db, CyberSummary, auth[0].id, 100)
    case = owned(request, db, CyberInvestigation, body.investigation_id, auth[0].id)
    row = CyberSummary(
        user_id=auth[0].id,
        sensitive=case.sensitive,
        investigation_id=case.id,
        snapshot=context,
        sha256=context_sha,
        result=result,
    )
    db.add(row)
    db.commit()
    return output(row)


def capture_decision(request: Request, status: int) -> None:
    """Runs only after the real response decision. No caller identity fields are copied."""
    settings = request.app.state.settings
    if not settings.cybersecurity_enabled:
        return
    change = getattr(request.state, "security_change", None)
    if change is not None and status in {200, 201}:
        capture_owner_configuration(request, change)
    if not settings.cybersecurity_operator_user_ids or status not in {401, 403, 422}:
        return
    route = getattr(request.scope.get("route"), "path", "")
    login = route == "/api/v1/auth/login" and status == 401
    denied = status == 403 and route.startswith("/api/v1/")
    rejected_import = status == 422 and (
        "/imports" in route or route == "/api/v1/cybersecurity/ingest"
    )
    if not (login or denied or rejected_import):
        return
    owner = UUID(settings.cybersecurity_operator_user_ids[0])
    with Session(request.app.state.engine) as db:
        if not db.scalar(text("SELECT to_regclass('cyber_sources') IS NOT NULL")):
            return
        user = db.get(User, owner)
        if user is None or user.status != "active":
            return
        lock_owner(db, owner)
        source = db.scalar(
            select(CyberSource)
            .where(CyberSource.user_id == owner, CyberSource.namespace == "onesa-application")
            .with_for_update()
        )
        if source is None:
            source = CyberSource(
                user_id=owner,
                sensitive=True,
                name="Native application decisions",
                namespace="onesa-application",
                scope="operator",
                token_hash=None,
                config={
                    "modes": ["live"],
                    "expected_interval_seconds": 86400,
                    "review": "explicit_server_operator_configuration",
                    "endpoint_refs": [],
                },
            )
            db.add(source)
            db.flush()
            config = PolicyCreate(
                review_note="Explicit operator-configured native decision capture"
            ).model_dump()
            db.add(
                CyberPolicy(
                    user_id=owner,
                    sensitive=True,
                    source_id=source.id,
                    version=1,
                    config=config,
                    sha256=sha(config),
                )
            )
            db.flush()
        reason = (
            "AUTHENTICATION_REJECTED"
            if login
            else "IMPORT_REJECTED"
            if rejected_import
            else "PRIVILEGED_CONFIG_REJECTED"
            if route.startswith("/api/v1/admin/")
            else "AUTHORIZATION_REJECTED"
        )
        event = SecurityEvent.model_validate(
            {
                "schemaVersion": "ot-security-evidence/v1",
                "producerNamespace": source.namespace,
                "sourceEventId": str(uuid4()),
                "occurredAt": now().isoformat(),
                "mode": "live",
                "eventType": "auth.authentication_failed" if login else "auth.authorization_denied",
                "assetRef": None,
                "summary": "The application rejected an authentication, authorization or "
                "input decision.",
                "quality": "good",
                "producerVersion": "onesa-native/1",
                "attributes": {
                    "service": "authentication"
                    if login
                    else "import"
                    if rejected_import
                    else "application",
                    "outcome": "denied",
                    "reasonCode": reason,
                },
            }
        )
        ingest(db, request, source, [event], "native")
        db.commit()


def capture_owner_configuration(request: Request, change: dict[str, Any]) -> None:
    """A server-set post-commit marker supplies authority, never an input payload."""
    owner = UUID(change["owner"])
    with Session(request.app.state.engine) as db:
        lock_owner(db, owner)
        source = db.scalar(
            select(CyberSource).where(
                CyberSource.user_id == owner, CyberSource.namespace == "onesa-owned-configuration"
            )
        )
        if source is None:
            source = CyberSource(
                user_id=owner,
                name="Owned configuration decisions",
                namespace="onesa-owned-configuration",
                scope="application",
                token_hash=None,
                config={
                    "modes": ["live"],
                    "expected_interval_seconds": 86400,
                    "review": "actual_committed_owner_configuration",
                    "endpoint_refs": [],
                },
            )
            db.add(source)
            db.flush()
            config = PolicyCreate(
                review_note="Actual committed owner configuration evidence"
            ).model_dump()
            db.add(
                CyberPolicy(
                    user_id=owner, source_id=source.id, version=1, config=config, sha256=sha(config)
                )
            )
            db.flush()
        event = SecurityEvent.model_validate(
            {
                "schemaVersion": "ot-security-evidence/v1",
                "producerNamespace": source.namespace,
                "sourceEventId": str(uuid4()),
                "occurredAt": now().isoformat(),
                "mode": "live",
                "eventType": "config.changed",
                "assetRef": None,
                "summary": (
                    "A reviewed owner configuration change was committed by this application."
                ),
                "quality": "good",
                "producerVersion": "onesa-native/1",
                "attributes": {
                    "configRevision": change["revision"],
                    "changedKeys": change["changed_keys"],
                },
            }
        )
        ingest(db, request, source, [event], "native")
        db.commit()
