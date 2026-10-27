"""Pinned runner failure boundaries, using synthetic stores and disposable files."""

import hashlib
import io
import json
import subprocess
import tarfile
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import oracle_ai_runner as r
import oracle_owner as o
import test_oracle_owner as owner_fixture


class LedgerBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        owner_fixture.OwnerStoreTests.setUpClass()

    def setUp(self):
        self.fixture = owner_fixture.OwnerStoreTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.store = self.fixture.store
        self.binding = self.fixture.binding
        self.root = self.fixture.root
        trust = json.loads((self.root / "trust.json").read_bytes())
        self.registry = {"installations": {str(self.root): {**trust, "active": True}}}
        self.private = patch.object(r, "private", side_effect=lambda p, **kw: Path(p))
        self.private.start()
        self.addCleanup(self.private.stop)
        self.reader = patch.object(
            r,
            "read",
            side_effect=lambda p: (
                self.registry
                if str(p) == "/etc/onesa/oracle-release-trust.json"
                else json.loads(Path(p).read_bytes())
            ),
        )
        self.reader.start()
        self.addCleanup(self.reader.stop)

    def call(self, identifier, *, phase="staging", binding=None):
        return r.verify_invocation(
            binding or self.binding,
            {"context_id": identifier},
            phase,
            {"verifier_store": str(self.root)},
        )

    def test_valid_signed_owner_context_must_already_be_reserved(self):
        identifier = self.fixture.context()
        with self.assertRaises(r.Refused):
            self.call(identifier)
        self.store.db.execute(
            "UPDATE contexts SET state='reserved' WHERE id=?", (identifier,)
        )
        rows = self.call(identifier)
        self.assertEqual(rows[0]["id"], identifier)
        self.store.db.execute(
            "UPDATE contexts SET state='consumed' WHERE id=?", (identifier,)
        )
        with self.assertRaises(r.Refused):
            self.call(identifier)

    def test_owner_zero_is_not_unsigned_actions_or_changed_source_authority(self):
        identifier = self.fixture.context()
        self.store.db.execute(
            "UPDATE contexts SET state='reserved' WHERE id=?", (identifier,)
        )
        for key, value in [
            ("candidate_commit", "f" * 40),
            ("component", "frontend"),
            ("target_environment", "staging"),
            ("artifact_digest", "sha256:" + "f" * 64),
        ]:
            with self.subTest(key=key), self.assertRaises(r.Refused):
                self.call(identifier, binding={**self.binding, key: value})
        envelope = self.store.get(identifier)
        envelope["record"]["workflow_run_id"] = 123
        self.store.db.execute(
            "UPDATE records SET envelope=? WHERE id=?",
            (o.canonical(envelope).decode(), identifier),
        )
        with self.assertRaises(r.Refused):
            self.call(identifier)

    def test_revoked_anchor_and_revoked_record_fail_closed(self):
        identifier = self.fixture.context()
        self.store.db.execute(
            "UPDATE contexts SET state='reserved' WHERE id=?", (identifier,)
        )
        self.registry["installations"][str(self.root)]["active"] = False
        with self.assertRaises(r.Refused):
            self.call(identifier)
        self.registry["installations"][str(self.root)]["active"] = True
        self.store.db.execute("UPDATE records SET revoked=1 WHERE id=?", (identifier,))
        with self.assertRaises(r.Refused):
            self.call(identifier)

    def test_context_cannot_be_presented_as_deployment_authorization(self):
        identifier = self.fixture.context()
        self.store.db.execute(
            "UPDATE contexts SET state='reserved' WHERE id=?", (identifier,)
        )
        with self.assertRaises(r.Refused):
            self.call(identifier, phase="deploy")


class ProbeResourceTests(unittest.TestCase):
    def test_source_resources_are_required_and_unrelated_public_files_excluded(self):
        resource = r.PROBE_RESOURCE_FILES[0]
        with self.assertRaisesRegex(r.Refused, "RESOURCE_SOURCE_MISSING"):
            r.probe_source_files({"scripts/probe.py": "a" * 64})
        files = {
            "scripts/probe.py": "a" * 64,
            resource: "b" * 64,
            "onesa-ai-platform-frontend/apps/chat/public/unrelated.json": "c" * 64,
        }
        self.assertEqual(
            r.probe_source_files(files),
            {"scripts/probe.py": "a" * 64, resource: "b" * 64},
        )

    def test_missing_or_modified_image_resource_fails_before_scan_acceptance(self):
        resource = r.PROBE_RESOURCE_FILES[0]
        expected = {"scripts/probe.py": "a" * 64, resource: "b" * 64}
        for actual in [
            {"scripts/probe.py": "a" * 64},
            {**expected, resource: "c" * 64},
        ]:
            with (
                self.subTest(actual=actual),
                patch.object(
                    r, "trusted_toolchain", return_value={"probe_files": expected}
                ),
                patch.object(
                    r, "docker", return_value=json.dumps(actual).encode()
                ) as docker,
                patch.object(r, "image_security") as scan,
                self.assertRaisesRegex(r.Refused, "PROBE_BYTES_DIFFER"),
            ):
                r.verify_probe_bytes(
                    Path("/synthetic"), {}, {"probe_image": "sha256:" + "d" * 64}
                )
            self.assertIn(resource, docker.call_args.args[-1])
            self.assertIn("--read-only", docker.call_args.args)
            scan.assert_not_called()


