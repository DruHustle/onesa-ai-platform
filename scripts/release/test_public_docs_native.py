"""Synthetic native metadata stays conditional; no browser/provider authority is exercised."""

import copy
import hashlib
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import evidence as e
import free_gate as f
from test_docs_scope import DocsGitHub
from test_evidence import FINGERPRINT, SHA

PRODUCER = "b" * 64


class NativeGitHub(DocsGitHub):
    def __init__(self):
        super().__init__()
        self.docs["native_validation_required"] = True
        proof = self.docs["scopes"]["public"]
        proof.update(status="BLOCKED", validation_channel="native-owner")
        proof["checks"]["hosted_preview_acceptance"] = "PENDING_NATIVE_OWNER"
        proof["staging_acceptance"] = proof.pop("hosted_acceptance")
        native_origin = "https://onesa-docs-synthetic-druhustles-projects.vercel.app"
        proof["preview"]["url"] = native_origin
        proof["staging_acceptance"]["origin"] = native_origin
        stamp = datetime.now(timezone.utc).isoformat()
        self.runs_by_id[20]["updated_at"] = stamp
        self.metadata_record = {
            "schema_version": 1,
            "evidence_kind": f.PUBLIC_DOCS_METADATA_KIND,
            "repository": e.REPOSITORY,
            "candidate_commit": SHA,
            "source_sha256": FINGERPRINT,
            "verified_at": stamp,
            "delivery_scope": "docs-public",
            "classification": "public",
            "build_environment": "staging",
            "producer_sha256": PRODUCER,
            "ci_sha256": e.digest(e.checked_ci(self, SHA)[1]),
            "staging_run_id": 20,
            "preview_record_sha256": e.digest(self.docs),
            "preview_artifact_id": 201,
            "production_artifact_id": 202,
            "preview_artifact_sha256": proof["preview_artifact"]["artifact_sha256"],
            "production_artifact_sha256": proof["artifact_sha256"],
            "preview_build_sha256": proof["preview_artifact"]["build_sha256"],
            "production_build_sha256": proof["build_sha256"],
            "hosted_acceptance_sha256": "c" * 64,
            "preview": {
                "provider": "vercel",
                "project": "onesa-docs",
                "project_id": f.PUBLIC_DOCS_PROJECT,
                "deployment_id": "dpl_synthetic",
                "origin": native_origin,
                "source_commit": SHA,
                "environment": "preview",
            },
            "counts": {
                "accessibility_views": 124,
                "layout_views": 20,
                "navigation_views": 2,
                "identity_icons": 3,
                "diagrams": 21,
                "manual_pdfs": 11,
                "links": 3084,
            },
            "application_deployment_authorized": False,
            "backend_deployment_authorized": False,
            "production_deployment_authorized": False,
        }
        self.release = {
            "id": 100,
            "draft": True,
            "published_at": None,
            "author": {"login": e.OWNER},
            "target_commitish": SHA,
            "tag_name": "docs-public-native-qualification-" + SHA,
            "body": "",
            "created_at": stamp,
            "updated_at": stamp,
            "assets": [{"id": 200, "name": f.PUBLIC_DOCS_METADATA_ASSET}],
        }
        self.asset = {
            "id": 200,
            "name": f.PUBLIC_DOCS_METADATA_ASSET,
            "state": "uploaded",
            "uploader": {"login": e.OWNER},
            "content_type": "application/json",
            "url": f"https://api.github.com/repos/{e.REPOSITORY}/releases/assets/200",
            "created_at": stamp,
            "updated_at": stamp,
        }
        self.refresh()

    def refresh(self):
        self.content = json.dumps(self.metadata_record).encode()
        self.asset.update(
            size=len(self.content),
            digest="sha256:" + hashlib.sha256(self.content).hexdigest(),
        )

    def run(self, identifier):
        return copy.deepcopy(super().run(identifier))

    def api(self, path, pages=False, binary=False):
        if path.endswith("/artifacts?per_page=100"):
            return [
                {
                    "artifacts": [
                        {"id": 201, "name": "onesa-public-docs-staging"},
                        {"id": 202, "name": "onesa-public-docs-production"},
                    ]
                }
            ]
        if path.endswith("/artifacts/202"):
            return {**self.metadata, "id": 202}
        if path.endswith("/artifacts/202/zip"):
            return self.site
        if path.endswith("/releases/100"):
            return copy.deepcopy(self.release)
        if path.endswith("/releases/assets/200"):
            return copy.deepcopy(self.asset)
        return super().api(path, pages, binary)


