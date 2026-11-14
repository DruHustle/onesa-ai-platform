"""Real existing conditional verifier plus separate external-custody boundaries."""

import copy
import hashlib
import os
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import free_gate
import oracle_docs_internal_conditional as adapter
import oracle_owner as owner
import test_internal_docs_actions as actions
from test_evidence import SHA
from test_internal_docs_metadata import PRODUCER


class ExistingConditionalIntegrationTests(unittest.TestCase):
    def setUp(self):
        fixture = actions.InternalActionsTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.prepare()
        self.github = fixture.github
        self.store = SimpleNamespace(
            policy={"toolchain": {"native_producer_sha256": PRODUCER}}
        )
        self.binding = {"candidate_commit": SHA}
        self.enterContext(
            patch.object(adapter, "load", return_value=(free_gate, self.github))
        )

    def verify(self, metadata=None, run=40):
        return adapter.verify(
            self.store,
            self.binding,
            run,
            self.github.metadata if metadata is None else metadata,
        )

    def test_genuine_existing_actions_chain_remains_conditional_without_authority(self):
        value = self.verify()
        self.assertEqual(value["authorization_run_id"], 40)
        self.assertEqual(value["qualification_run_id"], 30)
        self.assertFalse(value["production_deployment_authorized"])
        self.assertEqual(value["metadata_sha256"], owner.digest(self.github.metadata))

    def test_changed_external_native_metadata_never_inherits_actions_authority(self):
        for field, value in [
            ("candidate_commit", "c" * 40),
            ("delivery_scope", "docs-public"),
            ("producer_sha256", "f" * 64),
            ("production_deployment_authorized", True),
        ]:
            altered = {**self.github.metadata, field: value}
            with self.subTest(field=field), self.assertRaises(owner.Rejected):
                self.verify(altered)
        altered = copy.deepcopy(self.github.metadata)
        altered["counts"]["verified_asset_responses"] += 1
        with self.assertRaises(owner.Rejected):
            self.verify(altered)

    def test_zero_wrong_run_forged_grant_revocation_expiry_and_skipped_ci_fail_closed(
        self,
    ):
        for run in [0, False, "40", 39]:
            with self.subTest(run=run), self.assertRaises(owner.Rejected):
                self.verify(run=run)
        for mutation in [
            lambda: self.github.approval.update(production_deployment_authorized=True),
            lambda: self.github.approval.update(decision="revoke"),
            lambda: self.github.approval.update(
                approved_at=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            ),
            lambda: self.github.ci_jobs[0].update(conclusion="skipped"),
        ]:
            approval = copy.deepcopy(self.github.approval)
            jobs = copy.deepcopy(self.github.ci_jobs)
            mutation()
            with self.assertRaises(owner.Rejected):
                self.verify()
            self.github.approval = approval
            self.github.ci_jobs = jobs


class ExternalCheckoutBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.root.chmod(0o700)
        self.enterContext(patch.object(adapter, "ROOT", self.root))
        source = Path(__file__).resolve().parents[2]
        checkout = self.root / "unmoved/onesa-ai-platform"
        checkout.mkdir(mode=0o700, parents=True)
        for name in adapter.FILES:
            path = checkout / name
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            path.write_bytes((source / name).read_bytes())
            path.chmod(0o600)
        subprocess.run(
            ["git", "init", "--quiet", str(checkout)], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "add", "."], cwd=checkout, check=True, capture_output=True
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Disposable fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "Synthetic conditional source fixture",
            ],
            cwd=checkout,
            check=True,
            capture_output=True,
        )
        sha = (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=checkout)
            .decode()
            .strip()
        )
        tree = (
            subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=checkout)
            .decode()
            .strip()
        )
        target = self.root / "checkouts" / sha / "onesa-ai-platform"
        target.parent.mkdir(mode=0o700, parents=True)
        checkout.rename(target)
        self.checkout = target
        self.binding = {
            "candidate_commit": sha,
            "source_tree": tree,
            "repository": "DruHustle/onesa-ai-platform",
        }
        self.store = SimpleNamespace(
            policy={
                "toolchain": {
                    "conditional_source_pins": {
                        name: hashlib.sha256((target / name).read_bytes()).hexdigest()
                        for name in adapter.FILES
                    }
                }
            }
        )
        private = owner.private
        self.enterContext(
            patch.object(
                adapter.owner,
                "private",
                side_effect=lambda path, **kw: private(path, uid=os.getuid(), **kw),
            )
        )

    def test_actual_clean_git_tree_and_closed_three_file_source_load(self):
        self.assertEqual(
            adapter.checked_checkout(self.store, self.binding), self.checkout
        )
        gate, github = adapter.load(self.store, self.binding)
        self.assertEqual(gate.e.ROOT, self.checkout)
        self.assertEqual(gate.e.REPOSITORY, self.binding["repository"])
        self.assertIsInstance(github, gate.e.GitHub)

    def test_dirty_changed_wrong_tree_and_expanded_source_are_refused(self):
        scratch = self.checkout / "unreviewed.py"
        scratch.write_text("raise RuntimeError('unreviewed fixture')")
        with self.assertRaises(owner.Rejected):
            adapter.checked_checkout(self.store, self.binding)
        scratch.unlink()
        with self.assertRaises(owner.Rejected):
            adapter.checked_checkout(
                self.store, {**self.binding, "source_tree": "0" * 40}
            )
        self.store.policy["toolchain"]["conditional_source_pins"]["unreviewed.py"] = (
            "0" * 64
        )
        with self.assertRaises(owner.Rejected):
            adapter.checked_checkout(self.store, self.binding)


if __name__ == "__main__":
    unittest.main()
