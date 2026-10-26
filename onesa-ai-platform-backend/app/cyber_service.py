"""Transactional security evidence and versioned, bounded deterministic rules."""

import hashlib
import json
from collections.abc import Sequence
from datetime import timedelta
from typing import Any, TypeVar, cast
from uuid import UUID

from fastapi import Request
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth import authenticated, eligible
from app.cyber_models import (
    CyberAction,
    CyberAsset,
    CyberBaseline,
    CyberEvent,
    CyberFinding,
    CyberInvestigation,
    CyberMapping,
    CyberOwned,
    CyberPolicy,
    CyberReport,
    CyberResult,
    CyberSource,
)
from app.cyber_schemas import SecurityEvent, clean, utc
from app.errors import fail
from app.models import User, now

T = TypeVar("T", bound=CyberOwned)
RULE_VERSION = "onesa-security-rules/1.0"
MAX_EVENTS = 2000


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def operator(request: Request, owner: UUID) -> bool:
    return str(owner) in request.app.state.settings.cybersecurity_operator_user_ids


def visible(request: Request, cls: type[T], owner: UUID) -> Any:
    stmt = select(cls).where(cls.user_id == owner)
    return stmt if operator(request, owner) else stmt.where(cls.sensitive.is_(False))


def owned(
    request: Request,
    db: Session,
    cls: type[T],
    identifier: UUID,
    owner: UUID,
    *,
    lock: bool = False,
) -> T:
    stmt = visible(request, cls, owner).where(cls.id == identifier)
    row = db.scalar(stmt.with_for_update() if lock else stmt)
    if row is None:
        fail(404, "security_not_found", "Security resource not found")
    return cast(T, row)


def lock_owner(db: Session, owner: UUID) -> None:
    if (
        db.scalar(
            select(User.id).where(User.id == owner, User.status == "active").with_for_update()
        )
        is None
    ):
        fail(401, "unauthorized", "The account is no longer available")


def quota(db: Session, cls: type[T], owner: UUID, maximum: int) -> None:
    if (
        db.scalar(select(func.count()).select_from(cls).where(cls.user_id == owner)) or 0
    ) >= maximum:
        fail(
            409,
            "security_capacity",
            "Security storage capacity reached; export and review retention",
        )


def scrub(value: Any) -> Any:
    if isinstance(value, str):
        return clean(value)
    if isinstance(value, list):
        return [scrub(item) for item in value]
    if isinstance(value, dict):
        return {key: scrub(item) for key, item in value.items()}
    return value


def output(row: CyberOwned) -> dict[str, Any]:
    # Explicit column projection excludes all authentication hashes.
    return {
        col.name: value.isoformat()
        if hasattr(value, "isoformat")
        else str(value)
        if isinstance(value, UUID)
        else value
        for col in row.__table__.columns
        if col.name not in {"token_hash", "user_id"}
        for value in [getattr(row, col.name)]
    }


def evidence_snapshots(events: list[CyberEvent], budget: int = 12288) -> list[dict[str, Any]]:
    """Keep bounded full samples and checksum references to every immutable input."""
    result = []
    size = 2
    for event in reversed(events):
        value = output(event)
        length = len(canonical(value)) + 1
        if size + length <= budget:
            result.append(value)
            size += length
    return list(reversed(result))


def list_output(row: CyberOwned) -> dict[str, Any]:
    """Lists carry bounded metadata; full evidence has separate authorized reads."""
    value = output(row)
    if isinstance(row, CyberFinding):
        value["details"] = {
            key: row.details[key] for key in ["explanation", "priority_formula", "quality"]
        }
        value["details"].update(evidence=[], expected=None, observed=None, preview=True)
    elif isinstance(row, CyberInvestigation):
        value.pop("snapshot")
    elif isinstance(row, CyberAsset):
        value["details"] = {"twin": row.details.get("twin"), "review": "owner_self_review"}
    elif isinstance(row, CyberSource):
        value["config"] = {key: row.config[key] for key in ["modes", "expected_interval_seconds"]}
    elif isinstance(row, CyberMapping):
        value["review"] = {"review": "owner_self_review", "sha256": sha(row.review)}
    elif isinstance(row, CyberPolicy):
        value["config"] = {key: item for key, item in row.config.items() if key != "review_note"}
    elif isinstance(row, CyberBaseline):
        value["config"] = {
            "sha256": sha(row.config),
            "relevant_key_count": len(row.config["relevant_keys"]),
            "allowed_identity_count": len(row.config["allowed_identities"]),
            "input_reference_count": len(row.config["input_refs"]),
        }
    return value