class ArchiveTests(unittest.TestCase):
    def test_source_tar_is_bound_to_git_tree_not_only_image_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "source.tar"
            body = b"# own source\n"
            blob = hashlib.sha1(
                b"blob " + str(len(body)).encode() + b"\0" + body
            ).digest()
            tree = b"100644 twin_files.py\0" + blob

            def tree_sha(raw):
                return hashlib.sha1(
                    b"tree " + str(len(raw)).encode() + b"\0" + raw
                ).digest()

            app = tree_sha(tree)
            backend = tree_sha(b"40000 app\0" + app)
            root = tree_sha(b"40000 onesa-ai-platform-backend\0" + backend).hex()
            with tarfile.open(source, "w") as archive:
                member = tarfile.TarInfo("onesa-ai-platform-backend/app/twin_files.py")
                member.size = len(body)
                member.mode = 0o644
                archive.addfile(member, io.BytesIO(body))
            binding = {
                "source_tree": root,
                "artifact_digest": "sha256:" + "a" * 64,
                "candidate_commit": "a" * 40,
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }
            expected = {"app/twin_files.py": hashlib.sha256(body).hexdigest()}
            with (
                patch.object(r, "private", side_effect=lambda p, **kw: Path(p)),
                patch.object(
                    r,
                    "docker",
                    return_value=json.dumps(
                        {
                            "files": expected,
                            "identity": {
                                "source_commit": binding["candidate_commit"],
                                "source_archive_sha256": binding["source_sha256"],
                            },
                        }
                    ).encode(),
                ) as docker,
            ):
                r.verify_application_bytes(folder, binding)
                self.assertEqual(docker.call_count, 1)
                with self.assertRaises(r.Refused):
                    r.verify_application_bytes(
                        folder, {**binding, "source_tree": "f" * 40}
                    )
                self.assertEqual(docker.call_count, 1)

    def test_archive_path_alias_refused_before_image_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with tarfile.open(folder / "source.tar", "w") as archive:
                member = tarfile.TarInfo("../escape")
                member.size = 1
                archive.addfile(member, io.BytesIO(b"x"))
            with (
                patch.object(r, "private", side_effect=lambda p, **kw: Path(p)),
                patch.object(r, "docker") as docker,
            ):
                with self.assertRaises(r.Refused):
                    r.verify_application_bytes(folder, {"source_tree": "a" * 40})
                docker.assert_not_called()


