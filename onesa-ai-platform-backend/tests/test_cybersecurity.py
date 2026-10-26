"""Real PostgreSQL, actual auth decisions and native independent security journeys."""

import copy
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cyber_models import CyberEvent, CyberSource
from app.cyber_schemas import SecurityEvent, parse_batch
from app.main import create_app
from app.models import now
from tests.conftest import signup

BASE = "/api/v1/cybersecurity"


@pytest.fixture
def cyber(api):
    api.app.state.settings.cybersecurity_enabled = True
    signup(api)
    return api


def source(api, namespace="local-collector", modes=None):
    response = api.post(
        BASE + "/sources",
        json={
            "name": "Local evidence",
            "namespace": namespace,
            "modes": modes or ["live", "simulated", "replay"],
            "endpoint_refs": ["configured-api"],
            "expected_interval_seconds": 60,
            "review_note": "Owner reviewed local collector scope",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def asset(api):
    response = api.post(
        BASE + "/assets",
        json={
            "name": "Reviewed gateway",
            "identity": "gateway-01",
            "zone": "OT maintenance",
            "criticality": "high",
            "review_note": "Physical inventory reviewed by owner",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def mapping(api, src, target):
    response = api.post(
        BASE + f"/sources/{src['id']}/mappings",
        json={
            "asset_id": target["id"],
            "namespace": "maintenance",
            "external_asset": "gateway-01",
            "review_note": "Verified local inventory association",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def event(index=0, *, kind="auth.authentication_failed", mode="live", mapped=False, **changes):
    attributes = {
        "auth.authentication_failed": {
            "service": "application",
            "outcome": "denied",
            "reasonCode": "REJECTED",
        },
        "auth.authorization_denied": {
            "service": "application",
            "outcome": "denied",
            "reasonCode": "AUTHORIZATION_REJECTED",
        },
        "tls.certificate_observed": {
            "endpointRef": "configured-api",
            "notBefore": (now() - timedelta(days=10)).isoformat(),
            "notAfter": (now() + timedelta(days=2)).isoformat(),
            "fingerprintSha256": "a" * 64,
        },
        "config.changed": {
            "configRevision": "new",
            "baselineRevision": "accepted",
            "changedKeys": ["access_policy"],
        },
        "config.drift_observed": {"configRevision": "new", "changedKeys": ["access_policy"]},
        "identity.unrecognized": {
            "inputRef": "reviewed-input",
            "observedIdentityRef": "unknown-device",
        },
        "collector.health": {"state": "offline", "expectedIntervalSeconds": 30},
        "software.inventory_observed": {"inventoryRef": "report-01", "sha256": "a" * 64},
        "integrity.change_observed": {
            "previousSha256": "a" * 64,
            "currentSha256": "b" * 64,
            "evidenceBasis": "self_reported",
        },
    }[kind]
    return {
        "schemaVersion": "ot-security-evidence/v1",
        "producerNamespace": "local-collector",
        "sourceEventId": f"event-{index}",
        "occurredAt": now().isoformat(),
        "mode": mode,
        **(
            {"scenarioRunId": "isolated-demo"}
            if mode == "simulated"
            else {"replayRunId": "isolated-replay"}
            if mode == "replay"
            else {}
        ),
        "eventType": kind,
        "assetRef": {"namespace": "maintenance", "assetId": "gateway-01", "componentId": None}
        if mapped
        else None,
        "summary": "Explicitly supplied security observation",
        "quality": "good",
        "producerVersion": "1.0",
        "attributes": attributes,
        **changes,
    }


def ingest(api, src, events):
    return api.post(BASE + f"/sources/{src['id']}/imports", json={"events": events})


def state(api, mode="live"):
    response = api.get(BASE + "/workspace", params={"mode": mode})
    assert response.status_code == 200, response.text
    value = response.json()
    value["findings"] = [
        api.get(BASE + f"/findings/{item['id']}").json()["finding"] for item in value["findings"]
    ]
    return value


def finding(api, src, mapped=False):
    response = ingest(api, src, [event(i, mapped=mapped) for i in range(5)])
    assert response.status_code == 200, response.text
    return state(api)["findings"][0]


def investigation(api, value):
    response = api.post(
        BASE + "/investigations",
        json={"finding_id": value["id"], "title": "Review repeated rejected access"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_disabled_module_does_not_require_twins_or_provider(api):
    signup(api)
    assert api.get(BASE + "/readiness").status_code == 404
    api.app.state.settings.cybersecurity_enabled = True
    response = api.get(BASE + "/readiness")
    assert response.status_code == 200 and response.json()["provider_required"] is False
    assert api.get(BASE + "/workspace").json()["counts"]["findings"] == 0
    assert api.get("/api/v1/twins/readiness").status_code == 404
    assert api.get("/api/v1/conversations").status_code == 200


def test_real_import_finding_asset_case_decision_reload_and_snapshot(cyber):
    src, target = source(cyber), asset(cyber)
    mapping(cyber, src, target)
    value = finding(cyber, src, mapped=True)
    assert value["asset_id"] == target["id"] and value["confidence"] == "unverified"
    assert value["priority"] == 60
    case = investigation(cyber, value)
    decision = cyber.post(
        BASE + f"/investigations/{case['id']}/decisions",
        json={
            "revision": 1,
            "action": "acknowledge",
            "note": "Reviewed the supplied access observations",
        },
    )
    assert decision.status_code == 200
    saved = cyber.get(BASE + f"/investigations/{case['id']}").json()
    assert saved["investigation"]["status"] == "acknowledged"
    original = saved["investigation"]["snapshot"]
    assert len(original["finding"]["details"]["evidence"]) == 5
    assert ingest(cyber, src, [event(99, mapped=True)]).status_code == 200
    reloaded = cyber.get(BASE + f"/investigations/{case['id']}").json()
    assert reloaded["investigation"]["snapshot"] == original
    assert len(reloaded["evidence"]["history"]) == 2
    assert len(cyber.get(BASE + f"/findings/{value['id']}").json()["results"]) == 2
    assert cyber.get(BASE + f"/assets/{target['id']}").json()["findings"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("schemaVersion", "v0"),
        ("producerNamespace", " "),
        ("sourceEventId", ""),
        ("occurredAt", "2026-02-30T12:00:00Z"),
        ("occurredAt", "2026-10-26T12:00:00+02:00"),
        ("occurredAt", 123),
        ("mode", "LIVE"),
        ("quality", True),
        ("sequence", True),
        ("sequence", "1"),
        ("sequence", 9007199254740992),
        ("producerVersion", ""),
        ("eventType", "arbitrary"),
        ("owner_id", "someone"),
        ("sourceId", "fake"),
        ("ingestedAt", "fake"),
        ("summary", "x" * 513),
        (
            "assetRef",
            {"namespace": "m", "assetId": "a", "componentId": None, "localAssetId": "fake"},
        ),
    ],
)
def test_strict_wire_profile(field, value):
    payload = event()
    payload[field] = value
    with pytest.raises(ValueError):
        SecurityEvent.model_validate(payload)


@pytest.mark.parametrize(
    "kind",
    [
        "auth.authentication_failed",
        "auth.authorization_denied",
        "tls.certificate_observed",
        "config.changed",
        "config.drift_observed",
        "identity.unrecognized",
        "collector.health",
        "software.inventory_observed",
        "integrity.change_observed",
    ],
)
def test_all_profiles_reject_arbitrary_attribute_blobs(kind):
    payload = event(kind=kind)
    assert SecurityEvent.model_validate(payload).eventType == kind
    payload["attributes"]["secretConfiguration"] = "unwanted"
    with pytest.raises(ValueError):
        SecurityEvent.model_validate(payload)


@pytest.mark.parametrize("mode", ["simulated", "replay"])
def test_modes_require_separate_nonblank_run_id(mode):
    payload = event(mode=mode)
    assert SecurityEvent.model_validate(payload).mode == mode
    payload.pop("scenarioRunId" if mode == "simulated" else "replayRunId")
    with pytest.raises(ValueError):
        SecurityEvent.model_validate(payload)


def test_parser_limits_duplicate_keys_nonfinite_depth_and_ndjson(cyber):
    for raw in [
        b'{"events":[],"events":[]}',
        b'{"events":[NaN]}',
        b"[" * 13 + b"]" * 13,
        b'{"events":' + b" " * 1048576 + b"[]}",
    ]:
        with pytest.raises(ValueError):
            parse_batch(raw)
    assert len(parse_batch(json.dumps(event()).encode() + b"\n", True)) == 1
    src = source(cyber)
    response = cyber.post(
        BASE + f"/sources/{src['id']}/imports",
        content=b" " * 1048577,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert ingest(cyber, src, [event(i) for i in range(101)]).status_code == 422
    repeated = event()
    result = ingest(cyber, src, [repeated] * 100).json()
    assert result["inserted"] == 1 and result["duplicates"] == 99


def test_source_mapping_authority_idempotency_conflict_atomic_batch_and_revocation(cyber):
    src = source(cyber)
    payload = event(1)
    first = ingest(cyber, src, [payload])
    assert first.status_code == 200
    assert ingest(cyber, src, [payload]).json()["duplicates"] == 1
    changed = {**payload, "summary": "Different immutable content"}
    assert ingest(cyber, src, [changed]).status_code == 409
    assert (
        ingest(cyber, src, [event(2), event(3, producerNamespace="other-source")]).status_code
        == 422
    )
    assert len(state(cyber)["events"]) == 1
    assert ingest(cyber, src, [event(4, mapped=True)]).status_code == 422
    token = src["ingestion_token"]
    result = cyber.post(
        BASE + "/ingest", json={"events": [event(5)]}, headers={"Authorization": "Bearer " + token}
    )
    assert result.status_code == 200
    assert token not in cyber.get(BASE + "/workspace").text
    assert (
        cyber.get(
            BASE + "/workspace",
            headers={"Authorization": "Bearer " + token},
            cookies={"onesa_session": "invalid"},
        ).status_code
        == 401
    )
    assert cyber.post(BASE + f"/sources/{src['id']}/revoke").status_code == 200
    assert (
        cyber.post(
            BASE + "/ingest",
            json={"events": [event(6)]},
            headers={"Authorization": "Bearer " + token},
        ).status_code
        == 401
    )


def test_concurrent_scoped_delivery_has_one_insert_and_explicit_conflicts(cyber):
    src = source(cyber)
    payload = event()

    def deliver(value):
        with TestClient(cyber.app) as client:
            return client.post(
                BASE + "/ingest",
                json={"events": [value]},
                headers={"Authorization": "Bearer " + src["ingestion_token"]},
            )

    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(deliver, [payload] * 4))
    assert [r.status_code for r in responses] == [200] * 4
    assert sum(r.json()["inserted"] for r in responses) == 1
    assert sum(r.json()["duplicates"] for r in responses) == 3
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(deliver, [{**payload, "summary": "conflict"}, payload]))
    assert sorted(r.status_code for r in responses) == [200, 409]


def test_mode_run_window_late_quality_and_recurrence(cyber):
    src = source(cyber)
    instant = now()
    values = [
        event(i, occurredAt=(instant - timedelta(seconds=301 if i == 0 else i)).isoformat())
        for i in range(5)
    ]
    assert ingest(cyber, src, values).status_code == 200
    assert state(cyber)["findings"] == []
    assert ingest(cyber, src, [event(10, occurredAt=instant.isoformat())]).status_code == 200
    value = state(cyber)["findings"][0]
    assert value["details"]["observed"]["count"] == 5
    assert ingest(cyber, src, [event(11, quality="bad")]).status_code == 200
    assert state(cyber)["findings"][0]["occurrences"] == value["occurrences"]
    assert (
        ingest(cyber, src, [event(20 + i, mode="simulated") for i in range(5)]).status_code == 200
    )
    assert len(state(cyber, "simulated")["findings"]) == 1
    assert len(state(cyber)["findings"]) == 1
    assert (
        ingest(cyber, src, [event(30, mode="simulated", scenarioRunId="another-run")]).status_code
        == 200
    )
    assert len(state(cyber, "simulated")["findings"]) == 1
    assert (
        ingest(
            cyber, src, [event(40, occurredAt=(instant + timedelta(minutes=6)).isoformat())]
        ).status_code
        == 422
    )


def test_baseline_detections_certificate_health_integrity_and_unknowns(cyber):
    src = source(cyber)
    assert (
        ingest(
            cyber, src, [event(0, kind="config.changed"), event(1, kind="identity.unrecognized")]
        ).status_code
        == 200
    )
    assert state(cyber)["findings"] == []
    response = cyber.post(
        BASE + f"/sources/{src['id']}/baselines",
        json={
            "revision": "accepted",
            "relevant_keys": ["access_policy"],
            "input_refs": ["reviewed-input"],
            "allowed_identities": ["accepted-device"],
            "review_note": "Reviewed authoritative baseline and device allowlist",
        },
    )
    assert response.status_code == 201, response.text
    kinds = [
        "config.drift_observed",
        "identity.unrecognized",
        "tls.certificate_observed",
        "collector.health",
        "integrity.change_observed",
    ]
    assert (
        ingest(cyber, src, [event(10 + i, kind=kind) for i, kind in enumerate(kinds)]).status_code
        == 200
    )
    rules = {f["rule"] for f in state(cyber)["findings"]}
    assert rules == {
        "reviewed_configuration_drift",
        "unrecognized_identity",
        "certificate_validity",
        "collector_coverage",
        "reported_integrity_change",
    }
    bad = event(90, kind="tls.certificate_observed")
    bad["attributes"]["endpointRef"] = "unconfigured-url"
    assert ingest(cyber, src, [bad]).status_code == 422


def test_lifecycle_revision_resolution_expiring_acceptance_reopen(cyber):
    src = source(cyber)
    value = finding(cyber, src)
    case = investigation(cyber, value)
    path = BASE + f"/investigations/{case['id']}/decisions"
    body = {
        "revision": 1,
        "action": "resolve",
        "note": "Reviewed observations and remediation evidence",
    }
    assert cyber.post(path, json=body).status_code == 422
    body.update(action="accept_risk", acceptance_until=(now() + timedelta(days=1)).isoformat())
    assert cyber.post(path, json=body).json()["status"] == "accepted_risk"
    assert cyber.post(path, json=body).status_code == 409
    body.update(revision=2, action="reopen")
    assert cyber.post(path, json=body).json()["status"] == "open"
    body.update(revision=3, action="resolve", evidence_ids=[value["details"]["evidence"][0]["id"]])
    assert cyber.post(path, json=body).json()["status"] == "resolved"
    assert state(cyber)["findings"]  # Closing an incident does not erase the observed condition.


def test_cross_account_list_aggregate_detail_export_tool_and_mapping_isolation(cyber):
    src, target = source(cyber), asset(cyber)
    mapping(cyber, src, target)
    value = finding(cyber, src, True)
    case = investigation(cyber, value)
    cyber.cookies.clear()
    signup(cyber, "other@example.com")
    assert state(cyber)["events"] == state(cyber)["findings"] == state(cyber)["assets"] == []
    for path in [
        f"/assets/{target['id']}",
        f"/findings/{value['id']}",
        f"/investigations/{case['id']}",
        f"/export?source_id={src['id']}",
    ]:
        assert cyber.get(BASE + path).status_code == 404
    assert (
        cyber.post(
            BASE + "/tools/evidence",
            json={"investigation_id": case["id"], "expected_sha256": case["sha256"]},
        ).status_code
        == 404
    )
    assert (
        cyber.post(
            BASE + f"/sources/{src['id']}/imports", json={"events": [event(100)]}
        ).status_code
        == 404
    )
    own_source = source(cyber)
    assert (
        cyber.post(
            BASE + f"/sources/{own_source['id']}/mappings",
            json={
                "asset_id": target["id"],
                "namespace": "mine",
                "external_asset": "mine",
                "review_note": "Cannot map another account's asset",
            },
        ).status_code
        == 404
    )


def test_real_failed_login_and_privileged_denial_generate_operator_only_evidence(cyber):
    owner = cyber.get("/api/v1/auth/me").json()["id"]
    cyber.app.state.settings.cybersecurity_operator_user_ids = [owner]
    for _ in range(5):
        assert (
            cyber.post(
                "/api/v1/auth/login",
                json={"email": "unknown@example.com", "password": "a-wrong-password"},
            ).status_code
            == 401
        )
    result = state(cyber)
    assert len(result["events"]) == 5 and result["findings"][0]["confidence"] == "observed"
    assert "unknown@example.com" not in json.dumps(result)
    for _ in range(3):
        assert (
            cyber.post(
                "/api/v1/admin/invitations",
                json={
                    "email": "someone@example.com",
                    "access_days": 5,
                    "current_password": "correct-horse-123!",
                },
            ).status_code
            == 403
        )
    assert "privileged_configuration_rejected" in {f["rule"] for f in state(cyber)["findings"]}
    cyber.app.state.settings.cybersecurity_operator_user_ids = []
    assert state(cyber)["events"] == state(cyber)["findings"] == state(cyber)["sources"] == []


def test_private_exports_and_account_deletion_preserve_disabled_feature_privacy(cyber):
    src = source(cyber)
    value = finding(cyber, src)
    investigation(cyber, value)
    assert src["ingestion_token"] not in cyber.get(BASE + "/export").text
    assert "token_hash" not in cyber.get(BASE + "/export").text
    exported = cyber.get(BASE + "/export?format=ndjson")
    assert len(parse_batch(exported.content, True)) == 5
    cyber.app.state.settings.cybersecurity_enabled = False
    exported = cyber.post("/api/v1/account/export", json={"current_password": "correct-horse-123!"})
    assert exported.status_code == 200, exported.text
    assert len(exported.json()["cybersecurity"]["cyber_events"]) == 5
    assert src["ingestion_token"] not in exported.text and "token_hash" not in exported.text
    assert (
        cyber.post(
            "/api/v1/account/delete",
            json={"current_password": "correct-horse-123!", "confirmation": "DELETE MY ACCOUNT"},
        ).status_code
        == 204
    )
    with Session(cyber.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(CyberEvent)) == 0


def test_hostile_text_is_inert_redacted_and_never_instruction_authority(cyber):
    src = source(cyber)
    payload = event(
        summary="<script>attack()</script> password=do-not-store Bearer private-token https://host.invalid/?token=hidden"
    )
    assert ingest(cyber, src, [payload]).status_code == 200
    response = cyber.get(BASE + "/workspace")
    assert (
        "do-not-store" not in response.text
        and "private-token" not in response.text
        and "token=hidden" not in response.text
    )
    assert response.json()["events"][0]["wire"]["summary"].startswith(
        "<script>"
    )  # UI renders text, never HTML.


def report_fixture():
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "metadata": {
            "timestamp": now().isoformat(),
            "tools": {
                "components": [
                    {"type": "application", "name": "Local reviewed scanner", "version": "1.0"}
                ]
            },
        },
        "components": [
            {"type": "library", "bom-ref": "pkg-01", "name": "synthetic-package", "version": "1.0"}
        ],
        "vulnerabilities": [
            {
                "id": "SYNTHETIC-ADVISORY-01",
                "ratings": [{"severity": "high", "score": 7.5, "method": "CVSSv31"}],
                "affects": [{"ref": "pkg-01"}],
            }
        ],
    }


def test_bounded_report_real_ingestion_applicability_and_wrong_references(cyber):
    src, target = source(cyber), asset(cyber)
    mapping(cyber, src, target)
    path = BASE + f"/sources/{src['id']}/reports?asset_id={target['id']}"
    report = report_fixture()
    response = cyber.post(path, json=report)
    assert response.status_code == 201, response.text
    assert response.json()["details"]["exploitability"] == "unverified"
    assert (
        state(cyber)["findings"][0]["details"]["observed"]["components"][0]["applicability"]
        == "reported_match"
    )
    assert cyber.post(path, json=report).json()["duplicate"] is True
    malformed = copy.deepcopy(report)
    malformed["vulnerabilities"][0]["affects"][0]["ref"] = "unknown"
    assert cyber.post(path, json=malformed).status_code == 422
    malformed = copy.deepcopy(report)
    malformed["components"] *= 251
    assert cyber.post(path, json=malformed).status_code == 422


def test_typed_tool_and_deterministic_summary_without_inference(cyber):
    src = source(cyber)
    case = investigation(cyber, finding(cyber, src))
    body = {"investigation_id": case["id"], "expected_sha256": case["sha256"]}
    assert "cybersecurity_evidence_v1" in {
        t["name"] for t in cyber.get("/api/v1/agents/tools").json()["items"]
    }
    assert cyber.post(BASE + "/tools/evidence", json=body).json()["cause"] == "not_established"
    response = cyber.post(BASE + "/summaries", json={**body, "assist": False})
    assert response.status_code == 201 and response.json()["result"]["status"] == "deterministic"
    response = cyber.post(BASE + "/summaries", json={**body, "assist": True})
    assert response.json()["result"]["status"] == "abstained"
    assert (
        cyber.post(BASE + "/tools/evidence", json={**body, "expected_sha256": "a" * 64}).status_code
        == 409
    )


def test_explicit_demonstration_and_replay_never_seed_live_findings(cyber):
    assert (
        cyber.post(BASE + "/demo", json={"mode": "simulated", "run_id": "owned-demo"}).status_code
        == 404
    )
    cyber.app.state.settings.cybersecurity_demo_enabled = True
    for mode in ["simulated", "replay"]:
        response = cyber.post(BASE + "/demo", json={"mode": mode, "run_id": "owned-demo"})
        assert response.status_code == 200 and response.json()["created"] is True
        assert (
            cyber.post(BASE + "/demo", json={"mode": mode, "run_id": "owned-demo"}).json()[
                "created"
            ]
            is False
        )
        assert len(state(cyber, mode)["findings"]) == 1
    assert not state(cyber)["findings"] and not state(cyber)["events"]


def test_overdue_collector_assessment_is_coverage_and_idempotent(cyber):
    src = source(cyber)
    with Session(cyber.app.state.engine) as db:
        row = db.get(CyberSource, UUID(src["id"]))
        row.created_at = now() - timedelta(hours=2)
        db.commit()
    assert cyber.post(BASE + "/assess").status_code == 200
    value = state(cyber)["findings"][0]
    assert (
        value["rule"] == "collector_freshness" and "coverage gap" in value["details"]["explanation"]
    )
    assert cyber.post(BASE + "/assess").status_code == 200
    assert state(cyber)["findings"][0]["occurrences"] == value["occurrences"]


def test_actual_policy_commit_creates_native_scoped_configuration_evidence(cyber):
    src = source(cyber)
    body = {
        "auth_threshold": 6,
        "denial_threshold": 4,
        "window_seconds": 300,
        "certificate_warning_days": 14,
        "review_note": "Reviewed application configuration revision",
    }
    response = cyber.post(BASE + f"/sources/{src['id']}/policies", json=body)
    assert response.status_code == 201, response.text
    evidence = state(cyber)["events"]
    assert len(evidence) == 1 and evidence[0]["event_type"] == "config.changed"
    assert evidence[0]["provenance"]["basis"] == "application_decision"
    assert evidence[0]["wire"]["attributes"]["configRevision"] == response.json()["sha256"]
    native = next(
        s for s in state(cyber)["sources"] if s["namespace"] == "onesa-owned-configuration"
    )
    assert (
        ingest(cyber, native, [event(50, producerNamespace=native["namespace"])]).status_code == 403
    )


def test_capacity_backpressure_and_process_restart_keep_existing_evidence(cyber, monkeypatch):
    from app import cyber_service

    src = source(cyber)
    payload = event()
    assert ingest(cyber, src, [payload]).status_code == 200
    monkeypatch.setattr(cyber_service, "MAX_EVENTS", 1)
    assert ingest(cyber, src, [event(2)]).status_code == 429
    assert ingest(cyber, src, [payload]).json()["duplicates"] == 1
    fresh_app = create_app(cyber.app.state.settings)
    with TestClient(fresh_app) as client:
        client.cookies.update(cyber.cookies)
        response = client.get(BASE + "/workspace")
        assert response.status_code == 200 and len(response.json()["events"]) == 1


def test_mock_assistance_rejects_invented_citations_and_cannot_mutate_findings(cyber):
    src = source(cyber)
    case = investigation(cyber, finding(cyber, src))

    class Model:
        async def healthy(self):
            return True

        async def stream(self, _messages):
            yield json.dumps(
                {
                    "hypotheses": [
                        {
                            "statement": "Unverified local review hypothesis",
                            "citations": ["invented-id"],
                        }
                    ]
                }
            )

    cyber.app.state.model_client = Model()
    cyber.app.state.settings.cybersecurity_ai_enabled = True
    before = state(cyber)["findings"]
    response = cyber.post(
        BASE + "/summaries",
        json={"investigation_id": case["id"], "expected_sha256": case["sha256"], "assist": True},
    )
    assert response.status_code == 201 and response.json()["result"]["status"] == "abstained"
    assert state(cyber)["findings"] == before
    assert (
        cyber.get(BASE + f"/investigations/{case['id']}").json()["investigation"]["status"]
        == "open"
    )


def test_revocation_between_credential_lookup_and_ingestion_fails_closed(cyber, monkeypatch):
    from app import cybersecurity

    src = source(cyber)
    entered, resume = Event(), Event()
    original = cybersecurity.ingest

    def paused(*args):
        entered.set()
        assert resume.wait(3), "test coordination deadline"
        return original(*args)

    monkeypatch.setattr(cybersecurity, "ingest", paused)

    def deliver():
        with TestClient(cyber.app) as client:
            return client.post(
                BASE + "/ingest",
                json={"events": [event()]},
                headers={"Authorization": "Bearer " + src["ingestion_token"]},
            )

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(deliver)
        assert entered.wait(3)
        try:
            assert cyber.post(BASE + f"/sources/{src['id']}/revoke").status_code == 200
        finally:
            resume.set()
        assert future.result().status_code == 401
    assert state(cyber)["events"] == []


def test_rule_versions_long_history_and_saved_reports_remain_inspectable(cyber):
    src = source(cyber)
    value = finding(cyber, src)
    case = investigation(cyber, value)
    for revision in range(1, 43):
        response = cyber.post(
            BASE + f"/investigations/{case['id']}/decisions",
            json={
                "revision": revision,
                "action": "note",
                "note": f"Synthetic durable decision history note {revision}",
            },
        )
        assert response.status_code == 200
    detail = cyber.get(BASE + f"/investigations/{case['id']}").json()
    assert len(detail["evidence"]["history"]) == 40
    assert detail["evidence"]["history"][-1]["details"]["note"].endswith("42")
    older = cyber.get(
        BASE + f"/investigations/{case['id']}/actions",
        params={"before": detail["evidence"]["history_next"]},
    ).json()
    assert len(older["history"]) == 3 and older["history"][0]["kind"] == "opened"
    action_id = detail["evidence"]["history"][-1]["id"]
    assert (
        cyber.get(BASE + f"/actions/{action_id}").json()["details"]["finding_at_decision"]["id"]
        == value["id"]
    )
    report = cyber.post(
        BASE + "/summaries",
        json={"investigation_id": case["id"], "expected_sha256": case["sha256"]},
    )
    assert report.status_code == 201
    assert (
        cyber.get(BASE + f"/investigations/{case['id']}").json()["summaries"][0]["id"]
        == report.json()["id"]
    )
    policy = cyber.post(
        BASE + f"/sources/{src['id']}/policies",
        json={"auth_threshold": 2, "review_note": "New reviewed policy retains prior results"},
    )
    assert policy.status_code == 201
    assert ingest(cyber, src, [event(99)]).status_code == 200
    assert len(state(cyber)["findings"]) == 2
    assert (
        cyber.get(BASE + f"/investigations/{case['id']}").json()["investigation"]["snapshot"][
            "finding"
        ]["id"]
        == value["id"]
    )


def test_inventory_reference_cannot_fabricate_or_cross_source_a_validated_report(cyber):
    src, target = source(cyber), asset(cyber)
    mapping(cyber, src, target)
    assert (
        ingest(cyber, src, [event(kind="software.inventory_observed", mapped=True)]).status_code
        == 422
    )
    report = report_fixture()
    path = BASE + f"/sources/{src['id']}/reports?asset_id={target['id']}"
    first = cyber.post(path + "&mode=simulated&run_id=inventory-demo", json=report)
    replay = cyber.post(path + "&mode=replay&run_id=inventory-replay", json=report)
    assert first.status_code == replay.status_code == 201
    assert first.json()["id"] != replay.json()["id"]
    assert len(state(cyber, "simulated")["events"]) == len(state(cyber, "replay")["events"]) == 1
    bad = event(99, kind="software.inventory_observed", mapped=True)
    bad["attributes"] = {"inventoryRef": first.json()["id"], "sha256": "0" * 64}
    assert ingest(cyber, src, [bad]).status_code == 422


def test_optional_twin_mapping_is_owned_installed_and_revision_bound(cyber, tmp_path):
    from app.twin_models import TwinAsset

    directory = tmp_path / "independent-owned-models"
    directory.mkdir(mode=0o700)
    settings = cyber.app.state.settings
    settings.digital_twins_enabled = True
    settings.digital_twins_demo_enabled = True
    settings.digital_twins_storage_directory = str(directory)
    response = cyber.post("/api/v1/twins/demo")
    assert response.status_code == 201
    twin, other = response.json()["assets"]
    component = twin["definition"]["components"][0]["id"]
    body = {
        "name": "Reviewed installed equipment",
        "identity": "installed-pump-01",
        "zone": "Isolated test",
        "criticality": "high",
        "review_note": "Explicit owner review of installed component association",
        "twin_asset_id": twin["id"],
        "twin_component_id": component,
    }
    created = cyber.post(BASE + "/assets", json=body)
    assert created.status_code == 201, created.text
    target = created.json()
    src = source(cyber)
    mapping(cyber, src, target)
    finding(cyber, src, True)
    linked = cyber.get(BASE + f"/twins/{twin['id']}/summary").json()["items"]
    assert linked[0]["component_id"] == component and linked[0]["mapping_current"] is True
    wrong = {
        **body,
        "identity": "wrong-component",
        "twin_component_id": other["definition"]["components"][0]["id"],
    }
    assert cyber.post(BASE + "/assets", json=wrong).status_code == 404
    with Session(cyber.app.state.engine) as db:
        row = db.get(TwinAsset, UUID(twin["id"]))
        row.revision += 1
        db.commit()
    stale = cyber.get(BASE + f"/twins/{twin['id']}/summary").json()["items"][0]
    assert stale["mapping_current"] is False and stale["component_id"] is None
    settings.cybersecurity_enabled = False
    assert cyber.get("/api/v1/twins/catalog").status_code == 200


def test_cited_mock_assistance_and_registered_tool_remain_read_only(cyber):
    src = source(cyber)
    value = finding(cyber, src)
    case = investigation(cyber, value)
    evidence_id = value["details"]["evidence"][0]["id"]

    class CitedMock:
        async def healthy(self):
            return True

        async def stream(self, messages):
            assert "Untrusted security evidence" in messages[0].content
            yield json.dumps(
                {
                    "hypotheses": [
                        {
                            "statement": (
                                "Review this observed rejection with the operator; "
                                "cause remains unverified."
                            ),
                            "citations": [evidence_id],
                        }
                    ]
                }
            )

    cyber.app.state.model_client = CitedMock()
    cyber.app.state.settings.cybersecurity_ai_enabled = True
    body = {"investigation_id": case["id"], "expected_sha256": case["sha256"]}
    response = cyber.post(BASE + "/summaries", json={**body, "assist": True})
    assert response.status_code == 201 and response.json()["result"]["status"] == "mock_assistance"
    assert response.json()["result"]["human_review_required"] is True
    assert len(json.dumps(cyber.post(BASE + "/tools/evidence", json=body).json()).encode()) <= 16384
    response = cyber.post(
        "/api/v1/agents/runs",
        json={
            "goal": "Read the explicitly authorized investigation",
            "allowed_tools": ["cybersecurity_evidence_v1"],
            "steps": [{"tool": "cybersecurity_evidence_v1", "arguments": body}],
        },
    )
    assert response.status_code == 201 and response.json()["status"] == "completed"
    assert state(cyber)["investigations"][0]["status"] == "open"


def test_evidence_checksum_and_authority_are_refreshed_after_inference(cyber):
    from app.cyber_models import CyberInvestigation
    from app.models import User

    value = finding(cyber, source(cyber))
    case = investigation(cyber, value)
    body = {"investigation_id": case["id"], "expected_sha256": case["sha256"]}
    with Session(cyber.app.state.engine) as db:
        row = db.get(CyberInvestigation, UUID(case["id"]))
        original = copy.deepcopy(row.snapshot)
        row.snapshot = {"modified": "An infrastructure change is not an authorized snapshot"}
        db.commit()
    assert cyber.post(BASE + "/tools/evidence", json=body).status_code == 503
    with Session(cyber.app.state.engine) as db:
        row = db.get(CyberInvestigation, UUID(case["id"]))
        row.snapshot = original
        owner = row.user_id
        db.commit()

    class RevokingMock:
        async def stream(self, messages):
            with Session(cyber.app.state.engine) as db:
                db.get(User, owner).status = "disabled"
                db.commit()
            yield '{"hypotheses":[]}'

    cyber.app.state.settings.cybersecurity_ai_enabled = True
    cyber.app.state.model_client = RevokingMock()
    response = cyber.post(BASE + "/summaries", json={**body, "assist": True})
    assert response.status_code == 401


def test_workspace_is_metadata_control_coverage_is_explicit_and_exports_page(cyber):
    src, target = source(cyber), asset(cyber)
    mapping(cyber, src, target)
    payloads = [event(i, mapped=True) for i in range(101)]
    assert ingest(cyber, src, payloads[:100]).status_code == 200
    assert ingest(cyber, src, payloads[100:]).status_code == 200
    raw = cyber.get(BASE + "/workspace").json()
    assert raw["findings"][0]["details"]["evidence"] == []
    assert raw["control_coverage"]["denominator"] == 8
    assert raw["control_coverage"]["assessed"] == 1 and raw["control_coverage"]["unknown"] == 7
    value = cyber.get(BASE + f"/findings/{raw['findings'][0]['id']}").json()["finding"]
    case = investigation(cyber, value)
    assert "snapshot" not in cyber.get(BASE + "/workspace").json()["investigations"][0]
    first = cyber.get(BASE + "/export", params={"source_id": src["id"]})
    assert first.status_code == 200 and len(first.json()["events"]) == 100
    second = cyber.get(
        BASE + "/export", params={"source_id": src["id"], "before": first.headers["X-Next-Cursor"]}
    )
    assert second.status_code == 200 and len(second.json()["events"]) == 1
    assert not (
        set(e["sourceEventId"] for e in first.json()["events"])
        & set(e["sourceEventId"] for e in second.json()["events"])
    )
    assert (
        len(
            cyber.post(
                BASE + "/tools/evidence",
                json={"investigation_id": case["id"], "expected_sha256": case["sha256"]},
            ).content
        )
        <= 16384
    )
    assert cyber.post(BASE + f"/sources/{src['id']}/revoke").status_code == 200
    assert cyber.get(BASE + "/workspace").json()["control_coverage"]["stale"] == 1


def test_opaque_uri_mapping_and_certificate_refs_never_fetch_or_relabel(cyber):
    target = asset(cyber)
    endpoint = "https://configured.example.com/connection"
    response = cyber.post(
        BASE + "/sources",
        json={
            "name": "Reviewed source",
            "namespace": "local-collector",
            "modes": ["live"],
            "endpoint_refs": [endpoint],
            "review_note": "Reviewed opaque endpoint reference without network probing",
        },
    )
    assert response.status_code == 201
    src = response.json()
    assert (
        cyber.post(
            BASE + f"/sources/{src['id']}/mappings",
            json={
                "asset_id": target["id"],
                "namespace": "https://namespace.example.com/assets",
                "external_asset": "gateway-01",
                "review_note": "Reviewed opaque URI namespace and local equipment",
            },
        ).status_code
        == 201
    )
    observation = event(kind="tls.certificate_observed", mapped=True)
    observation["assetRef"]["namespace"] = "https://namespace.example.com/assets"
    observation["attributes"]["endpointRef"] = endpoint
    assert ingest(cyber, src, [observation]).status_code == 200
    assert state(cyber)["events"][0]["wire"]["attributes"]["endpointRef"] == endpoint
    hostile = json.dumps({"events": [event(summary="bad\ud800unicode")]}).encode()
    assert (
        cyber.post(
            BASE + f"/sources/{src['id']}/imports",
            content=hostile,
            headers={"Content-Type": "application/json"},
        ).status_code
        == 422
    )


def test_standalone_release_observer_knows_migrated_optional_table_ownership(pg):
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    program = """
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, str(root / 'scripts/release'))
sys.path.insert(0, str(root / 'onesa-ai-platform-backend'))
from sqlalchemy import create_engine
from oracle_ai_probe import persistent_fingerprints
engine = create_engine(sys.stdin.read())
try:
    records = persistent_fingerprints(engine, [])
    assert 'cyber_investigations' in records and 'twin_models' in records
    assert len([name for name in records if name.startswith('cyber_')]) == 12
    print('STANDALONE_MIGRATED_PRESERVATION_PASS')
finally:
    engine.dispose()
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", program, str(root)],
        input=pg.url.render_as_string(hide_password=False),
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "STANDALONE_MIGRATED_PRESERVATION_PASS"