CONTROL_TYPES = {
    "authentication_decisions": {"auth.authentication_failed"},
    "authorization_decisions": {"auth.authorization_denied"},
    "certificate_metadata": {"tls.certificate_observed"},
    "reviewed_configuration": {"config.changed", "config.drift_observed"},
    "identity_allowlist": {"identity.unrecognized"},
    "collector_health": {"collector.health"},
    "software_inventory": {"software.inventory_observed"},
    "reported_integrity": {"integrity.change_observed"},
}


def control_coverage(
    db: Session,
    request: Request,
    owner: UUID,
    assets: Sequence[CyberAsset],
    sources: Sequence[CyberSource],
    baselines: Sequence[CyberBaseline],
    mode: str,
) -> dict[str, Any]:
    rows = db.execute(
        select(
            CyberEvent.asset_id,
            CyberEvent.source_id,
            CyberEvent.event_type,
            CyberEvent.expires_at,
            CyberEvent.created_at,
            CyberEvent.wire["quality"].astext.label("quality"),
        )
        .where(
            CyberEvent.user_id == owner, CyberEvent.mode == mode, CyberEvent.asset_id.is_not(None)
        )
        .limit(MAX_EVENTS)
    ).all()
    catalog = {
        source.id: source for source in sources if not source.sensitive or operator(request, owner)
    }
    config_scopes = {
        baseline.source_id for baseline in baselines if baseline.config["relevant_keys"]
    }
    identity_scopes = {
        baseline.source_id for baseline in baselines if baseline.config["input_refs"]
    }
    grouped: dict[UUID, list[Any]] = {}
    for row in rows:
        if row.source_id in catalog:
            grouped.setdefault(row.asset_id, []).append(row)
    counts = {"assessed": 0, "unknown": 0, "stale": 0}
    by_asset = []
    instant = now()
    for asset in assets:
        controls = []
        for name, types in CONTROL_TYPES.items():
            observations = [
                row
                for row in grouped.get(asset.id, [])
                if row.event_type in types
                and row.quality == "good"
                and (name != "reviewed_configuration" or row.source_id in config_scopes)
                and (name != "identity_allowlist" or row.source_id in identity_scopes)
            ]
            fresh = [
                row
                for row in observations
                if row.expires_at > instant
                and catalog[row.source_id].revoked_at is None
                and row.created_at
                + timedelta(seconds=catalog[row.source_id].config["expected_interval_seconds"] * 2)
                > instant
            ]
            state = "assessed" if fresh else "stale" if observations else "unknown"
            counts[state] += 1
            controls.append({"control": name, "state": state, "eligible_observations": len(fresh)})
        by_asset.append({"asset_id": str(asset.id), "controls": controls})
    return {
        **counts,
        "denominator": len(assets) * len(CONTROL_TYPES),
        "by_asset": by_asset,
        "definition": (
            "Eight evidence families per reviewed asset. Assessed means unexpired "
            "good-quality evidence, current receiver delivery and required reviewed "
            "scope; it does not mean the control is secure or compliant."
        ),
        "mode": mode,
        "evaluated_at": instant.isoformat(),
    }


def audit(
    db: Session,
    owner: UUID,
    kind: str,
    details: dict[str, Any],
    investigation: CyberInvestigation | None = None,
    sensitive: bool = False,
) -> None:
    quota(db, CyberAction, owner, 1000)
    if len(canonical(details)) > 65536:
        fail(
            413,
            "security_snapshot_bound",
            "Decision snapshot exceeds 64 KiB; select fewer supporting observations",
        )
    db.add(
        CyberAction(
            user_id=owner,
            kind=kind,
            details=scrub(details),
            investigation_id=investigation.id if investigation else None,
            sensitive=investigation.sensitive if investigation else sensitive,
        )
    )