class OperationTests(unittest.TestCase):
    def fixture(self, folder):
        identifier = str(uuid4())
        source = "a" * 40
        image = "sha256:" + "b" * 64
        row = {
            "Id": "old-id",
            "Image": "sha256:" + "c" * 64,
            "Name": "/" + r.TARGET["production"],
            "RestartCount": 0,
            "State": {
                "StartedAt": "2026-10-26T00:00:00Z",
                "Running": True,
                "OOMKilled": False,
                "Health": {"Status": "healthy"},
            },
            "Config": {
                "Env": ["KEY=synthetic"],
                "Labels": {"org.onesa.source-commit": "d" * 40},
            },
        }
        mapping = folder / "images.env"
        mapping.write_text(
            "ORACLE_PRODUCTION_IMAGE="
            + row["Image"]
            + "\nORACLE_PRODUCTION_COMMIT="
            + "d" * 40
            + "\n"
        )
        (folder / "operations").mkdir()
        binding = {"candidate_commit": source, "artifact_digest": image}
        runtime = folder / "runtime.env"
        runtime.write_text("KEY=synthetic\n")
        (folder / "candidate.env").write_text("KEY=synthetic\n")
        plan = {
            "baseline": {"production": r.summary(row)},
            "mode": "twins",
            "baseline_runtime_sha256": {"production": r.sha(runtime)},
        }
        return identifier, row, mapping, binding, plan

    def test_interrupted_provider_request_is_never_automatically_duplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            operation, row, mapping, binding, plan = self.fixture(folder)
            calls = []

            def provider(*a, **kw):
                calls.append(a)
                raise subprocess.TimeoutExpired("synthetic-provider", 1)

            with (
                patch.object(r, "private", side_effect=lambda p, **kw: Path(p)),
                patch.object(r, "IMAGES", mapping),
                patch.object(r, "backup_lock", side_effect=nullcontext),
                patch.object(r, "update_backup_runtime_binding"),
                patch.object(r, "ENV", {"production": folder / "runtime.env"}),
                patch.object(
                    r, "candidate_environment", return_value=folder / "candidate.env"
                ),
                patch.object(
                    r, "inventory", return_value={r.TARGET["production"]: row}
                ),
                patch.object(r, "migrate", return_value=None),
                patch.object(r.subprocess, "run", side_effect=provider),
            ):
                with self.assertRaisesRegex(r.Refused, "PROVIDER_REQUEST_NOT_ACCEPTED"):
                    r.activate(binding, "production", operation, folder, plan)
                with self.assertRaises(FileExistsError):
                    r.activate(binding, "production", operation, folder, plan)
            self.assertEqual(len(calls), 1)
            receipt = json.loads(
                (
                    folder / "operations" / operation / "provider-receipt.json"
                ).read_text()
            )
            self.assertIsNone(receipt["provider_exit"])
            self.assertEqual(receipt["deployment_id"], "old-id")
            self.assertTrue(
                (folder / "operations" / operation / "intent.json").is_file()
            )

    def test_simultaneous_operation_has_one_migration_and_provider_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            operation, row, mapping, binding, plan = self.fixture(folder)
            counts = []
            barrier = threading.Barrier(2)

            def attempt():
                barrier.wait()
                try:
                    r.activate(binding, "production", operation, folder, plan)
                except (FileExistsError, r.Refused):
                    return

            def provider(*a, **kw):
                counts.append("provider")
                return SimpleNamespace(returncode=0)

            with (
                patch.object(r, "private", side_effect=lambda p, **kw: Path(p)),
                patch.object(r, "IMAGES", mapping),
                patch.object(r, "backup_lock", side_effect=nullcontext),
                patch.object(r, "update_backup_runtime_binding"),
                patch.object(r, "ENV", {"production": folder / "runtime.env"}),
                patch.object(
                    r, "candidate_environment", return_value=folder / "candidate.env"
                ),
                patch.object(
                    r, "inventory", return_value={r.TARGET["production"]: row}
                ),
                patch.object(
                    r, "migrate", side_effect=lambda *a: counts.append("migration")
                ),
                patch.object(r.subprocess, "run", side_effect=provider),
                ThreadPoolExecutor(max_workers=2) as executor,
            ):
                list(executor.map(lambda _: attempt(), range(2)))
            self.assertEqual(counts.count("provider"), 1)
            self.assertEqual(counts.count("migration"), 1)


class ImageEvidenceTests(unittest.TestCase):
    def test_current_exact_image_keeps_same_high_critical_and_secret_gate(self):
        scan = {
            "Metadata": {"ImageID": "fixture"},
            "Results": [{"Vulnerabilities": [{"Severity": "LOW"}]}],
            "ArtifactName": "fixture",
            "CreatedAt": r.now().isoformat(),
        }
        r.image_security(scan, "fixture")
        for changed in [
            dict(scan, Metadata={"ImageID": "wrong"}),
            dict(scan, CreatedAt="2020-01-01T00:00:00Z"),
            dict(scan, Results=[]),
            dict(scan, Results=[{"Vulnerabilities": [{"Severity": "HIGH"}]}]),
            dict(scan, Results=[{"Secrets": [{"RuleID": "synthetic"}]}]),
        ]:
            with self.subTest(changed=changed), self.assertRaises(r.Refused):
                r.image_security(changed, "fixture")


