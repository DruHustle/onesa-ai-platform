"""The CI producer cannot turn local checks into a hosted or deployment grant."""

import copy
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "release"))
from test_docs_scope import SHA, acceptance

spec = importlib.util.spec_from_file_location(
    "docs_build_evidence", Path(__file__).with_name("build_evidence.py")
)
producer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(producer)


class BuildEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.checks = {name: acceptance(name) for name in ["staging", "production"]}

    def test_actual_local_contexts_remain_local_and_use_real_actions_id(self):
        result = producer.record(SHA, 123, self.checks)
        self.assertEqual(result["actions_build_run_id"], 123)
        for key in [
            "hosted_qualification",
            "production_deployment_authorized",
            "application_deployment_authorized",
            "backend_deployment_authorized",
        ]:
            self.assertIs(result[key], False)

    def test_run_zero_failed_checks_wrong_source_context_or_missing_views_refuse(self):
        for run in [0, -1, True, "123"]:
            with self.subTest(run=run), self.assertRaises(producer.e.Rejected):
                producer.record(SHA, run, self.checks)
        for field, value in [
            ("result", "FAIL"),
            ("environment_context", "production"),
            ("provenance", {"revision": "f" * 40, "classification": "public"}),
            ("accessibility", ["PASS"] * 124),
        ]:
            checks = copy.deepcopy(self.checks)
            checks["staging"][field] = value
            with self.subTest(field=field), self.assertRaises(producer.e.Rejected):
                producer.record(SHA, 123, checks)

    def test_canonical_envelope_keeps_full_source_and_all_authority_false(self):
        source = {
            "schema_version": 2,
            "repository": "DruHustle/onesa-ug",
            "repository_id": 1444746154,
            "product": "platform",
            "source_path": "onesa-ai-platform",
            "candidate_commit": SHA,
            "source_tree": "b" * 40,
            "product_source_tree": "c" * 40,
            "branch": "main",
        }
        result = producer.record(SHA, 123, self.checks, source=source)
        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(result["source"], source)
        self.assertTrue(result["verification_only"])
        self.assertFalse(result["release_authorized"])
        self.assertFalse(result["hosted_qualification"])
        for key, value in (
            ("repository_id", True),
            ("product", "portal"),
            ("source_path", "../onesa-ai-platform"),
            ("branch", "dev"),
            ("candidate_commit", "d" * 40),
        ):
            changed = {**source, key: value}
            with self.subTest(key=key), self.assertRaises(producer.e.Rejected):
                producer.record(SHA, 123, self.checks, source=changed)

    def test_actual_git_checkout_identity_dirty_source_and_dispatch_refusals(self):
        with tempfile.TemporaryDirectory(prefix="docs-public-source-") as folder:
            root = Path(folder)

            def git(*parts):
                return subprocess.check_output(
                    [
                        "git",
                        "--no-replace-objects",
                        "--no-lazy-fetch",
                        "-C",
                        str(root),
                        *parts,
                    ],
                    stderr=subprocess.PIPE,
                    text=True,
                ).strip()

            git("init", "-b", "main")
            git("config", "user.name", "Synthetic fixture")
            git("config", "user.email", "fixture@example.test")
            git("remote", "add", "origin", "https://github.com/DruHustle/onesa-ug.git")
            product = root / "onesa-ai-platform"
            product.mkdir()
            (product / "public.txt").write_text("Synthetic public source only\n")
            git("add", "onesa-ai-platform/public.txt")
            git("commit", "-m", "Synthetic Docs source")
            sha = git("rev-parse", "HEAD")
            env = {
                "GITHUB_SHA": sha,
                "GITHUB_REPOSITORY": "DruHustle/onesa-ug",
                "GITHUB_REPOSITORY_ID": "1444746154",
                "GITHUB_EVENT_NAME": "workflow_dispatch",
                "GITHUB_REF": "refs/heads/main",
                "GITHUB_ACTOR": "DruHustle",
                "GITHUB_TRIGGERING_ACTOR": "DruHustle",
                "GITHUB_RUN_ATTEMPT": "1",
                "GITHUB_WORKFLOW_SHA": sha,
                "GITHUB_WORKFLOW_REF": "DruHustle/onesa-ug/"
                + producer.builds.CANONICAL_WORKFLOW
                + "@refs/heads/main",
            }
            source = producer.checkout_source(env, git)
            self.assertEqual(source["source_tree"], git("rev-parse", "HEAD^{tree}"))
            self.assertEqual(
                source["product_source_tree"],
                git("rev-parse", "HEAD:onesa-ai-platform"),
            )
            for key, value in (
                ("GITHUB_REPOSITORY_ID", "1"),
                ("GITHUB_EVENT_NAME", "pull_request"),
                ("GITHUB_REF", "refs/heads/dev"),
                ("GITHUB_ACTOR", "other"),
                ("GITHUB_TRIGGERING_ACTOR", "other"),
                ("GITHUB_RUN_ATTEMPT", "2"),
                ("GITHUB_WORKFLOW_SHA", "f" * 40),
                ("GITHUB_WORKFLOW_REF", "foreign/workflow"),
            ):
                with self.subTest(key=key), self.assertRaises(producer.e.Rejected):
                    producer.checkout_source({**env, key: value}, git)
            (product / "public.txt").write_text("Changed after checkout\n")
            with self.assertRaisesRegex(producer.e.Rejected, "Clean canonical"):
                producer.checkout_source(env, git)
            git("checkout", "--", "onesa-ai-platform/public.txt")
            self.assertEqual(git("status", "--porcelain"), "")
            git("remote", "set-url", "origin", "https://github.com/foreign/repo.git")
            with self.assertRaisesRegex(producer.e.Rejected, "Clean canonical"):
                producer.checkout_source(env, git)


if __name__ == "__main__":
    unittest.main()