def ingest(
    db: Session, request: Request, source: CyberSource, events: list[SecurityEvent], transport: str
) -> dict[str, Any]:
    """Owner then source locks serialize quotas, revoke, mapping and concurrent retries."""
    lock_owner(db, source.user_id)
    # Recheck authority after waiting; callers flush new reports/sources first.
    db.expire_all()
    locked_source = db.scalar(
        select(CyberSource)
        .where(CyberSource.id == source.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked_source is None or locked_source.revoked_at is not None:
        fail(401, "source_revoked", "Source credential is unavailable")
    source = locked_source
    if transport in {"session_import", "report_import", "explicit_demonstration"}:
        identity = authenticated(request, db, request.cookies.get("onesa_session"))
        if identity[0].id != source.user_id:
            fail(403, "source_access_denied", "Source owner authority is no longer available")
    user = db.get(User, source.user_id)
    if user is None or user.status != "active":
        fail(401, "source_revoked", "Source credential is unavailable")
    eligible(request, db, user)
    if source.sensitive and not operator(request, source.user_id):
        fail(403, "operator_required", "Configured security operator access is required")
    inserted: list[CyberEvent] = []
    duplicate = 0
    count = (
        db.scalar(
            select(func.count()).select_from(CyberEvent).where(CyberEvent.user_id == source.user_id)
        )
        or 0
    )
    for event in events:
        if event.producerNamespace != source.namespace or event.mode not in source.config["modes"]:
            fail(422, "source_scope", "Event producer or mode differs from the configured source")
        wire = event.wire()
        content_hash = sha(wire)
        existing = db.scalar(
            select(CyberEvent).where(
                CyberEvent.source_id == source.id, CyberEvent.source_event_id == event.sourceEventId
            )
        )
        if existing:
            if existing.sha256 != content_hash:
                fail(409, "event_conflict", "An immutable source event ID has different content")
            duplicate += 1
            continue
        occurred = utc(event.occurredAt)
        if occurred > now() + timedelta(minutes=5) or occurred < now() - timedelta(days=90):
            fail(
                422,
                "event_time_bounds",
                "Evidence must be within 90 days and 5 minutes of clock skew",
            )
        if count + len(inserted) >= MAX_EVENTS:
            fail(429, "security_backpressure", "Security evidence capacity reached; pause delivery")
        mapping = None
        if event.assetRef is not None:
            ref = event.assetRef
            mapping = db.scalar(
                select(CyberMapping).where(
                    CyberMapping.source_id == source.id,
                    CyberMapping.external_namespace == ref.namespace,
                    CyberMapping.external_asset == ref.assetId,
                    CyberMapping.external_component == (ref.componentId or ""),
                )
            )
            if mapping is None:
                fail(
                    422,
                    "mapping_review_required",
                    "Review the external asset mapping before ingestion",
                )
        if event.eventType == "tls.certificate_observed" and event.attributes[
            "endpointRef"
        ] not in source.config.get("endpoint_refs", []):
            fail(
                422, "endpoint_review_required", "Certificate endpoint reference is not configured"
            )
        if event.eventType == "software.inventory_observed":
            try:
                report_id = UUID(event.attributes["inventoryRef"])
            except ValueError:
                fail(
                    422,
                    "inventory_review_required",
                    "Reference a separately validated owned inventory",
                )
            report = db.scalar(
                select(CyberReport).where(
                    CyberReport.id == report_id,
                    CyberReport.user_id == source.user_id,
                    CyberReport.asset_id == (mapping.asset_id if mapping else None),
                )
            )
            if (
                report is None
                or report.sha256 != event.attributes["sha256"]
                or report.details["source_id"] != str(source.id)
                or report.details["mode"] != event.mode
                or report.details["run_id"] != (event.scenarioRunId or event.replayRunId or "")
            ):
                fail(
                    422,
                    "inventory_review_required",
                    "Inventory reference, source, asset and hash must match",
                )
        # All attributes and references already passed typed opaque/hash/date validators.
        # Only the free-text summary is normalized; an opaque URI is never fetched.
        sanitized = dict(wire)
        # Identifiers/dates/hashes cannot silently change during redaction.
        sanitized["summary"] = clean(event.summary)
        if any(sanitized[key] != wire[key] for key in wire if key not in {"summary", "attributes"}):
            fail(422, "sensitive_identifier", "Remove sensitive values from evidence identifiers")
        checked = SecurityEvent.model_validate(sanitized)
        row = CyberEvent(
            user_id=source.user_id,
            sensitive=source.sensitive,
            source_id=source.id,
            source_event_id=event.sourceEventId,
            asset_id=mapping.asset_id if mapping else None,
            mapping_id=mapping.id if mapping else None,
            event_type=event.eventType,
            mode=event.mode,
            run_id=event.scenarioRunId or event.replayRunId or "",
            occurred_at=occurred,
            expires_at=occurred + timedelta(days=30),
            sha256=content_hash,
            wire=checked.wire(),
            provenance={
                "basis": "application_decision" if transport == "native" else "unverified_import",
                "transport": transport,
                "source_version": event.producerVersion,
                "mapping_id": str(mapping.id) if mapping else None,
                "received_sha256": content_hash,
                "stored_sha256": sha(sanitized),
                "clock_skew_seconds": max(0, int((occurred - now()).total_seconds())),
                "late": occurred < now() - timedelta(minutes=5),
            },
        )
        db.add(row)
        db.flush()
        inserted.append(row)
    if inserted:
        source.last_seen_at = now()
        for row in inserted:
            evaluate(db, source, row)
    return {
        "inserted": len(inserted),
        "duplicates": duplicate,
        "event_ids": [str(row.id) for row in inserted],
    }


def find(
    db: Session,
    source: CyberSource,
    rule: str,
    mode: str,
    run_id: str,
    asset_id: UUID | None,
    severity: str,
    evidence: list[CyberEvent],
    explanation: str,
    expected: Any,
    observed: Any,
    policy: CyberPolicy | None,
    extra: dict[str, Any] | None = None,
) -> None:
    version = policy.sha256 if policy else RULE_VERSION
    key = sha(
        [
            str(source.id),
            str(asset_id),
            rule,
            version,
            mode,
            run_id,
            (extra or {}).get("control_scope"),
        ]
    )
    current = db.scalar(
        select(CyberFinding).where(CyberFinding.dedupe_key == key).with_for_update()
    )
    instants = [event.occurred_at for event in evidence] or [now()]
    asset = db.get(CyberAsset, asset_id) if asset_id else None
    weight = {"info": 10, "low": 20, "medium": 40, "high": 60}[severity]
    priority = min(
        100, weight + ({"high": 20, "medium": 10}.get(asset.criticality, 0) if asset else 0)
    )
    snapshots = evidence_snapshots(evidence[:100])
    details = {
        "explanation": explanation,
        "observed": observed,
        "expected": expected,
        "evidence": snapshots,
        "evidence_references": [
            {
                "id": str(event.id),
                "sha256": event.sha256,
                "stored_sha256": event.provenance["stored_sha256"],
                "occurred_at": event.occurred_at.isoformat(),
            }
            for event in evidence[:100]
        ],
        "full_samples": len(snapshots),
        "referenced_events": len(evidence[:100]),
        "policy_id": str(policy.id) if policy else None,
        "priority_formula": "severity base (10/20/40/60) + reviewed criticality (0/10/20), cap 100",
        "quality": sorted({event.wire["quality"] for event in evidence}),
        "scope": "configured source and reviewed mapping only",
        **(extra or {}),
    }
    if len(canonical(details)) > 49152:
        fail(
            413,
            "finding_snapshot_bound",
            "Finding snapshot exceeds 48 KiB; narrow the reviewed evidence scope",
        )
    evidence_key = sha(details)
    if current is None:
        quota(db, CyberFinding, source.user_id, 300)
        current = CyberFinding(
            user_id=source.user_id,
            sensitive=source.sensitive,
            source_id=source.id,
            asset_id=asset_id,
            dedupe_key=key,
            rule=rule,
            rule_version=RULE_VERSION,
            mode=mode,
            run_id=run_id,
            severity=severity,
            confidence="observed"
            if evidence and all(e.provenance["basis"] == "application_decision" for e in evidence)
            else "unverified",
            priority=priority,
            first_seen=min(instants),
            last_seen=max(instants),
            details=details,
        )
        db.add(current)
        db.flush()
    if (
        db.scalar(
            select(CyberResult.id).where(
                CyberResult.finding_id == current.id, CyberResult.evidence_key == evidence_key
            )
        )
        is not None
    ):
        return
    quota(db, CyberResult, source.user_id, 600)
    if current.details != details:
        current.occurrences += 1
        current.first_seen = min(current.first_seen, min(instants))
        current.last_seen = max(current.last_seen, max(instants))
        current.priority = max(current.priority, priority)
        current.details = details
    snapshot = {"finding": output(current), "rule_version": RULE_VERSION}
    db.add(
        CyberResult(
            user_id=source.user_id,
            sensitive=source.sensitive,
            finding_id=current.id,
            evidence_key=evidence_key,
            snapshot=snapshot,
            sha256=sha(snapshot),
        )
    )


def evaluate(db: Session, source: CyberSource, event: CyberEvent) -> None:
    # Expired or bad-quality evidence remains inspectable, never silently "good".
    if event.expires_at < now() or event.wire["quality"] == "bad":
        return
    policy = db.scalar(
        select(CyberPolicy)
        .where(CyberPolicy.source_id == source.id)
        .order_by(CyberPolicy.version.desc())
        .limit(1)
    )
    if policy is None:
        return
    config, attrs = policy.config, event.wire["attributes"]
    baseline = db.scalar(
        select(CyberBaseline)
        .where(CyberBaseline.source_id == source.id)
        .order_by(CyberBaseline.created_at.desc(), CyberBaseline.id.desc())
        .limit(1)
    )

    def emit(
        rule: str,
        severity: str,
        explanation: str,
        expected: Any,
        observed: Any,
        evidence: list[CyberEvent] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        scoped = {
            "control_scope": attrs.get("service")
            or attrs.get("endpointRef")
            or attrs.get("inputRef")
        }
        scoped.update(extra or {})
        find(
            db,
            source,
            rule,
            event.mode,
            event.run_id,
            event.asset_id,
            severity,
            evidence or [event],
            explanation,
            expected,
            observed,
            policy,
            scoped,
        )

    if event.event_type in {"auth.authentication_failed", "auth.authorization_denied"}:
        threshold = config[
            "auth_threshold" if event.event_type.endswith("failed") else "denial_threshold"
        ]
        # Event-time window ending at the latest observed event supports late arrivals.
        latest = (
            db.scalar(
                select(func.max(CyberEvent.occurred_at)).where(
                    CyberEvent.source_id == source.id,
                    CyberEvent.event_type == event.event_type,
                    CyberEvent.mode == event.mode,
                    CyberEvent.run_id == event.run_id,
                    CyberEvent.asset_id == event.asset_id,
                    CyberEvent.wire["attributes"]["service"].astext == attrs["service"],
                )
            )
            or event.occurred_at
        )
        window_start = latest - timedelta(seconds=config["window_seconds"])
        candidates = db.scalars(
            select(CyberEvent)
            .where(
                CyberEvent.source_id == source.id,
                CyberEvent.event_type == event.event_type,
                CyberEvent.mode == event.mode,
                CyberEvent.run_id == event.run_id,
                CyberEvent.asset_id == event.asset_id,
                CyberEvent.wire["attributes"]["service"].astext == attrs["service"],
                CyberEvent.occurred_at > window_start,
                CyberEvent.occurred_at <= latest,
                CyberEvent.expires_at > now(),
            )
            .order_by(CyberEvent.occurred_at, CyberEvent.id)
            .limit(101)
        ).all()
        evidence = [
            e
            for e in candidates
            if e.wire["quality"] != "bad" and e.wire["attributes"]["service"] == attrs["service"]
        ][:100]
        if len(evidence) >= threshold:
            emit(
                event.event_type,
                "medium",
                "Repeated rejected decisions in the configured event-time "
                "window; compromise is not established.",
                {
                    "threshold": threshold,
                    "window_seconds": config["window_seconds"],
                    "service": attrs["service"],
                },
                {
                    "count": len(evidence),
                    "capped_at": 100,
                    "window_start_exclusive": window_start.isoformat(),
                    "window_end": latest.isoformat(),
                },
                evidence,
            )
        if (
            event.event_type == "auth.authorization_denied"
            and attrs["reasonCode"] == "PRIVILEGED_CONFIG_REJECTED"
        ):
            emit(
                "privileged_configuration_rejected",
                "high",
                "The application rejected a privileged operation; this does not prove compromise.",
                "authorized operator",
                "rejected attempt",
            )
    elif event.event_type == "tls.certificate_observed":
        remaining = (utc(attrs["notAfter"]) - now()).total_seconds()
        if remaining <= config["certificate_warning_days"] * 86400:
            emit(
                "certificate_validity",
                "high" if remaining <= 0 else "medium",
                "Configured endpoint certificate metadata indicates expiry; "
                "imported metadata is not an active connection test.",
                {"warning_days": config["certificate_warning_days"]},
                {"notAfter": attrs["notAfter"], "expired": remaining <= 0},
            )
    elif event.event_type in {"config.changed", "config.drift_observed"} and baseline:
        relevant = set(attrs["changedKeys"]) & set(baseline.config["relevant_keys"])
        if relevant and attrs["configRevision"] != baseline.revision:
            emit(
                "reviewed_configuration_drift",
                "medium",
                "Reported security-relevant keys differ from the accepted "
                "revision; secret values are not collected.",
                baseline.revision,
                {"revision": attrs["configRevision"], "keys": sorted(relevant)},
                extra={"baseline_id": str(baseline.id)},
            )
    elif event.event_type == "identity.unrecognized" and baseline:
        if (
            attrs["inputRef"] in baseline.config["input_refs"]
            and attrs["observedIdentityRef"] not in baseline.config["allowed_identities"]
        ):
            emit(
                "unrecognized_identity",
                "medium",
                "Observed identity is outside a reviewed allowlist for this "
                "input; ownership and device authenticity remain unproven.",
                {"baseline_id": str(baseline.id)},
                {"observedIdentityRef": attrs["observedIdentityRef"]},
            )
    elif event.event_type == "collector.health" and attrs["state"] in {"offline", "degraded"}:
        emit(
            "collector_coverage",
            "low",
            "The collector reports reduced monitoring coverage; this is not evidence of an attack.",
            "online",
            attrs["state"],
        )
    elif (
        event.event_type == "integrity.change_observed"
        and attrs["previousSha256"] != attrs["currentSha256"]
    ):
        emit(
            "reported_integrity_change",
            "medium",
            "An integrity change was reported; the evidence-basis label is "
            "not independent signed or hardware attestation.",
            attrs["previousSha256"],
            attrs["currentSha256"],
            extra={"evidence_basis": attrs["evidenceBasis"], "attestation": "not_established"},
        )


def snapshot(db: Session, request: Request, investigation: CyberInvestigation) -> dict[str, Any]:
    finding = owned(request, db, CyberFinding, investigation.finding_id, investigation.user_id)
    source = owned(request, db, CyberSource, finding.source_id, investigation.user_id)
    return {
        "investigation_id": str(investigation.id),
        "original_decision_context": investigation.snapshot,
        "original_sha256": investigation.sha256,
        "finding": output(finding),
        "source": output(source),
        "asset": output(owned(request, db, CyberAsset, finding.asset_id, investigation.user_id))
        if finding.asset_id
        else None,
        **action_history(db, request, investigation),
        "missing": ["Device attestation", "Verified exploitability", "Independent review"],
        "checklist": [
            "Review source, mode and freshness",
            "Validate asset mapping and affected scope",
            "Compare against approved baseline",
            "Record a human decision with cited evidence",
        ],
        "cause": "not_established",
    }


def action_history(
    db: Session, request: Request, investigation: CyberInvestigation, before: UUID | None = None
) -> dict[str, Any]:
    stmt = visible(request, CyberAction, investigation.user_id).where(
        CyberAction.investigation_id == investigation.id
    )
    if before:
        cursor = owned(request, db, CyberAction, before, investigation.user_id)
        if cursor.investigation_id != investigation.id:
            fail(404, "security_not_found", "Decision cursor not found")
        stmt = stmt.where(text("(cyber_actions.created_at,cyber_actions.id)<(:at,:id)"))
        stmt = stmt.params(at=cursor.created_at, id=cursor.id)
    rows = list(
        db.scalars(stmt.order_by(CyberAction.created_at.desc(), CyberAction.id.desc()).limit(41))
    )
    items = []
    for row in reversed(rows[:40]):
        value = output(row)
        value["details"] = {
            key: item
            for key, item in row.details.items()
            if key not in {"finding_at_decision", "evidence"}
        }
        value["details"]["decision_snapshot_sha256"] = sha(row.details)
        items.append(value)
    return {"history": items, "history_next": str(rows[39].id) if len(rows) > 40 else None}