class OciDescriptorTests(unittest.TestCase):
    def proof(self, value):
        raw = json.dumps(value).encode()
        digest = "sha256:" + hashlib.sha256(raw).hexdigest()
        return digest, {digest: r.base64.b64encode(raw).decode()}

    def test_scanner_config_is_cryptographically_linked_to_actual_manifest(self):
        config = "sha256:" + "a" * 64
        manifest, proof = self.proof(
            {
                "schemaVersion": 2,
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "config": {"digest": config},
            }
        )
        self.assertEqual(r.scanned_configuration_digest(manifest, proof), config)
        index, parent = self.proof(
            {
                "schemaVersion": 2,
                "manifests": [
                    {
                        "digest": manifest,
                        "platform": {"os": "linux", "architecture": "arm64"},
                    }
                ],
            }
        )
        self.assertEqual(
            r.scanned_configuration_digest(index, {**proof, **parent}), config
        )
        scan = {
            "Metadata": {"ImageID": config},
            "CreatedAt": r.now().isoformat(),
            "ArtifactName": "fixture",
            "Results": [{}],
        }
        with patch.object(r, "read", return_value=proof):
            r.image_security(scan, manifest)
            with self.assertRaises(r.Refused):
                r.image_security(
                    {**scan, "Metadata": {"ImageID": "sha256:" + "b" * 64}}, manifest
                )

    def test_modified_or_foreign_platform_proof_cannot_relabel_a_scan(self):
        digest, proof = self.proof(
            {
                "schemaVersion": 2,
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "config": {"digest": "sha256:" + "a" * 64},
            }
        )
        with self.assertRaises(r.Refused):
            r.scanned_configuration_digest(
                digest, {digest: r.base64.b64encode(b"{}").decode()}
            )
        index, parent = self.proof(
            {
                "schemaVersion": 2,
                "manifests": [
                    {
                        "digest": digest,
                        "platform": {"os": "linux", "architecture": "amd64"},
                    }
                ],
            }
        )
        with self.assertRaises(r.Refused):
            r.scanned_configuration_digest(index, {**parent, **proof})
        with self.assertRaises(r.Refused):
            r.scanned_configuration_digest(digest, {})


class ProbeCapacityTests(unittest.TestCase):
    def test_probe_fits_existing_one_cpu_daemon_without_expanding_two_cpu_ceiling(self):
        for observed, expected in [(b"1\n", "1"), (b"2\n", "2"), (b"8\n", "2")]:
            with (
                self.subTest(observed=observed),
                patch.object(r, "docker", return_value=observed) as docker,
            ):
                self.assertEqual(r.probe_cpu_limit(), expected)
                docker.assert_called_once_with(
                    "info", "--format", "{{.NCPU}}", timeout=15
                )

    def test_missing_invalid_or_failed_daemon_observation_never_defaults_to_capacity(
        self,
    ):
        for observed in [b"", b"0", b"-1", b"1.5", b"unknown", b"10000"]:
            with (
                self.subTest(observed=observed),
                patch.object(r, "docker", return_value=observed),
                self.assertRaises(r.Refused),
            ):
                r.probe_cpu_limit()
        with (
            patch.object(r, "docker", side_effect=r.Refused("DAEMON_UNAVAILABLE")),
            self.assertRaises(r.Refused),
        ):
            r.probe_cpu_limit()


class ComponentCheckScopeTests(unittest.TestCase):
    def test_cybersecurity_requires_its_own_checks_without_twins_or_skips(self):
        api = r.required_probe_checks(
            {"component": "api"}, "production", "cybersecurity"
        )
        stage = r.required_probe_checks(
            {"component": "api"}, "staging", "cybersecurity"
        )
        front = r.required_probe_checks(
            {"component": "frontend"}, "production", "cybersecurity"
        )
        self.assertTrue(
            {
                "cybersecurity_ingestion",
                "cybersecurity_findings",
                "cybersecurity_decisions",
                "cybersecurity_native_configuration",
                "cybersecurity_revocation",
                "cybersecurity_export",
            }
            <= api
        )
        self.assertNotIn("twins_model_delivery", api)
        self.assertEqual(stage - api, {"cybersecurity_ui"})
        self.assertEqual(front - api, {"cybersecurity_ui"})
        with self.assertRaises(r.Refused):
            r.required_probe_checks({"component": "api"}, "staging", "unknown")

    def test_api_and_frontend_qualification_keep_their_actual_affected_scope(self):
        api = r.required_probe_checks({"component": "api"}, "staging", "twins")
        frontend = r.required_probe_checks(
            {"component": "frontend"}, "staging", "twins"
        )
        self.assertNotIn("twins_inspection", api)
        self.assertEqual(frontend - api, {"twins_inspection"})
        self.assertTrue(
            {
                "authentication",
                "owner_isolation",
                "database_persistence",
                "file_persistence",
                "twins_model_delivery",
            }
            <= api
        )
        foundation = r.required_probe_checks(
            {"component": "api"}, "staging", "foundation"
        )
        self.assertTrue({"twins_disabled", "ordinary_workflows"} <= foundation)
        self.assertNotIn("twins_model_delivery", foundation)
