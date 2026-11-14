import json
from unittest.mock import patch

from app import release_identity


def test_identity_binds_build_and_distinguishes_instances_without_hostname(tmp_path):
    file = tmp_path / "identity.json"
    file.write_text(json.dumps({"source_commit": "a" * 40, "source_archive_sha256": "b" * 64}))
    with (
        patch.object(release_identity, "IDENTITY", file),
        patch.dict("os.environ", {"HOSTNAME": "private-instance-one"}),
    ):
        one = release_identity.identity("production")
        assert one["source_commit"] == "a" * 40
        assert "private-instance-one" not in json.dumps(one)
        assert one["instance_id"] != release_identity.identity("staging")["instance_id"]
        with patch.dict("os.environ", {"HOSTNAME": "private-instance-two"}):
            assert one["instance_id"] != release_identity.identity("production")["instance_id"]


def test_unstamped_development_build_never_claims_a_release(tmp_path):
    file = tmp_path / "identity.json"
    with patch.object(release_identity, "IDENTITY", file):
        assert release_identity.identity("development") == {}
        file.write_text(json.dumps({"source_commit": "unqualified", "source_archive_sha256": ""}))
        assert release_identity.identity("production") == {}
        file.write_text("invalid")
        assert release_identity.identity("production") == {}


def test_build_identity_alone_does_not_establish_readiness(tmp_path):
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    file = tmp_path / "identity.json"
    file.write_text(json.dumps({"source_commit": "a" * 40, "source_archive_sha256": "b" * 64}))
    with (
        patch.object(release_identity, "IDENTITY", file),
        TestClient(create_app(Settings(environment="test", database_url=None))) as client,
    ):
        response = client.get("/health")
        assert response.status_code == 200 and response.json()["source_commit"] == "a" * 40
        assert client.get("/core-ready").status_code == 503
