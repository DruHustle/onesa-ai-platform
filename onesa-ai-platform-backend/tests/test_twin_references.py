"""Real PostgreSQL import ownership/retries and independently hashed reference assets."""

import copy
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app import twin_references
from app.models import AuthSession, now
from app.twin_files import sha
from app.twin_models import TwinAsset, TwinFile, TwinModel, TwinReading, TwinSource, TwinTemplate
from tests.conftest import signup


@pytest.fixture
def references(api, tmp_path):
    storage = tmp_path / "private-models"
    storage.mkdir(mode=0o700)
    config = api.app.state.settings
    config.digital_twins_enabled = True
    config.digital_twins_demo_enabled = False
    config.digital_twins_storage_directory = str(storage)
    signup(api)
    return api


def first():
    return twin_references.manifest()["assets"][0]


def import_model(api, identifier=None):
    return api.post(f"/api/v1/twins/references/{identifier or first()['id']}/import")


def test_catalog_matches_frontend_bytes_provenance_and_mesh_budgets():
    result = twin_references.catalog()
    public = Path(__file__).parents[2] / "onesa-ai-platform-frontend/apps/chat/public/models/nvidia"
    assert (public / "manifest.json").read_bytes() == (
        twin_references.ROOT / "manifest.json"
    ).read_bytes()
    assert len(result["assets"]) == 3
    for entry in result["assets"]:
        assert entry["author"] == "NVIDIA"
        assert entry["license"] == "CC-BY-4.0"
        assert entry["sourceRevision"] in entry["sourceUrl"]
        assert "Converted and optimized" in entry["attribution"]
        assert entry["visualOnly"] is True and entry["unit"] == "m"
        assert 0 < entry["triangles"] <= 30000
        assert 0 < len(entry["preview_model"]["definition"]["nodes"]) <= 100
        for kind in ("glb", "thumbnail", "sourceFile", "licenseFile"):
            data = (public / entry[kind]["path"]).read_bytes()
            assert data == twin_references.read_artifact(entry, kind)
            assert sha(data) == entry[kind]["sha256"]


def test_manifest_and_cached_geometry_reject_changed_bytes(tmp_path, monkeypatch):
    twin_references.catalog()  # Warm the geometry cache first.
    root = tmp_path / "references"
    shutil.copytree(twin_references.ROOT, root)
    monkeypatch.setattr(twin_references, "ROOT", root)
    path = root / first()["glb"]["path"]
    data = path.read_bytes()
    path.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
    with pytest.raises(ValueError, match="integrity"):
        twin_references.catalog()
    manifest_path = root / "manifest.json"
    value = json.loads(manifest_path.read_text())
    value["assets"][0]["sourceUrl"] = "https://invalid.example/unreviewed"
    manifest_path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="catalog integrity"):
        twin_references.manifest()


@pytest.mark.parametrize("kind", ["thumbnail", "sourceFile", "licenseFile"])
def test_required_provenance_and_fallback_files_cannot_disappear(tmp_path, monkeypatch, kind):
    root = tmp_path / "references"
    shutil.copytree(twin_references.ROOT, root)
    monkeypatch.setattr(twin_references, "ROOT", root)
    (root / first()[kind]["path"]).unlink()
    with pytest.raises(OSError):
        twin_references.catalog()


@pytest.mark.parametrize("path", ["../outside.glb", "/tmp/outside.glb", "nvidia-mobile-cart/../x"])
def test_reference_paths_cannot_escape_reviewed_bundle(path):
    entry = copy.deepcopy(first())
    entry["glb"]["path"] = path
    with pytest.raises(ValueError, match="artifact path"):
        twin_references.read_artifact(entry, "glb")


def test_all_references_import_without_simulation_or_connections(references, pg):
    assert references.get("/api/v1/twins/readiness").json()["simulation_enabled"] is False
    response = references.get("/api/v1/twins/references")
    assert response.status_code == 200
    for entry in response.json()["assets"]:
        response = import_model(references, entry["id"])
        assert response.status_code == 201, response.text
        row = response.json()["asset"]
        assert response.json()["created"] is True
        assert row["definition"]["visual_only"] is True
        assert row["definition"]["stage"] == "preview"
        detail = references.get(f"/api/v1/twins/assets/{row['id']}").json()
        assert detail["sources"] == [] and detail["state"] == []
        assert detail["documents"] == []
        model = detail["models"][0]
        assert model["definition"]["reference"]["glb"]["sha256"] == entry["glb"]["sha256"]
        assert model["definition"]["rights"] == "CC-BY-4.0"
        binary = references.get(f"/api/v1/twins/files/{model['file_id']}/content")
        assert binary.status_code == 200
        assert "no-store" in binary.headers["cache-control"]
        assert sha(binary.content) == entry["glb"]["sha256"]
    with Session(pg) as db:
        for cls in (TwinAsset, TwinModel, TwinTemplate, TwinFile):
            assert db.scalar(select(func.count()).select_from(cls)) == 3
        for cls in (TwinReading, TwinSource):
            assert db.scalar(select(func.count()).select_from(cls)) == 0


