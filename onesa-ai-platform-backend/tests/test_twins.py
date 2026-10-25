"""Real PostgreSQL ownership, import, model and telemetry acceptance with synthetic records."""

import copy
import io
import json
import struct
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import now
from app.twin_demo import aas_environment, pump_aasx, pump_glb
from app.twin_files import FileStore, bounded_json, preview
from app.twin_models import TwinReading, TwinSource
from app.twin_schemas import ModelCreate
from app.twins import commentary_context
from tests.conftest import signup


def test_model_context_has_its_own_budget_and_keeps_the_full_evidence_unchanged():
    full = {
        "question": "Inspection",
        "equipment": {"id": "local-asset"},
        "component": {"id": "local-component"},
        "window": {"mode": "simulated"},
        "facts": [{"freshness": "good", "reading": "x" * 1000} for _ in range(32)],
        "history": {
            "readings": [{"value": index, "provenance": "x" * 1000} for index in range(100)],
            "events": [{"kind": "threshold_crossing"} for _ in range(100)],
        },
        "documents": [{"document_id": "local-document", "text": "manual " * 1000}],
    }
    raw = commentary_context(full)
    assert len(raw) <= 24000
    prompt = json.loads(raw)
    assert prompt["history"]["readings"][-1]["value"] == 99
    assert len(prompt["facts"]) <= 8 and prompt["documents"]
    assert len(full["history"]["readings"]) == 100
    assert len(full["facts"]) == 32 and len(full["documents"][0]["text"]) == 7000


def test_account_export_keeps_owned_twins_when_disabled_and_never_exports_source_credentials(twins):
    row = seed(twins)[0]
    src, _ = source(twins, row)
    assert ingest(twins, src, [sample(0.002, -1, unit="m/s")]).status_code == 200
    twins.app.state.settings.digital_twins_enabled = False
    response = twins.post("/api/v1/account/export", json={"current_password": "correct-horse-123!"})
    assert response.status_code == 200, response.text
    exported = response.json()["digital_twins"]
    assert len(exported["twin_assets"]) == 2
    assert exported["twin_readings"][0]["provenance"]["raw_unit"] == "m/s"
    assert src["ingestion_token"] not in response.text and "token_hash" not in response.text


def test_configured_model_contract_grounding_unavailability_and_local_core_independence(twins):
    row = seed(twins)[0]
    src, bearing = source(twins, row)
    assert ingest(twins, src, [sample(6, -1)]).status_code == 200
    document_id = detail(twins, row)["documents"][0]["document_id"]

    class FixtureModel:
        invalid = False
        unavailable = False
        calls = 0

        async def healthy(self):
            return not self.unavailable

        async def stream(self, _messages):
            self.calls += 1
            if self.unavailable:
                raise RuntimeError("Synthetic unavailable provider")
            yield json.dumps(
                {
                    "hypotheses": [
                        {
                            "statement": (
                                "Mounting or alignment may warrant inspection; this is unconfirmed"
                            ),
                            "document_id": document_id,
                            "quote": "Invented source quote"
                            if self.invalid
                            else (
                                "A vibration threshold is a rule output, "
                                "not a confirmed fault or prediction."
                            ),
                        }
                    ]
                }
            )

    model = FixtureModel()
    twins.app.state.model_client = model
    twins.app.state.settings.model_backend = "ollama"
    request = {
        **window(),
        "component_id": bearing["id"],
        "question": "bearing vibration inspection maintenance",
        "use_model": True,
    }
    path = f"/api/v1/twins/assets/{row['id']}/tools/evidence"
    response = twins.post(path, json=request)
    assert response.status_code == 200, response.text
    assert response.json()["assistant"]["status"] == "model_backed_unconfirmed_hypotheses"
    model.invalid = True
    assert (
        twins.post(path, json=request).json()["assistant"]["status"]
        == "model_unavailable_or_invalid"
    )
    model.unavailable = True
    assert (
        twins.post(path, json=request).json()["assistant"]["status"]
        == "model_unavailable_or_invalid"
    )
    assert twins.get("/core-ready").status_code == 200
    assert twins.get(f"/api/v1/twins/assets/{row['id']}").status_code == 200
    # A configured-provider fixture exercises the real gateway contract; it is not
    # reported as actual Ollama/model-backed acceptance.
    assert model.calls == 3


