"""Conditional owner custody never substitutes for actual private hosted checks."""

import copy
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import evidence as e
import free_gate as f
from test_evidence import FINGERPRINT, SHA
from test_internal_docs_metadata import PRODUCER, DraftGitHub


class InternalDocsConditionalTests(unittest.TestCase):
    def setUp(self):
        self.github = DraftGitHub()
        self.patches = [
            patch.object(e, "source_hash", return_value=FINGERPRINT),
            patch.object(f, "_internal_docs_local_source", return_value=FINGERPRINT),
            patch.object(
                f,
                "_internal_docs_asset_bytes",
                side_effect=lambda _id: self.github.content,
            ),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def qualify(self):
        return f.qualification(
            self.github,
            SHA,
            self.github.run(30),
            None,
            "docs-internal",
            metadata_custody={
                "release_id": 100,
                "asset_id": 200,
                "asset_digest": self.github.asset["digest"],
                "producer_sha256": PRODUCER,
            },
        )

    def prepare(self):
        self.github.record = self.qualify()
        self.github.approval = f.authorize(
            self.github,
            SHA,
            self.github.run(40),
            30,
            e.digest(self.github.record),
            None,
            "approve",
            "docs-internal",
        )

    def verify(self, pin=PRODUCER):
        return f.verify(
            self.github,
            SHA,
            40,
            "docs-internal",
            expected_producer_sha256=pin,
        )

    def test_owner_custody_is_conditional_with_no_hosted_or_production_pass(self):
        self.prepare()
        result = self.verify()
        self.assertEqual(result["status"], "CONDITIONAL_EXTERNAL_HANDOFF")
        self.assertEqual(
            result["conditional_authority"], "REQUIRES_EXTERNAL_LIVE_VALIDATION"
        )
        self.assertFalse(result["deployment_triggered"])
        for record in [
            self.github.record,
            self.github.approval,
            result,
            result["staging"],
        ]:
            self.assertEqual(record["STAGING_VERIFIED"], "BLOCKED")
            for key in [
                "production_deployment_authorized",
                "application_deployment_authorized",
                "backend_deployment_authorized",
            ]:
                self.assertIs(record[key], False)
        self.assertEqual(result["staging"]["metadata"], self.github.metadata)
        self.assertEqual(result["staging"]["custody"]["asset_id"], 200)
        self.assertEqual(result["qualification_artifact"]["run_id"], 30)
        self.assertEqual(result["artifact"]["run_id"], 40)

    def test_full_and_public_consumers_refuse_conditional_approval(self):
        self.prepare()
        for scope in ["full", "docs-public"]:
            with self.subTest(scope=scope), self.assertRaises(e.Rejected):
                f.verify(self.github, SHA, 40, scope)
        with self.assertRaises(e.Rejected):
            f.verify(self.github, SHA, 40)

    def test_external_pin_is_required_and_cannot_be_selected_by_metadata(self):
        self.prepare()
        for pin in [None, "", "PASS", "c" * 64, True]:
            with self.subTest(pin=pin), self.assertRaises(e.Rejected):
                self.verify(pin)
        with self.assertRaises(e.Rejected):
            f.verify(self.github, SHA, 40, "docs-internal")

    def test_legacy_docs_pass_and_unscoped_caller_json_cannot_qualify_internal(self):
        for custody in [
            None,
            {"status": "PASS"},
            {
                "release_id": {"status": "PASS"},
                "asset_id": 200,
                "asset_digest": self.github.asset["digest"],
                "producer_sha256": PRODUCER,
            },
        ]:
            with self.subTest(custody=custody), self.assertRaises(e.Rejected):
                f.qualification(
                    self.github,
                    SHA,
                    self.github.run(30),
                    20,
                    "docs-internal",
                    metadata_custody=custody,
                )
        with self.assertRaises(e.Rejected):
            f.docs_qualification(self.github, SHA, 20, "docs-internal")

    def test_qualification_and_authorization_grants_or_pass_cannot_be_substituted(self):
        for target in ["record", "approval"]:
            for key, value in [
                ("STAGING_VERIFIED", "PASS"),
                ("conditional_authority", "AUTHORIZED"),
                ("production_deployment_authorized", True),
                ("application_deployment_authorized", True),
                ("backend_deployment_authorized", True),
            ]:
                self.prepare()
                getattr(self.github, target)[key] = value
                with (
                    self.subTest(target=target, key=key),
                    self.assertRaises(e.Rejected),
                ):
                    self.verify()

    def test_current_main_ci_source_and_owner_dispatch_are_mandatory(self):
        self.prepare()
        self.github.main_sha = "c" * 40
        with self.assertRaises(e.Rejected):
            self.verify()
        self.github.main_sha = SHA
        self.github.ci_jobs[0]["conclusion"] = "failure"
        with self.assertRaises(e.Rejected):
            self.verify()
        self.github.ci_jobs[0]["conclusion"] = "success"
        for field, value in [
            ("actor", {"login": "foreign"}),
            ("triggering_actor", {"login": "foreign"}),
            ("event", "workflow_run"),
            ("run_attempt", 2),
            ("head_branch", "staging"),
        ]:
            run = copy.deepcopy(self.github.run(30))
            run[field] = value
            with self.subTest(field=field), self.assertRaises(e.Rejected):
                f.qualification(
                    self.github,
                    SHA,
                    run,
                    None,
                    "docs-internal",
                    metadata_custody={
                        "release_id": 100,
                        "asset_id": 200,
                        "asset_digest": self.github.asset["digest"],
                        "producer_sha256": PRODUCER,
                    },
                )

    def test_current_draft_asset_metadata_and_producer_custody_are_revalidated(self):
        for change in [
            lambda g: g.release.update(draft=False),
            lambda g: g.asset.update(uploader={"login": "foreign"}),
            lambda g: g.asset.update(digest="sha256:" + "c" * 64),
            lambda g: g.metadata["staging"].update(
                origin="https://87654321.onesa-engineering-docs.pages.dev"
            ),
        ]:
            self.github = DraftGitHub()
            self.prepare()
            change(self.github)
            if self.github.metadata["staging"]["origin"].startswith("https://876"):
                self.github.refresh()
            with self.assertRaises(e.Rejected):
                self.verify()

    def test_unavailable_draft_read_fails_closed_without_permissions_fallback(self):
        actual = self.github.api

        def denied(path, pages=False):
            if "/releases/" in path:
                raise e.Rejected("Draft is unavailable to configured read-only token")
            return actual(path, pages)

        with (
            patch.object(self.github, "api", side_effect=denied),
            self.assertRaises(e.Rejected),
        ):
            self.qualify()

    def test_latest_revocation_pending_failure_and_expiry_block_old_authority(self):
        self.prepare()
        revoked = f.authorize(
            self.github,
            SHA,
            self.github.run(40),
            None,
            None,
            None,
            "revoke",
            "docs-internal",
        )
        self.assertIs(revoked["production_deployment_authorized"], False)
        self.github.approval = revoked
        with self.assertRaises(e.Rejected):
            self.verify()
        for status, conclusion in [("in_progress", None), ("completed", "failure")]:
            self.prepare()
            self.github.runs_by_id[41] = {
                **self.github.run(40),
                "id": 41,
                "status": status,
                "conclusion": conclusion,
            }
            self.github.latest = 41
            with self.assertRaises(e.Rejected):
                self.verify()
            self.github.latest = 40
        self.prepare()
        self.github.approval["approved_at"] = (
            datetime.now(timezone.utc) - timedelta(days=2)
        ).isoformat()
        with self.assertRaises(e.Rejected):
            self.verify()

    def test_owner_revocation_or_artifact_change_during_verify_is_rejected(self):
        self.prepare()
        actual = self.github.runs
        calls = 0

        def moved(workflow, sha):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.github.latest = 41
                self.github.runs_by_id[41] = {**self.github.run(40), "id": 41}
            return actual(workflow, sha)

        with (
            patch.object(self.github, "runs", side_effect=moved),
            self.assertRaises(e.Rejected),
        ):
            self.verify()
        self.github.latest = 40
        self.prepare()
        artifact = self.github.artifact
        authorization_reads = 0

        def replaced(run, name):
            nonlocal authorization_reads
            record, origin = artifact(run, name)
            if name == "free-production-authorization":
                authorization_reads += 1
                if authorization_reads == 2:
                    record["production_deployment_authorized"] = True
            return record, origin

        with (
            patch.object(self.github, "artifact", side_effect=replaced),
            self.assertRaisesRegex(e.Rejected, "artifact changed"),
        ):
            self.verify()
        self.assertEqual(authorization_reads, 2)

    def test_production_issue_claims_cannot_replace_conditional_owner_dispatch(self):
        self.github.record = self.qualify()
        with self.assertRaises(e.Rejected):
            f.authorize(
                self.github,
                SHA,
                self.github.run(40),
                30,
                e.digest(self.github.record),
                2,
                "approve",
                "docs-internal",
            )

    def test_cli_requires_explicit_ids_and_pin_not_ambient_scope_or_pin(self):
        self.prepare()
        with (
            patch.dict(
                os.environ,
                {
                    "DELIVERY_SCOPE": "docs-internal",
                    "METADATA_PRODUCER_SHA256": PRODUCER,
                    "GITHUB_ACTIONS": "",
                },
            ),
            patch.object(
                sys,
                "argv",
                [
                    "free_gate",
                    "verify",
                    "--sha",
                    SHA,
                    "--authorization-run",
                    "40",
                    "--delivery-scope",
                    "docs-internal",
                    "--output",
                    "/synthetic/record.json",
                ],
            ),
            patch.object(f.e, "GitHub", return_value=self.github),
            patch.object(
                f.subprocess,
                "check_output",
                side_effect=[SHA + "\n", "", json.dumps({"login": e.OWNER})],
            ),
            self.assertRaisesRegex(e.Rejected, "Independently held"),
        ):
            f.main()
        with (
            patch.dict(
                os.environ, {"DELIVERY_SCOPE": "docs-internal", "GITHUB_ACTIONS": ""}
            ),
            patch.object(
                sys,
                "argv",
                [
                    "free_gate",
                    "verify",
                    "--sha",
                    SHA,
                    "--authorization-run",
                    "40",
                    "--output",
                    "/synthetic/record.json",
                ],
            ),
            patch.object(f.e, "GitHub", return_value=self.github),
            patch.object(
                f.subprocess,
                "check_output",
                side_effect=[SHA + "\n", "", json.dumps({"login": e.OWNER})],
            ),
            patch.object(
                f, "verify", side_effect=e.Rejected("synthetic default check")
            ) as verify,
            self.assertRaises(e.Rejected),
        ):
            f.main()
        self.assertEqual(verify.call_args.args[-1], "full")

    def test_workflows_retain_read_only_disposable_owner_boundaries(self):
        for name in ["free-qualification.yml", "free-authorization.yml"]:
            value = (e.ROOT / ".github/workflows" / name).read_text()
            self.assertIn("contents: read", value)
            self.assertNotIn("contents: write", value)
            self.assertNotIn("secrets.", value)
            self.assertIn("runs-on: ubuntu-latest", value)
            self.assertIn("persist-credentials: false", value)
            self.assertIn("default: full", value)
            self.assertIn("github.ref == 'refs/heads/main'", value)


if __name__ == "__main__":
    unittest.main()