def test_retries_are_idempotent_even_when_workspace_quota_is_full(references, pg):
    created = import_model(references).json()
    with Session(pg) as db:
        existing = db.scalar(select(TwinTemplate))
        for index in range(99):
            db.add(
                TwinTemplate(user_id=existing.user_id, name=str(index), kind="test", definition={})
            )
        db.commit()
    repeated = import_model(references)
    assert repeated.status_code == 201, repeated.text
    assert repeated.json() == {"created": False, "asset": created["asset"]}
    with Session(pg) as db:
        for cls in (TwinAsset, TwinModel, TwinFile):
            assert db.scalar(select(func.count()).select_from(cls)) == 1


def test_concurrent_lost_response_retries_create_one_owned_copy(references, pg):
    def send(_):
        client = TestClient(references.app)
        client.cookies.update(references.cookies)
        client.headers.update(references.headers)
        try:
            response = import_model(client)
            assert response.status_code == 201, response.text
            return response.json()
        finally:
            client.close()

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(send, range(4)))
    assert sum(result["created"] for result in results) == 1
    assert len({result["asset"]["id"] for result in results}) == 1
    with Session(pg) as db:
        for cls in (TwinAsset, TwinModel, TwinTemplate, TwinFile):
            assert db.scalar(select(func.count()).select_from(cls)) == 1


def test_reference_import_preserves_existing_two_hundred_model_capacity(references, pg):
    entries = twin_references.manifest()["assets"]
    assert import_model(references, entries[0]["id"]).status_code == 201

    def fill_to(count):
        with Session(pg) as db:
            original = db.scalar(select(TwinModel))
            current = db.scalar(select(func.count()).select_from(TwinModel))
            for _ in range(count - current):
                db.add(
                    TwinModel(
                        user_id=original.user_id,
                        template_id=original.template_id,
                        file_id=original.file_id,
                        definition=original.definition,
                    )
                )
            db.commit()

    fill_to(100)
    assert import_model(references, entries[1]["id"]).status_code == 201
    fill_to(200)
    response = import_model(references, entries[2]["id"])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "twin_quota"
    with Session(pg) as db:
        assert db.scalar(select(func.count()).select_from(TwinModel)) == 200
        for cls in (TwinAsset, TwinTemplate, TwinFile):
            assert db.scalar(select(func.count()).select_from(cls)) == 2


def test_reference_imports_remain_owner_scoped_and_private(references):
    original = import_model(references).json()["asset"]
    detail = references.get(f"/api/v1/twins/assets/{original['id']}").json()
    file_id = detail["models"][0]["file_id"]
    references.cookies.clear()
    references.headers.pop("X-CSRF-Token")
    assert references.get("/api/v1/twins/references").status_code == 401
    signup(references, "second-reference-owner@example.com")
    assert references.get(f"/api/v1/twins/assets/{original['id']}").status_code == 404
    assert references.get(f"/api/v1/twins/files/{file_id}/content").status_code == 404
    second = import_model(references).json()["asset"]
    assert second["id"] != original["id"]
    assert second["template_id"] != original["template_id"]
    assert second["active_model_id"] != original["active_model_id"]


def test_reference_import_rechecks_revoked_session_before_persistence(references, pg, monkeypatch):
    original = twin_references.validated

    def revoke(entry):
        result = original(entry)
        with Session(pg) as db:
            db.execute(update(AuthSession).values(revoked_at=now()))
            db.commit()
        return result

    monkeypatch.setattr(twin_references, "validated", revoke)
    assert import_model(references).status_code == 401
    with Session(pg) as db:
        for cls in (TwinAsset, TwinModel, TwinTemplate, TwinFile):
            assert db.scalar(select(func.count()).select_from(cls)) == 0


def test_import_requires_csrf_enabled_feature_and_durable_storage(references):
    token = references.headers.pop("X-CSRF-Token")
    assert import_model(references).status_code == 403
    references.headers["X-CSRF-Token"] = token
    config = references.app.state.settings
    config.digital_twins_enabled = False
    assert references.get("/api/v1/twins/references").status_code == 404
    assert import_model(references).status_code == 404
    config.digital_twins_enabled = True
    assert import_model(references, "not-reviewed").status_code == 404
    config.environment = "production"
    assert import_model(references).status_code == 503
    config.digital_twins_persistent_mount = True
    assert import_model(references).status_code == 201
    assert references.get("/api/v1/twins/readiness").json()["simulation_enabled"] is False


def test_corrupt_reference_refuses_without_partial_records(references, pg, tmp_path, monkeypatch):
    root = tmp_path / "references"
    shutil.copytree(twin_references.ROOT, root)
    monkeypatch.setattr(twin_references, "ROOT", root)
    (root / first()["glb"]["path"]).write_bytes(b"invalid")
    response = import_model(references)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "twin_reference_unavailable"
    with Session(pg) as db:
        for cls in (TwinAsset, TwinModel, TwinTemplate, TwinFile):
            assert db.scalar(select(func.count()).select_from(cls)) == 0
