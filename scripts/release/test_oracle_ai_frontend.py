"""Prebuilt artifact and provider provenance; disposable files, no provider requests."""

import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import oracle_ai_frontend as f

r = f.r


class FrontendArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.provider = {"project_id": "prj_fixture", "team_id": "team_fixture"}
        self.files = {
            ".vercel/project.json": json.dumps(
                {
                    "projectId": "prj_fixture",
                    "orgId": "team_fixture",
                    "projectName": "onesa-protocol-fixture",
                    "settings": {"rootDirectory": f.APP_ROOT},
                }
            ).encode(),
            "vercel.json": b'{"version":2}',
            ".vercel/output/functions/index.func/index.js": b"export default function(){}",
            ".vercel/output/static/a.js": b'console.log("synthetic")',
        }

    def artifact(self, *, links=None, extra=None, corrupt=None):
        links = links or {"functions/alias.func": "index.func"}
        receipt = {
            "files": {
                k[len(".vercel/output/") :]: hashlib.sha256(v).hexdigest()
                for k, v in self.files.items()
                if k.startswith(".vercel/output/")
            },
            "deployment_metadata_files": {
                k: hashlib.sha256(v).hexdigest()
                for k, v in self.files.items()
                if not k.startswith(".vercel/output/")
            },
            "links": links,
        }
        with tarfile.open(self.root / "prebuilt.tar", "w") as archive:
            for name, data in [*self.files.items(), *(extra or [])]:
                member = tarfile.TarInfo(name)
                body = b"changed" if name == corrupt else data
                member.size = len(body)
                archive.addfile(member, io.BytesIO(body))
            for name, target in links.items():
                member = tarfile.TarInfo(".vercel/output/" + name)
                member.type = tarfile.SYMTYPE
                member.linkname = target
                archive.addfile(member)
        (self.root / "receipt.json").write_text(json.dumps(receipt))
        return {"receipt": "receipt.json", "archive": "prebuilt.tar"}

    def unpack(self, build):
        destination = self.root / "unpacked"
        destination.mkdir(exist_ok=True)
        with (
            patch.object(f.r, "private", side_effect=lambda p, **kw: Path(p)),
            patch.object(
                f.r,
                "read",
                side_effect=lambda p: (
                    self.provider
                    if p == f.PROVIDER
                    else json.loads(Path(p).read_bytes())
                ),
            ),
        ):
            f.unpack(self.root, build, destination)
        return destination

    def test_function_alias_round_trip_and_deployment_metadata(self):
        output = self.unpack(self.artifact())
        alias = output / ".vercel/output/functions/alias.func"
        self.assertTrue(alias.is_symlink())
        self.assertEqual(
            (alias / "index.js").read_bytes(),
            self.files[".vercel/output/functions/index.func/index.js"],
        )
        self.assertTrue((output / f.APP_ROOT).is_dir())
        self.assertEqual(list((output / f.APP_ROOT).iterdir()), [])

    def test_unapproved_application_root_is_rejected(self):
        for root in ["../outside", "/outside", "other-product", None]:
            with self.subTest(root=root):
                project = json.loads(self.files[".vercel/project.json"])
                project["settings"]["rootDirectory"] = root
                self.files[".vercel/project.json"] = json.dumps(project).encode()
                with self.assertRaisesRegex(f.r.Refused, "APPLICATION_ROOT_SCOPE"):
                    self.unpack(self.artifact())
                shutil.rmtree(self.root / "unpacked")

    def test_modified_output_or_deployment_config_fails_before_extraction(self):
        for name in self.files:
            with self.subTest(name=name), self.assertRaises(f.r.Refused):
                self.unpack(self.artifact(corrupt=name))
            self.assertFalse((self.root / "unpacked" / ".vercel").exists())

    def test_escape_cycle_missing_target_and_duplicate_paths_fail_closed(self):
        cases = [
            {"links": {"functions/alias.func": "../../../escape.func"}},
            {"links": {"functions/a.func": "b.func", "functions/b.func": "a.func"}},
            {"links": {"functions/a.func": "missing.func"}},
            {"extra": [("vercel.json", b"{}")]},
            {"extra": [("../escape", b"x")]},
            {"extra": [(".vercel/output/functions/alias.func/injected.js", b"x")]},
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(f.r.Refused):
                self.unpack(self.artifact(**case))

    def test_wrong_project_is_refused(self):
        self.files[".vercel/project.json"] = (
            b'{"projectId":"prj_other","orgId":"team_fixture"}'
        )
        with self.assertRaisesRegex(f.r.Refused, "PROJECT_SCOPE"):
            self.unpack(self.artifact())

    def test_metadata_does_not_transfer_source_environment_or_project(self):
        binding = {"candidate_commit": "a" * 40}
        plan = {"project_id": "prj_fixture"}
        row = {
            "id": "dpl_fixture",
            "projectId": "prj_fixture",
            "meta": {"githubCommitSha": "a" * 40},
            "target": None,
        }
        with patch.object(f, "provider", return_value=row):
            self.assertEqual(
                f.check_deployment("dpl_fixture", binding, "staging", plan), row
            )
            for changed in [
                dict(row, projectId="prj_other"),
                dict(row, meta={"githubCommitSha": "b" * 40}),
                dict(row, target="production"),
            ]:
                with (
                    patch.object(f, "provider", return_value=changed),
                    self.assertRaises(f.r.Refused),
                ):
                    f.check_deployment("dpl_fixture", binding, "staging", plan)

    def test_multiple_provider_matches_require_inspection(self):
        with (
            patch.object(
                f,
                "provider",
                return_value={
                    "deployments": [
                        {"meta": {"onesaOracleOperation": "fixture"}},
                        {"meta": {"onesaOracleOperation": "fixture"}},
                    ]
                },
            ),
            self.assertRaisesRegex(f.r.Refused, "DUPLICATE_PROVIDER"),
        ):
            f.deployments_for("fixture", {"project_id": "prj_fixture"})


class IndependentPreviewTests(unittest.TestCase):
    def test_changed_frontend_uses_its_reserved_context_without_redeploying_api(self):
        api = {
            "candidate_commit": "a" * 40,
            "source_tree": "b" * 40,
            "source_sha256": "c" * 64,
        }
        frontend = {**api, "candidate_commit": "d" * 40}
        chain = [{"kind": "context", "id": "synthetic-context"}]
        folder = Path("/synthetic/frontend")
        plan = {"preview_receipt_path": "/synthetic/api-preview"}
        with patch.object(f, "create") as create:
            path = f.select_preview(frontend, api, chain, "staging", folder, plan)
            self.assertEqual(
                path,
                "/synthetic/frontend/operations/synthetic-context/provider-receipt.json",
            )
            create.assert_called_once_with(
                frontend, "staging", "synthetic-context", folder, plan
            )
        with patch.object(f, "create") as create:
            f.select_preview(frontend, api, chain, "operations", folder, plan)
            create.assert_not_called()
        with patch.object(f, "create") as create:
            plan = {"preview_receipt_path": "/synthetic/api-preview"}
            self.assertEqual(
                f.select_preview(api, api, chain, "staging", folder, plan),
                "/synthetic/api-preview",
            )
            create.assert_not_called()


def prepare_full_cli_fixture(destination):
    """Synthetic prebuilt data through the real unpacker; never release authority."""
    destination = Path(destination)
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    fixture = FrontendArtifactTests()
    fixture.setUp()
    try:
        for environment in ["staging", "production"]:
            fixture.files["vercel.json"] = b'{"framework":"nextjs","regions":["fra1"]}'
            fixture.files[".vercel/output/config.json"] = b'{"version":3}'
            fixture.files[".vercel/output/builds.json"] = json.dumps(
                {
                    "target": "preview" if environment == "staging" else "production",
                    "builds": [],
                }
            ).encode()
            fixture.files[".vercel/output/functions/index.func/.vc-config.json"] = (
                b'{"runtime":"nodejs24.x","handler":"index.js","launcherType":"Nodejs"}'
            )
            fixture.files[".vercel/output/static/owned.js"] = (
                b"// Synthetic loopback provider fixture only.\n" * 2048
            )
            output = fixture.unpack(fixture.artifact())
            shutil.copytree(output, destination / environment, symlinks=True)
            rejected = destination / "missing-root" / environment
            shutil.copytree(output, rejected, symlinks=True)
            shutil.rmtree(rejected / f.APP_ROOT)
            shutil.rmtree(output)
    finally:
        fixture.doCleanups()


class StaticAssetVerificationTests(unittest.TestCase):
    def setUp(self):
        self.body = b"synthetic compiled chunk"
        self.digest = hashlib.sha256(self.body).hexdigest()
        self.receipt = {"served_static_files": {}}
        patch.object(r, "read", return_value=self.receipt).start()
        self.plan = {"builds": {"production": {"receipt": "build.json"}}}
        self.reader = patch.object(f.urllib.request, "urlopen").start()
        self.reader.side_effect = lambda *args, **kwargs: io.BytesIO(self.body)
        self.addCleanup(patch.stopall)

    def verify(self, paths):
        self.receipt["served_static_files"] = {name: self.digest for name in paths}
        return f.verify_static(Path("/fixture"), self.plan, {})

    def test_generated_catch_all_chunks_are_requested_and_hashed(self):
        self.verify(
            [
                "/_next/static/chunks/app/api/[...path]/route-fixture.js",
                "/_next/static/chunks/app/[[...slug]]/page-fixture.js",
            ]
        )
        urls = [
            getattr(call.args[0], "full_url", call.args[0])
            for call in self.reader.call_args_list
        ]
        self.assertEqual(
            urls,
            [
                "https://platform.onesa.eu"
                + "/_next/static/chunks/app/api/%5B...path%5D/route-fixture.js",
                "https://platform.onesa.eu"
                + "/_next/static/chunks/app/%5B%5B...slug%5D%5D/page-fixture.js",
            ],
        )
        self.assertEqual(self.reader.call_count, 2)

    def test_traversal_and_url_controls_fail_before_any_asset_request(self):
        for name in [
            "/_next/static/../secret.js",
            "/_next/static/./a.js",
            "/_next/static//a.js",
            "//foreign.invalid/a.js",
            "https://foreign.invalid/a.js",
            "/_next/static/%2e%2e/a.js",
            "/_next/static/%252e%252e/a.js",
            "/_next/static/a.js?token=fixture",
            "/_next/static/a.js#fragment",
            "/_next/static/\\secret.js",
            "/_next/static/a\x00.js",
            "/_next/static/a\n.js",
        ]:
            with self.subTest(path=name), self.assertRaises(r.Refused):
                self.verify(["/_next/static/valid.js", name])
            self.reader.assert_not_called()

    def test_changed_and_oversized_served_bodies_remain_unqualified(self):
        for body in [b"modified chunk", b"x" * (8388608 + 1)]:
            self.body = body
            with self.subTest(bytes=len(body)), self.assertRaises(r.Refused):
                self.verify(["/_next/static/chunks/app/[...path]/route-fixture.js"])


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--prepare-cli-fixture":
        prepare_full_cli_fixture(sys.argv[2])
    else:
        unittest.main()


class ProviderRoutingTests(unittest.TestCase):
    def setUp(self):
        self.project = {
            "id": "prj_fixture",
            "rootDirectory": f.APP_ROOT,
            "framework": "nextjs",
            "nodeVersion": "24.x",
            "serverlessFunctionRegion": "fra1",
            "ssoProtection": {"deploymentType": "all"},
            "protectionBypass": {},
            "passwordProtection": None,
            "trustedIps": None,
        }
        fields = {
            k: self.project[k]
            for k in [
                "ssoProtection",
                "protectionBypass",
                "passwordProtection",
                "trustedIps",
            ]
        }
        self.plan = {
            "project_id": self.project["id"],
            "serverless_function_region": "fra1",
            "vercel_protection_sha256": hashlib.sha256(
                json.dumps(fields, sort_keys=True).encode()
            ).hexdigest(),
            "vercel_api_url_variable_ids": {
                "staging": "fixture_stage",
                "production": "fixture_production",
            },
            "api_origins": {
                "staging": "https://platform-api-staging.onesa.eu",
                "production": "https://platform-api.onesa.eu",
            },
        }
        self.variables = {
            self.plan["vercel_api_url_variable_ids"][env]: {
                "id": self.plan["vercel_api_url_variable_ids"][env],
                "key": "ONESA_API_URL",
                "value": self.plan["api_origins"][env],
                "target": ["preview" if env == "staging" else "production"],
                "gitBranch": None,
            }
            for env in ["staging", "production"]
        }
        self.calls = []

    def provider(self, path, *, data=None):
        self.calls.append((path, data))
        self.assertIsNone(data)
        if path.startswith("/v9/projects/"):
            return self.project
        self.assertTrue(path.startswith("/v1/projects/prj_fixture/env/"))
        return self.variables[path.rsplit("/", 1)[1]]

    def call(self):
        with (
            patch.object(r, "read", return_value={"project_id": "prj_fixture"}),
            patch.object(f, "provider", side_effect=self.provider),
        ):
            return f.protection(self.plan)

    def test_only_two_explicit_nonsecret_routing_variables_are_read(self):
        self.assertEqual(self.call(), self.project)
        self.assertEqual(len(self.calls), 3)
        self.assertTrue(
            all("/env" not in path or "/env/" in path for path, _ in self.calls)
        )

    def test_wrong_origin_target_branch_or_project_fails_before_deploy(self):
        row = self.variables["fixture_stage"]
        for key, value in [
            ("value", "https://foreign.invalid"),
            ("key", "UNRELATED_SECRET"),
            ("target", ["production"]),
            ("gitBranch", "foreign"),
            ("id", "foreign_id"),
        ]:
            old = row[key]
            row[key] = value
            with self.subTest(key=key), self.assertRaises(r.Refused):
                self.call()
            row[key] = old


class ExplicitDeploymentRoutingTests(unittest.TestCase):
    def test_ambiguous_cli_acknowledgement_never_allows_duplicate_create(self):
        from uuid import uuid4

        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            binding = {
                "repository": "DruHustle/onesa-ai-platform",
                "candidate_commit": "a" * 40,
            }
            plan = {
                "project_id": "prj_fixture",
                "serverless_function_region": "fra1",
                "builds": {"production": {"archive_sha256": "b" * 64}},
                "api_origins": {"production": "https://platform-api.onesa.eu"},
                "cli_image": "sha256:" + "c" * 64,
            }
            operation = str(uuid4())
            calls = []

            def provider(*args, **kwargs):
                calls.append(args)
                raise subprocess.TimeoutExpired("synthetic-cli", 1)

            with (
                patch.object(r, "private", side_effect=lambda p, **kw: Path(p)),
                patch.object(f, "unpack"),
                patch.object(f, "protection", return_value={"id": "prj_fixture"}),
                patch.object(f, "deployments_for", return_value=[]),
                patch.object(
                    r,
                    "trusted_toolchain",
                    return_value={
                        "transport_guard_sha256": r.sha(
                            Path(f.__file__).with_name(
                                "oracle_vercel_transport_guard.cjs"
                            )
                        )
                    },
                ),
                patch.object(f.subprocess, "run", side_effect=provider),
                patch.object(f.time, "monotonic", side_effect=[0, 121]),
            ):
                with self.assertRaisesRegex(r.Refused, "UNCERTAIN"):
                    f.create(binding, "production", operation, folder, plan)
                with self.assertRaises(FileExistsError):
                    f.create(binding, "production", operation, folder, plan)
            self.assertEqual(len(calls), 1)
            command = calls[0][0]
            self.assertEqual(
                command[command.index("--env") + 1],
                "ONESA_API_URL=https://platform-api.onesa.eu",
            )
            self.assertTrue(
                (folder / "operations" / operation / "intent.json").exists()
            )
            self.assertTrue((folder / "operations" / operation / "cli.stderr").exists())
