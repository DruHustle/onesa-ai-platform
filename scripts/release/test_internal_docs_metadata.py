"""Synthetic draft metadata is evidence only; provider custody is never exercised."""

import copy
import hashlib
import json
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import evidence as e
import free_gate as f
from test_evidence import FINGERPRINT, SHA
from test_free_gate import GitHub

PRODUCER = "b" * 64


class DraftGitHub(GitHub):
    def __init__(self):
        super().__init__()
        stamp = datetime.now(timezone.utc).isoformat()
        self.metadata = {
            "schema_version": 1,
            "kind": "protected-docs-preview-qualification",
            "repository": e.REPOSITORY,
            "candidate_commit": SHA,
            "source_sha256": FINGERPRINT,
            "producer_sha256": PRODUCER,
            "ci_run_id": 10,
            "verified_at": stamp,
            "delivery_scope": "docs-internal",
            "staging": {
                "project": "onesa-engineering-docs",
                "environment": "preview",
                "deployment_id": "123abcde-1234-1234-1234-123456789abc",
                "source_commit": SHA,
                "origin": "https://123abcde.onesa-engineering-docs.pages.dev",
            },
            "private_artifacts": {
                key: "c" * 64
                for key in [
                    "staging_tree_sha256",
                    "staging_archive_sha256",
                    "production_tree_sha256",
                    "production_archive_sha256",
                ]
            },
            "access_configuration_sha256": "d" * 64,
            "counts": {
                "source_provenance_checks": 1,
                "unauthenticated_denials": 200,
                "verified_asset_responses": 200,
                "accessibility_views": 18,
                "layout_views": 18,
                "architecture_topics": 18,
                "engineering_chapters": 17,
                "onboarding_days": 4,
                "application_navigation_views": 2,
                "identity_icons": 3,
                "pdfs": 22,
                "diagrams": 83,
                "mfa_checks": 1,
                "blocking_accessibility": 0,
                "unexpected_browser_errors": 0,
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
            "tag_name": "docs-internal-qualification-" + SHA,
            "body": "",
            "created_at": stamp,
            "updated_at": stamp,
            "assets": [{"id": 200}],
        }
        self.asset = {
            "id": 200,
            "name": f.INTERNAL_DOCS_METADATA_ASSET,
            "state": "uploaded",
            "uploader": {"login": e.OWNER},
            "content_type": "application/json",
            "url": f"https://api.github.com/repos/{e.REPOSITORY}/releases/assets/200",
            "created_at": stamp,
            "updated_at": stamp,
        }
        self.refresh()

    def refresh(self):
        self.content = json.dumps(self.metadata).encode()
        self.asset["size"] = len(self.content)
        self.asset["digest"] = "sha256:" + hashlib.sha256(self.content).hexdigest()

    def api(self, path, pages=False):
        if path == f"repos/{e.REPOSITORY}/releases/100":
            return copy.deepcopy(self.release)
        if path == f"repos/{e.REPOSITORY}/releases/assets/200":
            return copy.deepcopy(self.asset)
        return super().api(path, pages)


class InternalDocsMetadataTests(unittest.TestCase):
    def setUp(self):
        self.github = DraftGitHub()
        self.source = patch.object(
            f, "_internal_docs_local_source", return_value=FINGERPRINT
        )
        self.download = patch.object(
            f, "_internal_docs_asset_bytes", side_effect=lambda _id: self.github.content
        )
        self.source_mock = self.source.start()
        self.download.start()
        self.addCleanup(self.source.stop)
        self.addCleanup(self.download.stop)

    def read(self, **kwargs):
        return f.internal_docs_preview_metadata(
            self.github, SHA, 100, 200, self.github.asset["digest"], PRODUCER, **kwargs
        )

    def test_actual_api_custody_still_cannot_authorize_or_establish_hosted_pass(self):
        result = self.read()
        self.assertEqual(result["status"], "REQUIRES_EXTERNAL_LIVE_VALIDATION")
        self.assertEqual(result["STAGING_VERIFIED"], "BLOCKED")
        self.assertIs(result["PRODUCTION_AUTHORIZED"], False)
        for key in [
            "application_deployment_authorized",
            "backend_deployment_authorized",
            "production_deployment_authorized",
        ]:
            self.assertIs(result[key], False)
        self.assertEqual(result["custody"]["asset_id"], 200)
        self.assertEqual(result["metadata"], self.github.metadata)
        self.assertNotIn("PASS", json.dumps(result))

    def test_public_full_and_caller_pass_cannot_select_this_reader(self):
        for scope in ["full", "docs-public", "PASS"]:
            with self.subTest(scope=scope), self.assertRaises(e.Rejected):
                self.read(delivery_scope=scope)
        with self.assertRaises(e.Rejected):
            f.internal_docs_preview_metadata(
                self.github,
                SHA,
                {"status": "PASS"},
                200,
                self.github.asset["digest"],
                PRODUCER,
            )

    def test_candidate_source_producer_ci_scope_and_grants_are_bound(self):
        for key, value in [
            ("candidate_commit", "c" * 40),
            ("source_sha256", "a" * 64),
            ("producer_sha256", "a" * 64),
            ("ci_run_id", 11),
            ("ci_run_id", True),
            ("repository", "other/repo"),
            ("delivery_scope", "full"),
            ("schema_version", True),
            ("application_deployment_authorized", True),
            ("backend_deployment_authorized", True),
            ("production_deployment_authorized", True),
        ]:
            original = copy.deepcopy(self.github.metadata)
            self.github.metadata[key] = value
            self.github.refresh()
            with self.subTest(key=key, value=value), self.assertRaises(e.Rejected):
                self.read()
            self.github.metadata = original
            self.github.refresh()

    def test_no_private_paths_identity_claims_tokens_or_pass_fields(self):
        for section in [None, "staging", "private_artifacts", "counts"]:
            for key in ["email", "sub", "JWT", "private_paths", "site_bytes", "status"]:
                original = copy.deepcopy(self.github.metadata)
                target = (
                    self.github.metadata
                    if section is None
                    else self.github.metadata[section]
                )
                target[key] = "synthetic-private-field"
                self.github.refresh()
                with (
                    self.subTest(section=section, key=key),
                    self.assertRaises(e.Rejected),
                ):
                    self.read()
                self.github.metadata = original
                self.github.refresh()

    def test_source_bound_deployment_origin_only_not_aliases_foreign_or_production(
        self,
    ):
        for key, value in [
            ("project", "onesa-app"),
            ("environment", "production"),
            ("source_commit", "c" * 40),
            ("deployment_id", "not-uuid"),
            ("deployment_id", "87654321-1234-1234-1234-123456789abc"),
            ("origin", "https://onesa-engineering-docs.pages.dev"),
            ("origin", "https://staging.onesa-engineering-docs.pages.dev"),
            (
                "origin",
                "https://123abcde.onesa-engineering-docs.pages.dev.evil.invalid",
            ),
            ("origin", "https://123abcde.onesa-engineering-docs.pages.dev/?token=x"),
            ("origin", "https://user@123abcde.onesa-engineering-docs.pages.dev"),
            ("origin", "http://123abcde.onesa-engineering-docs.pages.dev"),
        ]:
            original = copy.deepcopy(self.github.metadata)
            self.github.metadata["staging"][key] = value
            self.github.refresh()
            with self.subTest(key=key), self.assertRaises(e.Rejected):
                self.read()
            self.github.metadata = original
            self.github.refresh()

    def test_only_exact_hashes_and_bounded_typed_counts(self):
        for section, key, value in [
            ("private_artifacts", "staging_tree_sha256", "private/path.pdf"),
            ("private_artifacts", "production_archive_sha256", "A" * 64),
            ("counts", "mfa_checks", True),
            ("counts", "mfa_checks", 0),
            ("counts", "unauthenticated_denials", 0),
            ("counts", "verified_asset_responses", 20001),
            ("counts", "blocking_accessibility", 1),
            ("counts", "unexpected_browser_errors", 1),
        ]:
            original = copy.deepcopy(self.github.metadata)
            self.github.metadata[section][key] = value
            self.github.refresh()
            with self.subTest(section=section, key=key), self.assertRaises(e.Rejected):
                self.read()
            self.github.metadata = original
            self.github.refresh()

    def test_non_owner_published_wrong_candidate_or_multi_asset_draft_rejected(self):
        for key, value in [
            ("author", {"login": "other"}),
            ("draft", False),
            ("published_at", datetime.now(timezone.utc).isoformat()),
            ("target_commitish", "main"),
            ("tag_name", "qualification"),
            ("assets", [{"id": 201}]),
            ("assets", [{"id": 200}, {"id": 201}]),
            ("body", "private body cannot become evidence"),
        ]:
            original = copy.deepcopy(self.github.release)
            self.github.release[key] = value
            with self.subTest(key=key), self.assertRaises(e.Rejected):
                self.read()
            self.github.release = original

    def test_asset_uploader_type_size_digest_and_immutable_origin(self):
        for key, value in [
            ("uploader", {"login": "other"}),
            ("name", "site.zip"),
            ("content_type", "application/zip"),
            ("size", True),
            ("size", f.INTERNAL_DOCS_METADATA_BYTES + 1),
            ("state", "new"),
            ("url", "https://evil.invalid/file"),
            ("id", 201),
        ]:
            original = copy.deepcopy(self.github.asset)
            self.github.asset[key] = value
            with self.subTest(key=key), self.assertRaises(e.Rejected):
                self.read()
            self.github.asset = original
        self.github.content += b"tampered"
        with self.assertRaises(e.Rejected):
            self.read()

    def test_stale_future_naive_or_malformed_timestamps_rejected(self):
        for stamp in [
            (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
            (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            "bad",
            None,
        ]:
            original = copy.deepcopy(self.github.metadata)
            self.github.metadata["verified_at"] = stamp
            self.github.refresh()
            with self.subTest(stamp=stamp), self.assertRaises(e.Rejected):
                self.read()
            self.github.metadata = original
            self.github.refresh()

    def test_digest_duplicates_nonfinite_and_non_json_rejected(self):
        for content in [
            b'{"status":"PASS","status":"PASS"}',
            b'{"count":NaN}',
            b"not json",
            b"\xff",
        ]:
            self.github.content = content
            self.github.asset["size"] = len(content)
            self.github.asset["digest"] = (
                "sha256:" + hashlib.sha256(content).hexdigest()
            )
            with self.subTest(content=content), self.assertRaises(e.Rejected):
                self.read()

    def test_main_movement_failed_staging_or_stale_ci_rejected(self):
        self.github.main_sha = "c" * 40
        with self.assertRaises(e.Rejected):
            self.read()
        self.github.main_sha = SHA
        for field, value in [
            ("conclusion", "failure"),
            ("head_branch", "staging"),
            (
                "updated_at",
                (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
            ),
        ]:
            original = copy.deepcopy(self.github.runs_by_id[10])
            self.github.runs_by_id[10][field] = value
            with self.subTest(field=field), self.assertRaises(e.Rejected):
                self.read()
            self.github.runs_by_id[10] = original

    def test_custody_main_source_or_ci_changed_during_read_rejected(self):
        for change in ["draft", "main", "source", "ci"]:
            self.github = DraftGitHub()
            self.source_mock.return_value = FINGERPRINT

            def mutate(_id, change=change):
                if change == "draft":
                    self.github.release["draft"] = False
                if change == "main":
                    self.github.main_sha = "c" * 40
                if change == "source":
                    self.source_mock.return_value = "a" * 64
                if change == "ci":
                    self.github.ci_jobs[0]["conclusion"] = "failure"
                return self.github.content

            with (
                patch.object(f, "_internal_docs_asset_bytes", side_effect=mutate),
                self.subTest(change=change),
                self.assertRaises(e.Rejected),
            ):
                self.read()

    def test_local_reader_requires_exact_clean_checkout(self):
        self.source.stop()
        ok = SimpleNamespace(returncode=0, stdout=SHA.encode() + b"\n")
        clean = SimpleNamespace(returncode=0, stdout=b"")
        for head, status in [
            (ok, SimpleNamespace(returncode=0, stdout=b" M file")),
            (SimpleNamespace(returncode=0, stdout=b"c" * 40), clean),
            (SimpleNamespace(returncode=1, stdout=b""), clean),
        ]:
            with (
                patch.object(f.subprocess, "run", side_effect=[head, status]),
                self.subTest(head=head, status=status),
                self.assertRaises(e.Rejected),
            ):
                f._internal_docs_local_source(SHA)
        with (
            patch.object(f.subprocess, "run", side_effect=[ok, clean]),
            patch.object(e, "source_hash", return_value=FINGERPRINT),
        ):
            self.assertEqual(f._internal_docs_local_source(SHA), FINGERPRINT)

    def test_binary_download_uses_fixed_get_and_bounded_owned_process(self):
        self.download.stop()
        original = subprocess.Popen
        for count, exit_code in [
            (32, 0),
            (f.INTERNAL_DOCS_METADATA_BYTES + 1, 0),
            (0, 1),
        ]:

            def spawn(command, count=count, exit_code=exit_code, **kwargs):
                self.assertEqual(
                    command,
                    [
                        "gh",
                        "api",
                        f"repos/{e.REPOSITORY}/releases/assets/200",
                        "--hostname",
                        "github.com",
                        "--method",
                        "GET",
                        "--header",
                        "Accept: application/octet-stream",
                    ],
                )
                self.assertIs(kwargs["stderr"], subprocess.DEVNULL)
                return original(
                    [
                        sys.executable,
                        "-c",
                        f"import sys;sys.stdout.buffer.write(b'x'*{count});sys.exit({exit_code})",
                    ],
                    **kwargs,
                )

            with (
                patch.object(f.subprocess, "Popen", side_effect=spawn),
                self.subTest(count=count, exit_code=exit_code),
            ):
                if count == 32:
                    self.assertEqual(f._internal_docs_asset_bytes(200), b"x" * 32)
                else:
                    with self.assertRaises(e.Rejected):
                        f._internal_docs_asset_bytes(200)

    def test_binary_download_deadline_and_errors_remain_redacted(self):
        self.download.stop()
        original = subprocess.Popen

        def spawn(_command, **kwargs):
            return original(
                [sys.executable, "-c", "import time;time.sleep(30)"], **kwargs
            )

        with (
            patch.object(f.subprocess, "Popen", side_effect=spawn),
            patch.object(f.time, "monotonic", side_effect=[0, 31]),
            self.assertRaisesRegex(e.Rejected, "Metadata download timed out"),
        ):
            f._internal_docs_asset_bytes(200)
        with (
            patch.object(
                f.subprocess, "Popen", side_effect=OSError("synthetic-private-detail")
            ),
            self.assertRaises(e.Rejected) as error,
        ):
            f._internal_docs_asset_bytes(200)
        self.assertEqual(str(error.exception), "Metadata download unavailable")

    def test_bad_immutable_inputs_fail_before_any_asset_download(self):
        self.download.stop()
        for value in [0, -1, True, "200", {"status": "PASS"}]:
            with (
                patch.object(f.subprocess, "Popen") as command,
                self.subTest(value=value),
                self.assertRaises(e.Rejected),
            ):
                f._internal_docs_asset_bytes(value)
            command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
