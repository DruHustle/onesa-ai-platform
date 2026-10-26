"""Prebuilt artifact and provider provenance; disposable files, no provider requests."""

import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import oracle_ai_frontend as f


class FrontendArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.provider = {"project_id": "prj_fixture", "team_id": "team_fixture"}
        self.files = {
            ".vercel/project.json": json.dumps(
                {"projectId": "prj_fixture", "orgId": "team_fixture"}
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
