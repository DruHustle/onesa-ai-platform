"""No network: local Oracle evidence cannot masquerade as Actions or production."""

import copy
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import oracle_context as oracle

ROOT = Path(__file__).resolve().parents[2]


class OracleContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.root.chmod(0o700)
        self.path = self.root / "context.json"
        self.fixtures = self.root / "fixtures.json"
        self.value = {
            "execution_context": "owner-operated-oracle-staging",
            "repository": "DruHustle/onesa-ai-platform",
            "candidate_commit": "a" * 40,
            "ci_run_id": 123,
            "project_id": "prj_synthetic",
            "qualification_id": "11111111-2222-4333-8444-555555555555",
            "frontend_origin": "https://onesa-ai-platform-synthetic.vercel.app",
            "fixture_file": str(self.fixtures),
            "output_dir": str(self.root),
        }
        self.fixture = {
            "scope": "approved-synthetic-staging",
            "project_id": "prj_synthetic",
            "candidate_commit": "a" * 40,
            "run_id": "123",
            "users": [
                {"id": str(i), "email": f"release-audit-123-{str(i) * 24}@example.com"}
                for i in [1, 2]
            ],
        }
        self.write()

    def write(self):
        for path, value in [(self.path, self.value), (self.fixtures, self.fixture)]:
            path.write_text(json.dumps(value))
            path.chmod(0o600)

    def javascript_accepts(self):
        result = subprocess.run(
            [
                "node",
                "-e",
                (
                    "try {require('./scripts/oracle_context.cjs').loadContext(process.argv[1]);}"
                    "catch {process.exit(1)}"
                ),
                str(self.path),
            ],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        return result.returncode == 0

    def rejected(self):
        with self.assertRaises((ValueError, KeyError, TypeError)):
            oracle.load_context(self.path)
        self.assertFalse(self.javascript_accepts())

    def test_owner_context_is_explicit_and_not_a_github_execution_or_grant(self):
        with patch.dict(os.environ, {}, clear=True):
            value = oracle.load_context(self.path)
            identity = oracle.record_identity(value)
        self.assertEqual(identity["workflow_run_id"], 0)
        self.assertEqual(identity["ci_run_id"], 123)
        self.assertNotIn("status", identity)
        self.assertNotIn("authorized", identity)
        self.assertTrue(self.javascript_accepts())

    def test_production_and_foreign_origins_are_rejected_by_both_harnesses(self):
        for origin in [
            "https://platform.onesa.eu",
            "http://localhost:3100",
            "https://robot.onesa.eu",
            "https://onesa-ai-platform-example.vercel.app.evil.example",
        ]:
            with self.subTest(origin=origin):
                self.value["frontend_origin"] = origin
                self.write()
                self.rejected()

    def test_wrong_source_project_scope_run_and_user_are_rejected(self):
        for key, value in [
            ("candidate_commit", "b" * 40),
            ("project_id", "prj_foreign"),
            ("scope", "approved-synthetic-production"),
            ("run_id", "456"),
        ]:
            with self.subTest(key=key):
                original = self.fixture[key]
                self.fixture[key] = value
                self.write()
                self.rejected()
                self.fixture[key] = original
        self.fixture["users"][0]["email"] = "owner@example.com"
        self.write()
        self.rejected()

    def test_context_and_fixture_must_be_private_regular_files(self):
        for path in [self.path, self.fixtures]:
            path.chmod(0o644)
            self.rejected()
            path.chmod(0o600)
        saved = self.path.with_suffix(".saved")
        self.path.rename(saved)
        self.path.symlink_to(saved)
        self.rejected()

    def test_context_cannot_claim_production_or_actions_execution(self):
        for key, value in [
            ("execution_context", "github-hosted"),
            ("repository", "DruHustle/onesa-ai-robot"),
            ("candidate_commit", "main"),
            ("ci_run_id", 0),
            ("qualification_id", "invalid"),
        ]:
            with self.subTest(key=key):
                original = self.value[key]
                self.value[key] = value
                self.write()
                self.rejected()
                self.value[key] = original

    def test_nonprivate_output_is_rejected(self):
        self.root.chmod(0o755)
        self.rejected()

    def test_suite_rejects_wrong_origin_before_any_http_call(self):
        import hosted_suite

        with patch.object(hosted_suite, "Session") as session:
            with self.assertRaises(ValueError):
                hosted_suite.run_suite(
                    "https://platform.onesa.eu", oracle_context=self.path
                )
            session.assert_not_called()

    def canonical_context(self):
        self.value["repository"] = "DruHustle/onesa-ug"
        self.value["source_binding"] = {
            "schema_version": 2,
            "repository": self.value["repository"],
            "repository_id": 1444746154,
            "product": "platform",
            "source_path": "onesa-ai-platform",
            "branch": "main",
            "candidate_commit": self.value["candidate_commit"],
            "source_tree": "b" * 40,
            "product_source_tree": "c" * 40,
        }
        self.write()

    def test_canonical_owner_receipt_preserves_root_and_product_without_authority(self):
        self.canonical_context()
        identity = oracle.record_identity(oracle.load_context(self.path))
        self.assertEqual(identity["repository"], self.value["repository"])
        self.assertEqual(identity["source_binding"], self.value["source_binding"])
        self.assertNotEqual(
            identity["source_binding"]["source_tree"],
            identity["source_binding"]["product_source_tree"],
        )
        self.assertEqual(identity["workflow_run_id"], 0)
        self.assertNotIn("authorized", identity)
        self.assertTrue(self.javascript_accepts())

    def test_both_context_readers_refuse_incomplete_foreign_and_mismatched_canonical_source(
        self,
    ):
        self.canonical_context()
        source = copy.deepcopy(self.value["source_binding"])
        for key in source:
            self.value["source_binding"] = {k: v for k, v in source.items() if k != key}
            self.write()
            with self.subTest(missing=key):
                self.rejected()
        for key, value in [
            ("schema_version", True),
            ("repository", "DruHustle/onesa-ai-platform"),
            ("repository_id", True),
            ("product", "portal"),
            ("source_path", "../onesa-ai-platform"),
            ("branch", "staging"),
            ("candidate_commit", "d" * 40),
            ("source_tree", "main"),
            ("product_source_tree", "c" * 39),
            ("release_authorized", True),
        ]:
            self.value["source_binding"] = {**source, key: value}
            self.write()
            with self.subTest(changed=key):
                self.rejected()

    def test_canonical_context_keeps_fixture_origin_and_private_file_guards(self):
        self.canonical_context()
        self.fixture["candidate_commit"] = "d" * 40
        self.write()
        self.rejected()
        self.fixture["candidate_commit"] = self.value["candidate_commit"]
        self.write()
        self.path.chmod(0o644)
        self.rejected()
        self.path.chmod(0o600)
        self.value["frontend_origin"] = "https://platform.onesa.eu"
        self.write()
        self.rejected()


if __name__ == "__main__":
    unittest.main()