@pytest.fixture
def twins(api, tmp_path):
    directory = tmp_path / "private-models"
    directory.mkdir(mode=0o700)
    config = api.app.state.settings
    config.digital_twins_enabled = True
    config.digital_twins_demo_enabled = True
    config.digital_twins_storage_directory = str(directory)
    signup(api)
    return api


def seed(api):
    result = api.post("/api/v1/twins/demo")
    assert result.status_code == 201, result.text
    return result.json()["assets"]


def detail(api, asset):
    result = api.get(f"/api/v1/twins/assets/{asset['id']}")
    assert result.status_code == 200, result.text
    return result.json()


def source(api, asset):
    bearing = next(c for c in asset["definition"]["components"] if c["external_id"] == "bearing")
    response = api.post(
        f"/api/v1/twins/assets/{asset['id']}/sources",
        json={
            "name": "Simulated MQTT bearing",
            "mode": "simulated",
            "bindings": [
                {
                    "tag": "vibration",
                    "component_id": bearing["id"],
                    "metric": "vibration",
                    "unit": "mm/s",
                    "sample_seconds": 1,
                    "stale_seconds": 10,
                    "high": 5,
                    "hysteresis": 1,
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json(), bearing


def ingest(api, source, samples, mode="simulated"):
    return api.post(
        f"/api/v1/twins/sources/{source['id']}/readings",
        headers={"X-Onesa-Source-Token": source["ingestion_token"]},
        json={"mode": mode, "samples": samples},
    )


def sample(value, seconds, message=None, **kwargs):
    return {
        "message_id": message or str(uuid4()),
        "tag": "vibration",
        "value": value,
        "unit": "mm/s",
        "observed_at": (now() + timedelta(seconds=seconds)).isoformat(),
        **kwargs,
    }


def window():
    return {
        "start": (now() - timedelta(hours=1)).isoformat(),
        "end": (now() + timedelta(seconds=30)).isoformat(),
        "mode": "simulated",
    }


def test_disabled_and_scoped_storage_readiness(api, tmp_path):
    signup(api)
    assert api.get("/api/v1/twins/catalog").status_code == 404
    api.app.state.settings.digital_twins_enabled = True
    status = api.get("/api/v1/twins/readiness").json()
    assert status["enabled"] and not status["ready"]
    assert api.get("/health").status_code == 200
    assert (
        api.post("/api/v1/twins/files", files={"file": ("pump.glb", pump_glb())}).status_code == 503
    )


def test_two_installations_share_model_but_keep_stable_distinct_components(twins):
    a, b = seed(twins)
    assert a["template_id"] == b["template_id"] and a["active_model_id"] == b["active_model_id"]
    assert a["serial"] != b["serial"]
    assert {c["id"] for c in a["definition"]["components"]}.isdisjoint(
        c["id"] for c in b["definition"]["components"]
    )
    assert {c["template_component_id"] for c in a["definition"]["components"]} == {
        c["template_component_id"] for c in b["definition"]["components"]
    }
    assert twins.post("/api/v1/twins/demo").json()["created"] is False
    assert len(twins.get("/api/v1/twins/catalog").json()["assets"]) == 2


def test_actual_aasx_preview_preserves_unknown_data_and_requires_review(twins):
    response = twins.post("/api/v1/twins/files", files={"file": ("pump.aasx", pump_aasx())})
    assert response.status_code == 201, response.text
    original = response.json()
    assert original["details"]["unsupported"][0]["type"] == "MultiLanguageProperty"
    assert original["details"]["preserved_environment"]["submodels"]
    attachments = original["details"]["attachments"]
    geometry = next(a for a in attachments if a["path"].endswith(".glb"))
    imported = twins.post(
        f"/api/v1/twins/imports/{original['id']}/commit",
        json={
            "name": "Imported pump",
            "serial": "IMPORTED-01",
            "geometry_file_id": geometry["id"],
            "include_documents": True,
        },
    )
    assert imported.status_code == 201, imported.text
    row = imported.json()
    assert row["active_model_id"] is None and row["definition"]["stage"] == "mapping"
    assert row["definition"]["identifier_map"]["urn:onesa:demo:pump:aas:1"] == row["id"]
    assert twins.get(
        f"/api/v1/twins/files/{original['id']}/content"
    ).content == pump_aasx() or twins.get(
        f"/api/v1/twins/files/{original['id']}/content"
    ).content.startswith(b"PK")
    assert detail(twins, row)["documents"][0]["title"] == "maintenance.txt"
    model = detail(twins, row)["models"][0]
    activated = twins.patch(
        f"/api/v1/twins/assets/{row['id']}",
        json={"expected_revision": row["revision"], "stage": "active", "model_id": model["id"]},
    )
    assert activated.status_code == 200, activated.text
    again = twins.post(
        f"/api/v1/twins/imports/{original['id']}/commit",
        json={"name": "Ignored duplicate", "serial": "IMPORTED-02"},
    )
    assert again.json()["id"] == row["id"]


def test_external_geometry_is_not_fetched_or_presented_as_rendered(twins):
    data = json.dumps(aas_environment(external=True)).encode()
    response = twins.post("/api/v1/twins/files", files={"file": ("external.json", data)})
    assert response.status_code == 201, response.text
    value = response.json()
    assert any(r["status"] == "external_not_fetched" for r in value["details"]["references"])
    row = twins.post(
        f"/api/v1/twins/imports/{value['id']}/commit",
        json={"name": "No geometry", "serial": "NO-GEOMETRY"},
    ).json()
    assert row["active_model_id"] is None
    assert (
        twins.patch(
            f"/api/v1/twins/assets/{row['id']}", json={"expected_revision": 1, "stage": "active"}
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "filename,data",
    [
        ("invalid.glb", b"glTF-invalid"),
        (
            "old.json",
            b'{"assetAdministrationShells":[{"modelType":{"name":"AssetAdministrationShell"}}]}',
        ),
        ("future.json", b'{"specVersion":"999"}'),
        ("duplicate.json", b'{"submodels":[],"submodels":[]}'),
        ("external.gltf", b'{"asset":{"version":"2.0"},"buffers":[{"uri":"http://127.0.0.1/"}]}'),
    ],
)
def test_invalid_or_unsupported_uploads_fail_closed(twins, filename, data):
    assert twins.post("/api/v1/twins/files", files={"file": (filename, data)}).status_code == 422


@pytest.mark.parametrize(
    "name,content",
    [
        ("../outside.txt", b"x"),
        ("/absolute.txt", b"x"),
        ("bomb.txt", b"x" * (1024 * 1024)),
        ("_rels/.rels", b'<!DOCTYPE x [<!ENTITY a SYSTEM "file:///etc/passwd">]><x>&a;</x>'),
    ],
)
def test_archive_traversal_expansion_entities(name, content):
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr(name, content)
    with pytest.raises((ValueError, zipfile.BadZipFile, OSError)):
        preview(target.getvalue(), "unsafe.aasx")


def test_glb_resource_reference_and_geometry_budget():
    raw = pump_glb()
    size = struct.unpack_from("<I", raw, 12)[0]
    model = json.loads(raw[20 : 20 + size])
    binary = raw[20 + size :]
    for change in (
        lambda m: m["buffers"][0].update(uri="http://127.0.0.1/private"),
        lambda m: m["accessors"][0].update(count=10000000),
        lambda m: m["nodes"][0].update(children=[0]),
    ):
        value = json.loads(json.dumps(model))
        change(value)
        encoded = json.dumps(value).encode()
        encoded += b" " * (-len(encoded) % 4)
        candidate = (
            struct.pack("<4sII", b"glTF", 2, 20 + len(encoded) + len(binary))
            + struct.pack("<II", len(encoded), 0x4E4F534A)
            + encoded
            + binary
        )
        with pytest.raises(ValueError):
            preview(candidate, "invalid.glb")
    with pytest.raises(ValueError):
        bounded_json(b'{"value":1e999}')


def test_mapping_replacement_preserves_component_identity_and_revision_fences(twins):
    row = seed(twins)[0]
    old = detail(twins, row)["models"][0]
    body = copy.deepcopy(
        {k: v for k, v in old["definition"].items() if k in ModelCreate.model_fields}
    )
    body["mappings"][1]["node"] = body["mappings"][0]["node"]
    assert twins.post("/api/v1/twins/models", json=body).status_code == 422
    body = {k: v for k, v in old["definition"].items() if k in ModelCreate.model_fields}
    original = pump_glb()
    json_length = struct.unpack_from("<I", original, 12)[0]
    scene = json.loads(original[20 : 20 + json_length])
    # A genuinely different model revision with changed scene labels still needs
    # an explicit mapping to the same stable equipment components.
    for node in scene["nodes"]:
        node["name"] = "Replacement " + node["name"]
    changed = json.dumps(scene, separators=(",", ":")).encode()
    changed += b" " * (-len(changed) % 4)
    tail = original[20 + json_length :]
    replacement = (
        struct.pack("<III", 0x46546C67, 2, 20 + len(changed) + len(tail))
        + struct.pack("<II", len(changed), 0x4E4F534A)
        + changed
        + tail
    )
    uploaded = twins.post("/api/v1/twins/files", files={"file": ("replacement.glb", replacement)})
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["sha256"] != old["definition"]["sha256"]
    body["file_id"] = uploaded.json()["id"]
    body["provenance"] = "Reviewed replacement; same stable components"
    new = twins.post("/api/v1/twins/models", json=body)
    assert new.status_code == 201, new.text
    updated = twins.patch(
        f"/api/v1/twins/assets/{row['id']}",
        json={
            "expected_revision": row["revision"],
            "stage": "active",
            "model_id": new.json()["id"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["definition"]["components"] == row["definition"]["components"]
    assert (
        twins.patch(
            f"/api/v1/twins/assets/{row['id']}",
            json={"expected_revision": row["revision"], "stage": "active"},
        ).status_code
        == 409
    )


def test_telemetry_units_duplicates_late_bad_stale_hysteresis_and_replay(twins):
    a, b = seed(twins)
    src, bearing = source(twins, a)
    readings = [sample(2, -9), sample(6, -8), sample(4.5, -7), sample(3, -6)]
    assert ingest(twins, src, readings).json() == {
        "accepted": 4,
        "duplicates": 0,
        "mode": "simulated",
    }
    assert ingest(twins, src, readings).json()["duplicates"] == 4
    same_time = {**readings[-1], "message_id": "different-id-same-observation"}
    assert ingest(twins, src, [same_time]).json()["duplicates"] == 1
    assert ingest(twins, src, [{**same_time, "value": 7}]).status_code == 409
    assert ingest(twins, src, [{**readings[0], "value": 999}]).status_code == 409
    assert ingest(twins, src, [sample(100, -10)]).status_code == 200
    assert ingest(twins, src, [sample(999, -5)], mode="replay").status_code == 200
    current = detail(twins, a)["state"][0]
    assert current["reading"]["value"] == 3 and current["freshness"] == "good"
    history = twins.post(f"/api/v1/twins/assets/{a['id']}/history", json=window()).json()
    assert len(history["events"]) == 2
    assert {e["kind"] for e in history["events"]} == {"threshold_crossing", "threshold_recovery"}
    assert not detail(twins, b)["state"]
    assert ingest(twins, src, [sample(0.002, -4, unit="m/s")]).status_code == 200
    assert detail(twins, a)["state"][0]["reading"]["value"] == 2
    assert ingest(twins, src, [sample(1, -3, unit="bar")]).status_code == 422
    assert ingest(twins, src, [sample(9, -2, quality="bad")]).status_code == 200
    assert detail(twins, a)["state"][0]["freshness"] == "bad"
    with Session(twins.app.state.engine) as db:
        for reading in db.scalars(select(TwinReading).where(TwinReading.asset_id == UUID(a["id"]))):
            reading.observed_at -= timedelta(minutes=5)
        source_row = db.get(TwinSource, UUID(src["id"]))
        source_row.last_seen_at -= timedelta(minutes=5)
        db.commit()
    current = detail(twins, a)["state"][0]
    assert current["freshness"] == "stale" and current["connection"] == "disconnected"
    assert current["reading"]["quality"] == "bad"
    assert twins.delete(f"/api/v1/twins/sources/{src['id']}").status_code == 204
    assert ingest(twins, src, [sample(1, -1)]).status_code == 401


def test_simultaneous_duplicate_ingestion_is_atomic(twins):
    a = seed(twins)[0]
    src, _ = source(twins, a)
    body = {"mode": "simulated", "samples": [sample(3, -1, message="same-observation")]}

    def attempt(_):
        with TestClient(twins.app) as client:
            return client.post(
                f"/api/v1/twins/sources/{src['id']}/readings",
                headers={"X-Onesa-Source-Token": src["ingestion_token"]},
                json=body,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(attempt, range(2)))
    assert [r.status_code for r in responses] == [200, 200]
    assert sorted(r.json()["accepted"] for r in responses) == [0, 1]


def test_grounded_tool_report_persists_and_mock_is_explicit(twins):
    row = seed(twins)[0]
    src, bearing = source(twins, row)
    assert ingest(twins, src, [sample(6, -1)]).status_code == 200
    request = {
        **window(),
        "component_id": bearing["id"],
        "question": "bearing vibration inspection maintenance",
        "use_model": True,
    }
    evidence = twins.post(f"/api/v1/twins/assets/{row['id']}/tools/evidence", json=request)
    assert evidence.status_code == 200, evidence.text
    value = evidence.json()
    assert value["assistant"]["status"] == "mock_not_model_verified"
    assert (
        value["documents"]
        and value["history"]["events"]
        and value["facts"][0]["reading"]["unit"] == "mm/s"
    )
    assert value["viewer_actions"][0]["component_ids"] == [bearing["id"]]
    saved = twins.post(
        f"/api/v1/twins/assets/{row['id']}/inspections", json={**request, "use_model": False}
    )
    assert saved.status_code == 201, saved.text
    restored = detail(twins, row)["notes"][0]
    assert restored["id"] == saved.json()["id"]
    assert restored["payload"]["evidence_sha256"] and restored["payload"]["checklist"]
    assert "history" not in restored["payload"]["evidence"]
    snapshot = twins.get(restored["snapshot_url"])
    assert snapshot.json()["payload"] == saved.json()["payload"]
    contract = twins.get(f"/api/v1/twins/assets/{row['id']}/robotics/v1").json()
    assert contract["contract_version"] == 1 and contract["capabilities"]["visualization_mesh"]
    assert not any(
        contract["capabilities"][key]
        for key in (
            "collision_geometry",
            "actuation",
            "calibrated_kinematics",
            "planning_environment",
        )
    )


def test_foreign_owner_cannot_access_any_derived_resource(twins):
    row = seed(twins)[0]
    src, bearing = source(twins, row)
    model = detail(twins, row)["models"][0]
    doc = detail(twins, row)["documents"][0]
    note = twins.post(
        f"/api/v1/twins/assets/{row['id']}/notes",
        json={
            "kind": "annotation",
            "component_id": bearing["id"],
            "text": "Private inspection",
        },
    ).json()
    twins.post("/api/v1/auth/logout")
    signup(twins, "foreign@example.com")
    base = f"/api/v1/twins/assets/{row['id']}"
    assert twins.get("/api/v1/twins/catalog").json()["assets"] == []
    for path in (
        base,
        base + "/robotics/v1",
        f"/api/v1/twins/files/{model['file_id']}",
        f"/api/v1/twins/files/{model['file_id']}/content",
        f"/api/v1/twins/notes/{note['id']}",
    ):
        assert twins.get(path).status_code == 404
    for path, body in [
        (base + "/history", window()),
        (base + "/tools/evidence", {**window(), "component_id": bearing["id"]}),
        (base + "/inspections", {**window(), "component_id": bearing["id"]}),
        (base + "/viewer-actions", {"action": "focus_component", "component_ids": [bearing["id"]]}),
        (base + "/documents", {"document_id": doc["document_id"]}),
    ]:
        assert twins.post(path, json=body).status_code == 404
    assert twins.delete(f"/api/v1/twins/sources/{src['id']}").status_code == 404
    assert (
        twins.post(
            f"/api/v1/twins/sources/{src['id']}/readings",
            json={"mode": "simulated", "samples": [sample(1, -1)]},
        ).status_code
        == 401
    )


def test_invalid_viewer_actions_and_cross_instance_component_are_rejected(twins):
    a, b = seed(twins)
    cid = b["definition"]["components"][0]["id"]
    assert (
        twins.post(
            f"/api/v1/twins/assets/{a['id']}/viewer-actions",
            json={"action": "focus_component", "component_ids": [cid]},
        ).status_code
        == 404
    )
    assert (
        twins.post(
            f"/api/v1/twins/assets/{a['id']}/viewer-actions",
            json={"action": "execute_javascript", "component_ids": [cid]},
        ).status_code
        == 422
    )


def test_private_file_store_integrity_symlink_and_configuration(tmp_path):
    assert not FileStore("").ready()
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    store = FileStore(str(directory))
    owner = uuid4()
    checksum = store.put(owner, b"original")
    assert store.read(owner, checksum) == b"original"
    store.path(owner, checksum).write_bytes(b"modified")
    with pytest.raises(ValueError):
        store.read(owner, checksum)
    other = uuid4()
    (directory / str(other)).symlink_to(directory / str(owner))
    with pytest.raises(ValueError):
        store.read(other, checksum)


def test_local_simulator_needs_no_broker_and_cannot_mutate_live_or_other_instances(twins):
    a, b = seed(twins)
    bearing = next(c for c in a["definition"]["components"] if c["external_id"] == "bearing")
    path = f"/api/v1/twins/assets/{a['id']}/simulate"
    result = twins.post(path, json={"component_id": bearing["id"], "scenario": "cycle"})
    assert result.status_code == 200, result.text
    assert result.json()["accepted"] == 4 and result.json()["mode"] == "simulated"
    assert detail(twins, a)["state"][0]["reading"]["value"] == 3
    history = twins.post(f"/api/v1/twins/assets/{a['id']}/history", json=window()).json()
    assert len(history["events"]) == 2
    paused = twins.post(path, json={"component_id": bearing["id"], "scenario": "disconnect"})
    assert paused.status_code == 200
    assert detail(twins, a)["state"][0]["freshness"] == "stale"
    assert detail(twins, a)["state"][0]["connection"] == "disconnected"
    assert not detail(twins, b)["state"]
    live = twins.get(f"/api/v1/twins/assets/{a['id']}?mode=live").json()
    assert live["state"] == []
    assert twins.get("/core-ready").status_code == 200
    twins.app.state.settings.digital_twins_demo_enabled = False
    assert (
        twins.post(path, json={"component_id": bearing["id"], "scenario": "cycle"}).status_code
        == 404
    )
