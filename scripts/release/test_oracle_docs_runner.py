"""Disposable provider/CLI boundary tests; none are hosted qualification."""

import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import oracle_docs_runner as docs
import oracle_owner as owner
import test_docs_scope as scope_fixtures


class DriverTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.root.chmod(0o700)
        self.binding = {
            "repository": "DruHustle/onesa-ai-platform",
            "component": "docs-public",
            "candidate_commit": "a" * 40,
            "source_tree": "b" * 40,
        }
        self.operation = {
            "id": str(uuid.uuid4()),
            "binding": self.binding,
            "parent": str(uuid.uuid4()),
        }
        self.spec = {
            "environment": "staging",
            "source": self.binding,
            "project_id": "prj_fixture",
            "team_id": "team_fixture",
            "cli_image": "sha256:" + "c" * 64,
            "transport_guard_sha256": owner.file_digest(
                Path(docs.__file__).with_name("oracle_vercel_transport_guard.cjs")
            ),
            "artifact": {"file_manifest_sha256": "d" * 64},
        }
        self.store = SimpleNamespace(
            root=self.root,
            github=None,
            get=lambda *_a, **_k: {"record": self.operation},
        )
        guard = Path(docs.__file__).with_name("oracle_vercel_transport_guard.cjs")
        installed_guard = self.root / guard.name
        installed_guard.write_bytes(guard.read_bytes())
        installed_guard.chmod(0o600)
        self.enterContext(
            patch.object(docs, "__file__", str(self.root / "oracle_docs_runner.py"))
        )
        custody = owner.private
        self.enterContext(
            patch.object(
                owner,
                "private",
                lambda p, **kw: custody(p, **{**kw, "uid": os.getuid()}),
            )
        )
        self.enterContext(patch.object(docs, "ROOT", self.root))
        self.enterContext(patch.object(docs, "scoped"))
        self.enterContext(
            patch.object(docs, "publication_spec", lambda *_a, **_k: self.spec)
        )
        self.enterContext(patch.object(docs, "cli_authentication"))
        self.enterContext(patch.object(docs, "unpack_static"))
        self.matches = self.enterContext(
            patch.object(docs, "operation_matches", return_value=[])
        )
        self.observation = {"deployment_id": "dpl_fixture", "state": "READY"}
        self.enterContext(
            patch.object(docs, "deployment_for", return_value=self.observation)
        )
        self.commands = []
        self.real_run = subprocess.run

    def cli(self, command, **_kwargs):
        self.commands.append(command)
        folder = docs.operation_folder(self.binding, self.operation["id"])
        intent = json.loads((folder / "intent.json").read_bytes())
        self.assertEqual(intent["provider_create_budget"], 1)
        self.assertFalse(intent["automatic_retry"])
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node is mandatory for the actual transport fixture")
        guard = Path(docs.__file__).with_name("oracle_vercel_transport_guard.cjs")
        # Invoke the real guard; no provider request or production credential exists.
        code = "require(process.argv[1]).createGuard(process.argv[2])('https://api.vercel.com','POST','/v13/deployments')"
        self.real_run(
            [node, "-e", code, str(guard), str(folder / "transport")],
            check=True,
            capture_output=True,
        )
        self.matches.return_value = [{"uid": "dpl_fixture"}]
        return SimpleNamespace(returncode=0)

    def test_preview_uses_existing_isolated_cli_with_explicit_preview_target(self):
        with patch.object(subprocess, "run", side_effect=self.cli):
            self.assertEqual(
                docs.create_publication(self.store, self.operation, production=False),
                self.observation,
            )
            with self.assertRaises(owner.Rejected):
                docs.create_publication(self.store, self.operation, production=False)
        self.assertEqual(len(self.commands), 1)
        args = self.commands[0]
        for arg in [
            "--target=preview",
            "--prebuilt",
            "--read-only",
            "--pull=never",
            "--no-wait",
            "no-new-privileges:true",
        ]:
            self.assertIn(arg, args)
        self.assertNotIn("--prod", args)
        self.assertNotIn("--token", args)
        self.assertIn("onesa-docs-publication-" + self.operation["id"], args)
        folder = docs.operation_folder(self.binding, self.operation["id"])
        self.assertEqual(
            json.loads((folder / "provider-receipt-immediate.json").read_bytes()),
            self.observation,
        )
        self.assertTrue((folder / "provider-receipt-ready.json").is_file())

    def test_interrupted_cli_acknowledgement_preserves_guard_and_refuses_replay(self):
        def interrupted(command, **kwargs):
            self.cli(command, **kwargs)
            self.matches.return_value = []
            raise subprocess.TimeoutExpired(command, 600)

        with (
            patch.object(subprocess, "run", side_effect=interrupted),
            patch.object(docs.time, "monotonic", side_effect=[0, 121]),
            self.assertRaises(owner.Rejected),
        ):
            docs.create_publication(self.store, self.operation, production=False)
        folder = docs.operation_folder(self.binding, self.operation["id"])
        self.assertTrue((folder / "intent.json").is_file())
        self.assertTrue((folder / "transport/create-request.json").is_file())
        self.assertIsNone(
            json.loads((folder / "cli-result.json").read_bytes())["exit_code"]
        )
        with patch.object(subprocess, "run") as duplicate:
            with self.assertRaises(owner.Rejected):
                docs.create_publication(self.store, self.operation, production=False)
            duplicate.assert_not_called()

    def retained(self):
        spec = {**self.spec, "environment": "production"}
        folder = docs.operation_folder(self.binding, self.operation["id"])
        folder.mkdir(mode=0o700, parents=True)
        docs.durable(
            folder / "intent.json",
            owner.canonical(
                {
                    "binding": self.binding,
                    "operation_id": self.operation["id"],
                    "prepared": spec,
                    "provider_create_budget": 1,
                    "automatic_retry": False,
                }
            ),
        )
        self.matches.return_value = [{"uid": "dpl_prior"}]
        return {
            "id": "dpl_prior",
            "projectId": "prj_fixture",
            "target": "production",
            "readyState": "READY",
            "meta": {
                "onesaOracleOperation": self.operation["id"],
                "onesaSourceRevision": self.binding["candidate_commit"],
                "onesaArtifactManifest": "d" * 64,
            },
        }

    def test_prior_terminal_publication_is_read_only_and_never_acceptance(self):
        row = self.retained()
        with (
            patch.object(docs, "target", return_value=("prj_fixture", "team_fixture")),
            patch.object(docs, "provider_get", return_value=row),
            patch.object(subprocess, "run") as process,
        ):
            results = docs.inspect_retained_publications(self.store)
            self.assertEqual(results[0]["deployment_id"], "dpl_prior")
            self.assertEqual(results[0]["provider_writes"], 0)
            self.assertFalse(results[0]["production_acceptance_claimed"])
            self.assertEqual(docs.inspect_retained_publications(self.store), results)
            process.assert_not_called()

    def test_changed_source_or_artifact_or_target_or_nonterminal_prior_request_fails(
        self,
    ):
        row = self.retained()
        variants = []
        for key, value in [
            ("projectId", "prj_foreign"),
            ("target", None),
            ("readyState", "BUILDING"),
            ("id", "dpl_other"),
        ]:
            variants.append({**row, key: value})
        for key in [
            "onesaSourceRevision",
            "onesaArtifactManifest",
            "onesaOracleOperation",
        ]:
            variant = copy.deepcopy(row)
            variant["meta"][key] = "changed"
            variants.append(variant)
        for variant in variants:
            with (
                self.subTest(variant=variant),
                patch.object(
                    docs, "target", return_value=("prj_fixture", "team_fixture")
                ),
                patch.object(docs, "provider_get", return_value=variant),
                self.assertRaises(owner.Rejected),
            ):
                docs.inspect_retained_publications(self.store)

    def test_new_source_cannot_hide_an_unacknowledged_production_request(self):
        self.retained()
        self.matches.return_value = []
        with (
            patch.object(docs, "target", return_value=("prj_fixture", "team_fixture")),
            patch.object(subprocess, "run") as process,
        ):
            with self.assertRaises(owner.Rejected):
                docs.create_publication(
                    self.store,
                    {**self.operation, "id": str(uuid.uuid4())},
                    production=True,
                )
            process.assert_not_called()

    def native_payload(self):
        observed = {
            "deployment_id": "dpl_fixture",
            "state": "READY",
            "origin": docs.ORIGIN,
            "artifact_manifest_sha256": "d" * 64,
            "asset_count": 279,
            "source_revision": self.binding["candidate_commit"],
        }
        challenge = {
            "binding": self.binding,
            "details": {
                "environment": "production",
                "operation_id": self.operation["id"],
                "provider": observed,
            },
        }
        accepted = scope_fixtures.acceptance("production")
        accepted.update(
            origin=docs.ORIGIN,
            provenance={
                "revision": self.binding["candidate_commit"],
                "classification": "public",
            },
        )
        evidence = {
            "kind": "owner-native-public-docs-observation",
            "provider": observed,
            "asset_manifest_sha256": "d" * 64,
            "asset_count": 279,
            "acceptance": accepted,
            "source_revision": self.binding["candidate_commit"],
            "observation_mode": "existing-owner-browser-no-profile-export",
            "browser": {
                "product": "Chrome/145.0.1.0",
                "reported_headless": False,
                "connection": "existing-owner-native-cdp",
            },
        }
        checkout = Path(scope_fixtures.e.ROOT)
        contract = {
            "registry": json.loads(
                (
                    checkout
                    / "onesa-ai-platform-frontend/packages/onesa-design/onesa-applications.json"
                ).read_bytes()
            ),
            "icons": json.loads(
                (
                    checkout
                    / "onesa-ai-platform-frontend/apps/docs/static/brand/icons/v1/sources.json"
                ).read_bytes()
            ),
        }
        self.enterContext(
            patch.object(
                docs, "prepare", return_value={"local_acceptance": {"artifact_id": 302}}
            )
        )
        self.enterContext(
            patch.object(docs, "inspect_production", return_value=observed)
        )
        self.enterContext(
            patch.object(docs.builds, "source_contract", return_value=contract)
        )
        return challenge, {"evidence": evidence}

    def test_native_contract_requires_the_actual_complete_typed_workflow_matrix(self):
        challenge, payload = self.native_payload()
        docs.validate_native(self.store, challenge, payload)
        variants = []
        for modify in [
            lambda e: e.update(source_revision="f" * 40),
            lambda e: e.update(asset_manifest_sha256="f" * 64),
            lambda e: e.update(asset_count=278),
            lambda e: e["acceptance"].update(environment_context="staging"),
            lambda e: e["acceptance"].update(result="SKIPPED"),
            lambda e: e["acceptance"]["accessibility"].pop(),
            lambda e: e["acceptance"]["accessibility"][0].update(
                violations=[{"impact": "serious"}]
            ),
            lambda e: e["acceptance"]["widths"][0].update(overflow=True),
            lambda e: e["acceptance"]["icons"].pop(),
            lambda e: e["browser"].update(reported_headless=True),
            lambda e: e["browser"].update(connection="headless-fixture"),
        ]:
            variant = copy.deepcopy(payload)
            modify(variant["evidence"])
            variants.append(variant)
        for index, variant in enumerate(variants):
            with self.subTest(index=index), self.assertRaises(owner.Rejected):
                docs.validate_native(self.store, challenge, variant)


if __name__ == "__main__":
    unittest.main()