class PublicNativeTests(unittest.TestCase):
    def setUp(self):
        self.github = NativeGitHub()
        for item in [
            patch.object(e, "source_hash", return_value=FINGERPRINT),
            patch.object(f, "_internal_docs_local_source", return_value=FINGERPRINT),
            patch.object(
                f,
                "_internal_docs_asset_bytes",
                side_effect=lambda _id: self.github.content,
            ),
        ]:
            item.start()
            self.addCleanup(item.stop)

    def custody(self):
        return {
            "release_id": 100,
            "asset_id": 200,
            "asset_digest": self.github.asset["digest"],
            "producer_sha256": PRODUCER,
        }

    def read(self):
        return f.public_docs_preview_metadata(self.github, SHA, 20, self.custody())

    def prepare(self):
        self.github.record = f.qualification(
            self.github,
            SHA,
            self.github.run(30),
            20,
            "docs-public",
            metadata_custody=self.custody(),
        )
        self.github.approval = f.authorize(
            self.github,
            SHA,
            self.github.run(40),
            30,
            e.digest(self.github.record),
            None,
            "approve",
            "docs-public",
            expected_producer_sha256=PRODUCER,
        )

    def verify(self, pin=PRODUCER):
        return f.verify(
            self.github, SHA, 40, "docs-public", expected_producer_sha256=pin
        )

    def test_pending_preview_and_metadata_never_establish_hosted_pass_or_grant(self):
        self.prepare()
        result = self.verify()
        self.assertEqual(result["status"], "CONDITIONAL_EXTERNAL_HANDOFF")
        self.assertFalse(result["deployment_triggered"])
        for record in [self.read(), self.github.record, self.github.approval, result]:
            self.assertEqual(record["STAGING_VERIFIED"], "BLOCKED")
            for key in [
                "production_deployment_authorized",
                "application_deployment_authorized",
                "backend_deployment_authorized",
            ]:
                self.assertIs(record[key], False)
        self.assertEqual(result["staging"]["public_site_artifact"]["id"], 202)
        self.assertEqual(result["staging"]["preview_site_artifact"]["id"], 201)

    def test_default_full_private_and_unpinned_current_public_consumers_refuse(self):
        self.prepare()
        for scope in ["full", "docs-internal", "docs-public"]:
            with self.subTest(scope=scope), self.assertRaises(e.Rejected):
                f.verify(self.github, SHA, 40, scope)
        with self.assertRaises(e.Rejected):
            f.verify(self.github, SHA, 40)
        with (
            patch.dict(
                os.environ,
                {"DELIVERY_SCOPE": "docs-public", "METADATA_PRODUCER_SHA256": PRODUCER},
                clear=True,
            ),
            self.assertRaises(e.Rejected),
        ):
            f.verify(self.github, SHA, 40)

    def test_missing_bad_or_self_selected_pin_refused(self):
        self.prepare()
        for pin in [None, "", "PASS", "d" * 64, True]:
            with self.subTest(pin=pin), self.assertRaises(e.Rejected):
                self.verify(pin)

    def test_pre_main_seam_can_review_stage_but_cannot_read_qualifying_metadata(self):
        self.github.main_sha = "d" * 40
        for identifier in [10, 11]:
            self.github.runs_by_id[identifier]["head_branch"] = "staging"
        stage = f.public_docs_native_preview(self.github, SHA, 20)
        self.assertEqual(stage["STAGING_VERIFIED"], "BLOCKED")
        with self.assertRaises(e.Rejected):
            self.read()

    def test_full_owner_dispatched_ci_keeps_preview_pending_and_production_denied(self):
        self.github.main_sha = "d" * 40
        for identifier in [10, 11]:
            self.github.runs_by_id[identifier].update(
                head_branch="staging", event="workflow_dispatch"
            )
        stage = f.public_docs_native_preview(self.github, SHA, 20)
        self.assertEqual(stage["status"], "REQUIRES_EXTERNAL_LIVE_VALIDATION")
        self.assertEqual(stage["STAGING_VERIFIED"], "BLOCKED")
        for field in [
            "production_deployment_authorized",
            "application_deployment_authorized",
            "backend_deployment_authorized",
        ]:
            self.assertIs(stage[field], False)
        with self.assertRaises(e.Rejected):
            self.read()

    def test_failed_skipped_ci_foreign_owner_and_rerun_refused(self):
        for field, value in [
            ("actor", {"login": "foreign"}),
            ("triggering_actor", {"login": "foreign"}),
            ("event", "push"),
            ("run_attempt", 2),
            ("head_branch", "dev"),
        ]:
            previous = copy.deepcopy(self.github.runs_by_id[20])
            self.github.runs_by_id[20][field] = value
            with self.subTest(field=field), self.assertRaises(e.Rejected):
                self.read()
            self.github.runs_by_id[20] = previous
        self.github.ci_jobs[0]["conclusion"] = "skipped"
        with self.assertRaises(e.Rejected):
            self.read()

    def test_legacy_pass_missing_pending_or_wrong_project_source_and_target_refused(
        self,
    ):
        proof = self.github.docs["scopes"]["public"]
        for target, key, value in [
            (proof, "status", "PASS"),
            (proof, "validation_channel", "ci"),
            (proof["checks"], "hosted_preview_acceptance", "PASS"),
            (proof["preview"], "projectId", "wrong"),
            (proof["preview"], "sourceRevision", "d" * 40),
            (proof["preview"], "target", "production"),
            (proof["preview"], "url", "https://evil.invalid/"),
            (proof["preview"], "url", proof["preview"]["url"] + "/"),
        ]:
            original = target[key]
            target[key] = value
            with self.subTest(key=key), self.assertRaises(e.Rejected):
                self.read()
            target[key] = original

    def test_false_or_missing_local_context_and_typed_views_refused(self):
        proof = self.github.docs["scopes"]["public"]
        for field in ["staging_acceptance", "production_acceptance"]:
            for key, value in [
                ("result", "FAIL"),
                ("environment_context", "wrong"),
                ("accessibility", ["PASS"] * 124),
            ]:
                original = proof[field][key]
                proof[field][key] = value
                with self.subTest(field=field, key=key), self.assertRaises(e.Rejected):
                    self.read()
                proof[field][key] = original

    def test_archive_bytes_ids_and_digest_substitution_refused(self):
        self.github.site = self.github.site + b"changed"
        with self.assertRaises(e.Rejected):
            self.read()
        self.github = NativeGitHub()
        for key in [
            "preview_artifact_id",
            "production_artifact_id",
            "preview_artifact_sha256",
            "production_build_sha256",
            "preview_record_sha256",
            "ci_sha256",
            "staging_run_id",
        ]:
            original = self.github.metadata_record[key]
            self.github.metadata_record[key] = (
                "d" * 64 if isinstance(original, str) else original + 1
            )
            self.github.refresh()
            with self.subTest(key=key), self.assertRaises(e.Rejected):
                self.read()
            self.github.metadata_record[key] = original
            self.github.refresh()

    def test_unknown_identity_sitebytes_caller_pass_and_boolean_counts_refused(self):
        for key, value in [
            ("status", "PASS"),
            ("email", "synthetic@example.invalid"),
            ("session", "synthetic"),
            ("html", "sitebytes"),
        ]:
            self.github.metadata_record[key] = value
            self.github.refresh()
            with self.subTest(key=key), self.assertRaises(e.Rejected):
                self.read()
            del self.github.metadata_record[key]
        self.github.metadata_record["counts"]["accessibility_views"] = True
        self.github.refresh()
        with self.assertRaises(e.Rejected):
            self.read()

    def test_asset_release_source_owner_digest_bounds_and_unavailable_draft_refused(
        self,
    ):
        for target, key, value in [
            (self.github.release, "draft", False),
            (self.github.release, "author", {"login": "foreign"}),
            (self.github.release, "target_commitish", "main"),
            (self.github.release, "assets", [{"id": 200}, {"id": 201}]),
            (self.github.asset, "uploader", {"login": "foreign"}),
            (self.github.asset, "size", 65537),
            (self.github.asset, "digest", "sha256:" + "d" * 64),
        ]:
            original = target[key]
            target[key] = value
            with self.subTest(key=key), self.assertRaises(e.Rejected):
                self.read()
            target[key] = original
        actual = self.github.api

        def unavailable(path, **kwargs):
            if "/releases/" in path:
                raise e.Rejected("Read-only draft visibility is unavailable")
            return actual(path, **kwargs)

        with (
            patch.object(self.github, "api", unavailable),
            self.assertRaises(e.Rejected),
        ):
            self.read()

    def test_revocation_expiry_latest_pending_and_grant_substitution_refused(self):
        for key, value in [
            ("decision", "revoke"),
            ("production_deployment_authorized", True),
            ("STAGING_VERIFIED", "PASS"),
            (
                "approved_at",
                (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
            ),
        ]:
            self.prepare()
            self.github.approval[key] = value
            with self.subTest(key=key), self.assertRaises(e.Rejected):
                self.verify()
        self.prepare()
        self.github.latest = 30
        with self.assertRaises(e.Rejected):
            self.verify()

    def test_empty_partial_or_caller_json_custody_cannot_fall_back_to_strict_public(
        self,
    ):
        for custody in [{}, {"status": "PASS"}, {"release_id": 100}]:
            with self.subTest(custody=custody), self.assertRaises(e.Rejected):
                f.qualification(
                    self.github,
                    SHA,
                    self.github.run(30),
                    20,
                    "docs-public",
                    metadata_custody=custody,
                )
        with self.assertRaises(e.Rejected):
            f.qualification(self.github, SHA, self.github.run(30), 20, "docs-public")

    def test_expired_metadata_duplicate_json_and_nonfinite_values_refused(self):
        self.github.metadata_record["verified_at"] = (
            datetime.now(timezone.utc) - timedelta(days=2)
        ).isoformat()
        self.github.refresh()
        with self.assertRaises(e.Rejected):
            self.read()
        self.github = NativeGitHub()
        for body in [
            b'{"schema_version":1,"schema_version":1}',
            b'{"links":NaN}',
            b'{"links":Infinity}',
        ]:
            self.github.content = body
            self.github.asset.update(
                size=len(body),
                digest="sha256:" + hashlib.sha256(body).hexdigest(),
            )
            with self.subTest(body=body), self.assertRaises(e.Rejected):
                self.read()

    def test_custody_changed_after_download_and_run_changed_after_artifacts_refused(
        self,
    ):
        actual = self.github.api
        release_reads = 0

        def changed_asset(path, **kwargs):
            nonlocal release_reads
            if path.endswith("/releases/100"):
                release_reads += 1
                if release_reads == 2:
                    self.github.asset["updated_at"] = (
                        datetime.now(timezone.utc) - timedelta(minutes=1)
                    ).isoformat()
            return actual(path, **kwargs)

        with (
            patch.object(self.github, "api", changed_asset),
            self.assertRaises(e.Rejected),
        ):
            self.read()

        self.github = NativeGitHub()
        actual_artifact = self.github.artifact
        reads = 0

        def changed_run(run, name):
            nonlocal reads
            result = actual_artifact(run, name)
            if name == "documentation-qualification":
                reads += 1
                if reads == 1:
                    self.github.runs_by_id[20]["run_attempt"] = 2
            return result

        with (
            patch.object(self.github, "artifact", changed_run),
            self.assertRaises(e.Rejected),
        ):
            self.read()

    def test_conditional_authorization_requires_pin_and_refuses_owner_issue(self):
        self.github.record = f.qualification(
            self.github,
            SHA,
            self.github.run(30),
            20,
            "docs-public",
            metadata_custody=self.custody(),
        )
        for pin, issue in [(None, None), ("d" * 64, None), (PRODUCER, 1)]:
            with self.subTest(pin=pin, issue=issue), self.assertRaises(e.Rejected):
                f.authorize(
                    self.github,
                    SHA,
                    self.github.run(40),
                    30,
                    e.digest(self.github.record),
                    issue,
                    "approve",
                    "docs-public",
                    expected_producer_sha256=pin,
                )

    def test_cli_ambient_scope_and_pin_do_not_select_conditional_channel(self):
        with (
            patch.dict(
                os.environ,
                {"DELIVERY_SCOPE": "docs-public", "METADATA_PRODUCER_SHA256": PRODUCER},
                clear=True,
            ),
            patch.object(
                sys,
                "argv",
                [
                    "free_gate.py",
                    "verify",
                    "--sha",
                    SHA,
                    "--authorization-run",
                    "40",
                    "--output",
                    "synthetic.json",
                ],
            ),
            patch.object(e, "GitHub", return_value=self.github),
            patch.object(
                f.subprocess,
                "check_output",
                side_effect=[SHA, b"", json.dumps({"login": e.OWNER})],
            ),
            patch.object(f, "verify", return_value={}) as verified,
            patch.object(e, "save"),
        ):
            f.main()
            verified.assert_called_once_with(self.github, SHA, "40", "full")

    def test_cli_partial_custody_and_foreign_scope_pin_fail_before_api(self):
        for arguments in [
            [
                "qualify",
                "--delivery-scope",
                "docs-public",
                "--metadata-release-id",
                "100",
            ],
            [
                "verify",
                "--delivery-scope",
                "full",
                "--metadata-producer-sha256",
                PRODUCER,
            ],
            [
                "authorize",
                "--delivery-scope",
                "docs-internal",
                "--metadata-producer-sha256",
                PRODUCER,
            ],
        ]:
            with (
                self.subTest(arguments=arguments),
                patch.dict(os.environ, {}, clear=True),
                patch.object(
                    sys,
                    "argv",
                    ["free_gate.py", *arguments, "--output", "synthetic.json"],
                ),
                patch.object(e, "GitHub") as github,
                self.assertRaises(e.Rejected),
            ):
                f.main()
            github.assert_not_called()


if __name__ == "__main__":
    unittest.main()
