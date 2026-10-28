"""Synthetic, isolated release-gate regressions; these do not approve a release."""

import copy
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import evidence as e

SHA = "a" * 40
FINGERPRINT = "b" * 64
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
STAMP = NOW.isoformat()


def run(identifier, workflow, branch="main", event="workflow_dispatch"):
    return {
        "id": identifier,
        "workflow_id": identifier,
        "repository": {"full_name": e.REPOSITORY, "id": 7},
        "head_repository": {"full_name": e.REPOSITORY},
        "head_sha": SHA,
        "head_branch": branch,
        "path": ".github/workflows/" + workflow,
        "event": event,
        "run_attempt": 1,
        "actor": {"login": e.OWNER},
        "triggering_actor": {"login": e.OWNER},
        "status": "completed",
        "conclusion": "success",
        "created_at": STAMP,
        "updated_at": STAMP,
    }


def fixtures():
    builds = [
        {
            "application": name,
            "image_digest": "sha256:" + "c" * 64,
            "artifact": {
                "id": index,
                "digest": "sha256:" + "d" * 64,
                "name": "runtime-" + name,
                "run_id": 10,
                "record_sha256": "e" * 64,
            },
        }
        for index, name in enumerate([e.PRODUCT + "-backend", e.PRODUCT + "-frontend"])
    ]
    checks = {
        name: "PASS"
        for name in [
            "deployed_commit",
            "backend_readiness",
            "frontend_availability",
            "authentication",
            "database_connectivity",
            "critical_workflows",
            "user_data_isolation",
            "storage_integrations",
            "streaming",
            "inference",
            "embeddings",
        ]
    }
    stage = {
        "repository": e.REPOSITORY,
        "candidate_commit": SHA,
        "source_sha256": FINGERPRINT,
        "environment": "Staging",
        "builds_sha256": e.digest(builds),
        "verified_at": STAMP,
        "checks": checks,
        "status": "PASS",
        "render_deployment_id": "dep-test",
        "vercel_deployment_id": "dpl_test",
        "critical_workflow_checks": {
            name: "PASS" for name in e.platform_workflow_check_names()
        },
        "observed_model": {"real_inference": True, "backend": "cloudflare"},
    }
    stage_origin = {
        "run_id": 20,
        "id": 200,
        "digest": "sha256:" + "f" * 64,
        "name": "staging-verification",
        "record_sha256": e.digest(stage),
    }
    evidence = {
        "schema_version": 1,
        "repository": e.REPOSITORY,
        "workflow_run_id": 30,
        "candidate_commit": SHA,
        "reviewed_commit": SHA,
        "valid_for_source_sha256": FINGERPRINT,
        "content_version": FINGERPRINT,
        "verification_timestamp": STAMP,
        "CODE_VERIFIED": "PASS",
        "STAGING_VERIFIED": "PASS",
        "OPERATIONS_VERIFIED": "BLOCKED",
        "CONTENT_LEGAL_APPROVED": "BLOCKED",
        "builds": builds,
        "staging": {"record": stage, "artifact": stage_origin},
    }
    origin = {
        "run_id": 30,
        "id": 300,
        "digest": "sha256:" + "f" * 64,
        "name": "release-qualification",
        "record_sha256": e.digest(evidence),
    }
    approval = {
        "schema_version": 1,
        "repository": e.REPOSITORY,
        "candidate_commit": SHA,
        "source_sha256": FINGERPRINT,
        "target_environment": "Production",
        "content_version": FINGERPRINT,
        "builds_sha256": e.digest(builds),
        "qualification": origin,
        "evidence_sha256": e.digest(evidence),
        "decision": "approve",
        "operations_review": "approved",
        "legal_review": "approved",
        "review_url": "https://github.com/" + e.REPOSITORY + "/issues/1",
        "approver": e.OWNER,
        "approved_at": STAMP,
        "workflow_run_id": 40,
    }
    manifest = {
        "repository": e.REPOSITORY,
        "candidate_commit": SHA,
        "workflow_run_id": 50,
        "target_environment": "Production",
        "source_sha256": FINGERPRINT,
        "build_sha256": "1" * 64,
        "encrypted_sha256": "2" * 64,
    }
    build_origin = {
        "run_id": 50,
        "id": 500,
        "digest": "sha256:" + "3" * 64,
        "name": "production-build-manifest",
        "record_sha256": e.digest(manifest),
    }
    bundle_origin = {
        "run_id": 50,
        "id": 501,
        "digest": "sha256:" + "4" * 64,
        "name": "production-build-encrypted",
        "record_sha256": manifest["encrypted_sha256"],
    }
    evidence["frontend_build"] = {
        "manifest": manifest,
        "artifact": build_origin,
        "bundle_artifact": bundle_origin,
    }
    origin["record_sha256"] = e.digest(evidence)
    approval["evidence_sha256"] = e.digest(evidence)
    return evidence, origin, approval


class GateTests(unittest.TestCase):
    def setUp(self):
        self.evidence, self.origin, self.approval = fixtures()
        self.run = run(40, "release-review.yml")

    def validate(self):
        e.validate_approval(
            self.approval, self.evidence, self.origin, self.run, SHA, now=NOW
        )

    def test_bounded_hosted_sse_parser_rejects_partial_foreign_and_oversized_frames(
        self,
    ):
        import hosted_suite

        valid = b'event: content_delta\ndata: {"text":\ndata: "synthetic"}\n\n'
        self.assertEqual(
            list(hosted_suite.stream_events(io.BytesIO(valid))),
            [("content_delta", {"text": "synthetic"})],
        )
        for payload in [
            b'event: content_delta\ndata: {"text":"unfinished"}\n',
            b"event: unauthorized\ndata: {}\n\n",
            b"event: content_delta\ndata: []\n\n",
            b"data: " + b"x" * 65537 + b"\n\n",
        ]:
            with self.subTest(length=len(payload)), self.assertRaises(e.Rejected):
                list(hosted_suite.stream_events(io.BytesIO(payload)))

    def test_streamed_generation_cannot_pass_mock_error_empty_or_unfinished_content(
        self,
    ):
        import hosted_suite

        class Response:
            def __init__(self, payload):
                self.payload = payload

            def model_call(self, *args):
                return self.payload

        def frame(name, data):
            return f"event: {name}\ndata: {json.dumps(data)}\n\n".encode()

        start = {"model": {"real_inference": True, "backend": "cloudflare"}}
        good = (
            frame("message_start", start)
            + frame("content_delta", {"text": "Synthetic parsed content"})
            + frame("message_end", {})
        )
        self.assertEqual(
            hosted_suite.generation(Response(good), {})[0], "Synthetic parsed content"
        )
        for payload in [
            frame(
                "message_start", {"model": {"real_inference": False, "backend": "mock"}}
            )
            + frame("content_delta", {"text": "mock"})
            + frame("message_end", {}),
            frame("message_start", start)
            + frame("error", {})
            + frame("message_end", {}),
            frame("message_start", start) + frame("message_end", {}),
            frame("message_start", start)
            + frame("content_delta", {"text": 5})
            + frame("message_end", {}),
            frame("message_start", start) + frame("content_delta", {"text": "partial"}),
        ]:
            with self.subTest(length=len(payload)), self.assertRaises(e.Rejected):
                hosted_suite.generation(Response(payload), {})

    def test_critical_workflows_require_current_run_full_hosted_ui_and_real_model(self):
        import hosted

        self.assertEqual(
            hosted.PLATFORM_API_WORKFLOWS | hosted.PLATFORM_UI_WORKFLOWS,
            e.platform_workflow_check_names(),
        )
        suite = {
            "candidate_commit": SHA,
            "workflow_run_id": 40,
            "frontend_origin": "https://synthetic.vercel.app",
            "status": "PASS",
            "workflow_checks": {name: "PASS" for name in hosted.PLATFORM_API_WORKFLOWS},
            "model": {"real_inference": True, "backend": "cloudflare"},
        }
        ui = {
            "candidate_commit": SHA,
            "workflow_run_id": 40,
            "origin": "https://synthetic.vercel.app",
            "status": "PASS",
            "workflow_checks": {name: "PASS" for name in hosted.PLATFORM_UI_WORKFLOWS},
            "real_hosted": True,
            "synthetic_only": True,
            "browser": "chromium",
            "views": [
                {
                    "viewport": viewport,
                    "route": route,
                    "mode": mode,
                    "system_scheme": mode,
                    "overflow": False,
                    "axe_violations": 0,
                }
                for viewport in ["desktop", "tablet", "mobile"]
                for route in [
                    "/",
                    "/knowledge",
                    "/agents",
                    "/travel",
                    "/settings",
                    "/recovery",
                    "/invitation",
                ]
                for mode in ["light", "dark"]
            ],
        }

        def observed(a, b):
            return hosted.platform_workflow_evidence(
                a, b, SHA, "https://synthetic.vercel.app", 40
            )[0]

        self.assertTrue(all(value == "PASS" for value in observed(suite, ui).values()))
        for a, b in [(None, ui), (suite, None), (None, None)]:
            self.assertNotEqual(set(observed(a, b).values()), {"PASS"})
        for mutation in [
            lambda item: item.update(status="FAIL"),
            lambda item: item["views"].pop(),
            lambda item: item["views"][0].update(axe_violations=1),
            lambda item: item.update(real_hosted=False),
            lambda item: item["workflow_checks"].pop(
                "actual_stop_and_session_preservation"
            ),
        ]:
            partial = copy.deepcopy(ui)
            mutation(partial)
            self.assertNotEqual(set(observed(suite, partial).values()), {"PASS"})
        for record, key, value in [
            (ui, "workflow_run_id", 41),
            (ui, "candidate_commit", "f" * 40),
            (suite, "frontend_origin", "https://foreign.vercel.app"),
        ]:
            foreign = copy.deepcopy(record)
            foreign[key] = value
            with self.assertRaises(e.Rejected):
                observed(
                    foreign if record is suite else suite,
                    foreign if record is ui else ui,
                )
        mock = copy.deepcopy(suite)
        mock["model"].update(real_inference=False, backend="mock")
        self.assertEqual(observed(mock, ui)["real_context_and_history"], "FAIL")

    def test_trusted_stage_reader_rejects_legacy_or_partial_critical_pass(self):
        if e.PRODUCT != "onesa-ai-platform":
            return
        for key in ["critical_workflow_checks", "observed_model"]:
            record = copy.deepcopy(self.evidence["staging"]["record"])
            del record[key]
            with self.assertRaises(e.Rejected):
                e.verify_stage(record, SHA, FINGERPRINT, self.evidence["builds"], NOW)

    def test_hosted_suite_failure_code_preserves_status_without_request_or_secret_data(
        self,
    ):
        import urllib.error

        import hosted_suite

        for path in ["/api/v1/travel/trips", "/api/v1/agents/runs"]:
            error = hosted_suite.HostedRequestFailure(
                503,
                path,
                json.dumps(
                    {
                        "error": {
                            "code": "planning_failed",
                            "message": "private-provider-body",
                        }
                    }
                ).encode(),
            )
            self.assertEqual(
                hosted_suite.safe_suite_failure_code(error), "PLANNING_REJECTED"
            )
            self.assertEqual(
                hosted_suite.safe_suite_failure_reason(error), "PLANNING_REJECTED"
            )
            self.assertNotIn("private-provider-body", str(error))

        for error, code, reason in [
            (
                TimeoutError("private-value-never-log"),
                "REQUEST_TIMEOUT",
                "REQUEST_TIMEOUT",
            ),
            (
                urllib.error.URLError(TimeoutError("private-value-never-log")),
                "REQUEST_TIMEOUT",
                "REQUEST_TIMEOUT",
            ),
            (
                urllib.error.URLError("private-value-never-log"),
                "REQUEST_TRANSPORT",
                "REQUEST_TRANSPORT_ERROR",
            ),
        ]:
            self.assertEqual(hosted_suite.safe_suite_failure_code(error), code)
            self.assertEqual(hosted_suite.safe_suite_failure_reason(error), reason)

        self.assertEqual(
            hosted_suite.safe_suite_failure_reason(
                e.Rejected("Actual explicit tool execution failed")
            ),
            "EXPLICIT_TOOL_OUTCOME",
        )
        self.assertEqual(
            hosted_suite.safe_suite_failure_reason(
                e.Rejected("Real model tool planning did not complete")
            ),
            "MODEL_TOOL_PLAN_OUTCOME",
        )

        self.assertEqual(
            hosted_suite.safe_suite_failure_code(
                e.Rejected("Synthetic hosted request failed: POST auth HTTP 401")
            ),
            "HTTP_401",
        )
        self.assertEqual(
            hosted_suite.safe_suite_failure_code(
                e.Rejected("Secure session cookie missing")
            ),
            "SESSION_COOKIE",
        )
        marker = "private-value-never-log"
        self.assertEqual(
            hosted_suite.safe_suite_failure_code(e.Rejected(marker)), "HOSTED_CHECK"
        )
        self.assertNotIn(
            marker, hosted_suite.safe_suite_failure_code(ValueError(marker))
        )
        self.assertEqual(
            hosted_suite.safe_suite_failure_reason(
                e.Rejected("Hosted conversation context was not retained")
            ),
            "CONTEXT_FACT_MISSING",
        )
        for code in (
            "inference_unavailable",
            "inference_timeout",
            "generation_failed",
            "model_not_available",
            "invalid_inference_response",
        ):
            with self.subTest(code=code):
                self.assertEqual(
                    hosted_suite.safe_suite_failure_reason(
                        hosted_suite.HostedStreamFailure(code)
                    ),
                    "STREAM_ERROR_" + code.upper(),
                )
        self.assertEqual(
            hosted_suite.safe_suite_failure_reason(
                hosted_suite.HostedStreamFailure({"untrusted": marker})
            ),
            "STREAM_ERROR_UNCLASSIFIED_STREAM_ERROR",
        )
        self.assertEqual(
            hosted_suite.safe_suite_failure_reason(
                hosted_suite.HostedStreamFailure(marker)
            ),
            "STREAM_ERROR_UNCLASSIFIED_STREAM_ERROR",
        )
        self.assertNotIn(
            marker, hosted_suite.safe_suite_failure_reason(ValueError(marker))
        )

    def test_hosted_stream_details_accept_only_static_categories_and_bounded_codes(
        self,
    ):
        import hosted_suite

        reasons = {
            "provider_stream_error",
            "invalid_stream_json",
            "invalid_stream_shape",
            "invalid_stream_delta",
            "stream_terminated_early",
            "empty_model_response",
            "response_size_limit",
            "generation_lease_lost",
        }
        for reason in reasons:
            with self.subTest(reason=reason):
                error = hosted_suite.HostedStreamFailure(
                    "generation_failed", reason, 3040
                )
                self.assertEqual(
                    hosted_suite.safe_suite_failure_reason(error),
                    "STREAM_DETAIL_" + reason.upper(),
                )
                self.assertEqual(error.provider_error_code, 3040)
                self.assertEqual(error.code, "GENERATION_FAILED")
        for reason in [
            "PRIVATE-provider-message",
            {"private": "value"},
            [],
            True,
            None,
        ]:
            with self.subTest(reason_type=type(reason).__name__):
                error = hosted_suite.HostedStreamFailure("generation_failed", reason)
                self.assertIsNone(error.reason)
                self.assertEqual(
                    hosted_suite.safe_suite_failure_reason(error),
                    "STREAM_ERROR_GENERATION_FAILED",
                )
                self.assertNotIn("PRIVATE", str(error))
        for code in [True, -1, 1000000, "PRIVATE", {"private": "value"}]:
            with self.subTest(code_type=type(code).__name__):
                self.assertIsNone(
                    hosted_suite.HostedStreamFailure(
                        "generation_failed", "provider_stream_error", code
                    ).provider_error_code
                )

        class FailedClient:
            def model_call(self, *_args, **_kwargs):
                return b'event: message_start\ndata: {}\n\nevent: error\ndata: {"code":"generation_failed","failure_reason":"provider_stream_error","provider_error_code":3040,"message":"PRIVATE-provider-body"}\n\n'

        with self.assertRaises(hosted_suite.HostedStreamFailure) as caught:
            hosted_suite.generation(FailedClient(), {})
        self.assertEqual(
            hosted_suite.safe_suite_failure_reason(caught.exception),
            "STREAM_DETAIL_PROVIDER_STREAM_ERROR",
        )
        self.assertEqual(caught.exception.provider_error_code, 3040)
        self.assertNotIn("PRIVATE", str(caught.exception))

    def test_hosted_staging_exit_gate_rejects_failure_blocked_and_false_pass_records(
        self,
    ):
        import hosted

        hosted.require_stage_acceptance(self.evidence["staging"]["record"])
        for status in ["FAIL", "BLOCKED", "NOT TESTED", None]:
            with self.subTest(status=status), self.assertRaises(e.Rejected):
                hosted.require_stage_acceptance(
                    {"status": status, "checks": {"authentication": "PASS"}}
                )
        for checks in [
            {},
            {"authentication": "PASS"},
            {"authentication": "FAIL"},
            {"inference": "BLOCKED"},
            {"storage": "NOT TESTED"},
        ]:
            with self.subTest(checks=checks), self.assertRaises(e.Rejected):
                hosted.require_stage_acceptance({"status": "PASS", "checks": checks})

    def test_hosted_failure_codes_identify_known_gates_without_private_exception_text(
        self,
    ):
        import hosted

        self.assertEqual(
            hosted.safe_failure_code(e.Rejected("Render readback unavailable")),
            "RENDER_ACCESS",
        )
        self.assertEqual(
            hosted.safe_failure_code(
                e.Rejected(
                    "Staging synthetic probes require the identified isolated runtime database"
                )
            ),
            "STAGING_DATABASE_BINDING",
        )
        marker = "private-provider-value-never-log"
        for error in [
            e.Rejected(marker),
            KeyError(marker),
            ValueError(marker),
            TypeError(marker),
            OSError(marker),
        ]:
            self.assertNotIn(marker, hosted.safe_failure_code(error))
        self.assertEqual(hosted.safe_failure_code(e.Rejected(marker)), "VALIDATION")

    def test_registered_staging_entrypoint_keeps_commit_branch_event_and_owner_guards(
        self,
    ):
        stage = run(11, "deploy.yml", branch="staging")
        e.trusted_staging_run(None, stage, SHA)
        for key, value in [
            ("head_branch", "main"),
            ("head_branch", "dev"),
            ("head_sha", "f" * 40),
            ("event", "workflow_run"),
            ("path", ".github/workflows/repair-hosting.yml"),
        ]:
            rejected = dict(stage, **{key: value})
            with self.subTest(key=key, value=value), self.assertRaises(e.Rejected):
                e.trusted_staging_run(None, rejected, SHA)
        foreign = copy.deepcopy(stage)
        foreign["actor"]["login"] = "unapproved-operator"
        with self.assertRaises(e.Rejected):
            e.trusted_staging_run(None, foreign, SHA)

    def test_exact_approval_accepted_only_with_explicit_human_reviews(self):
        self.validate()
        self.assertEqual(self.evidence["CONTENT_LEGAL_APPROVED"], "BLOCKED")

    def test_negative_approval_fields(self):
        for key, bad in [
            ("candidate_commit", "f" * 40),
            ("source_sha256", "0" * 64),
            ("evidence_sha256", "0" * 64),
            ("builds_sha256", "0" * 64),
            ("content_version", "old"),
            ("repository", "attacker/repo"),
            ("target_environment", "Preview"),
            ("approver", "attacker"),
            ("operations_review", "blocked"),
            ("legal_review", "blocked"),
            ("decision", "revoke"),
            ("workflow_run_id", 99),
            ("approved_at", (NOW - timedelta(days=2)).isoformat()),
        ]:
            with self.subTest(key=key):
                original = self.approval[key]
                self.approval[key] = bad
                with self.assertRaises(e.Rejected):
                    self.validate()
                self.approval[key] = original

    def test_evidence_altered_after_approval(self):
        self.evidence["CODE_VERIFIED"] = "FAIL"
        with self.assertRaises(e.Rejected):
            self.validate()

    def test_stage_missing_failed_foreign_stale_build(self):
        original = self.evidence["staging"]["record"]
        for key, bad in [
            ("candidate_commit", "d" * 40),
            ("source_sha256", "0" * 64),
            ("builds_sha256", "0" * 64),
            ("verified_at", (NOW - timedelta(days=2)).isoformat()),
            ("vercel_deployment_id", None),
        ]:
            with self.subTest(key=key):
                stage = dict(original, **{key: bad})
                with self.assertRaises(e.Rejected):
                    e.verify_stage(
                        stage, SHA, FINGERPRINT, self.evidence["builds"], now=NOW
                    )
        for name in original["checks"]:
            stage = copy.deepcopy(original)
            stage["checks"][name] = "FAIL"
            if (
                name in {"streaming", "inference", "embeddings"}
                and e.PRODUCT != "onesa-ai-platform"
            ):
                continue
            with self.subTest(check=name), self.assertRaises(e.Rejected):
                e.verify_stage(
                    stage, SHA, FINGERPRINT, self.evidence["builds"], now=NOW
                )
        stage = copy.deepcopy(original)
        del stage["checks"]["authentication"]
        with self.assertRaises(e.Rejected):
            e.verify_stage(stage, SHA, FINGERPRINT, self.evidence["builds"], now=NOW)

    def test_untrusted_origin_rejected(self):
        for key, bad in [
            ("head_sha", "d" * 40),
            ("head_branch", "feature/attacker"),
            ("path", ".github/workflows/untrusted.yml"),
            ("event", "pull_request"),
            ("run_attempt", 2),
            ("conclusion", "failure"),
            ("actor", {"login": "attacker"}),
            ("head_repository", {"full_name": "attacker/repo"}),
        ]:
            with self.subTest(key=key), self.assertRaises(e.Rejected):
                e.trusted_run(
                    dict(self.run, **{key: bad}), "release-review.yml", SHA, {"main"}
                )

    def test_zip_integrity_and_no_extraction(self):
        def archive(name, data):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as bundle:
                bundle.writestr(name, json.dumps(data))
            return buffer.getvalue()

        data = archive("record.json", self.evidence)
        self.assertEqual(
            e.decode_artifact(data, "sha256:" + hashlib.sha256(data).hexdigest()),
            self.evidence,
        )
        with self.assertRaises(e.Rejected):
            e.decode_artifact(data, "sha256:" + "0" * 64)
        data = archive("../../script.py", self.evidence)
        with self.assertRaises(e.Rejected):
            e.decode_artifact(data, "sha256:" + hashlib.sha256(data).hexdigest())

    def test_ci_failure_missing_security_not_pass(self):
        class API:
            def runs(self, workflow, sha):
                return [run(10, workflow, event="push")]

            def jobs(self, workflow):
                names = (
                    e.POLICY["jobs"]
                    if workflow["path"].endswith(e.POLICY["ci"])
                    else ["publication-hygiene"]
                )
                return [
                    {
                        "name": name,
                        "conclusion": "failure" if name == names[0] else "success",
                        "html_url": "https://github.com/synthetic",
                        "steps": [],
                    }
                    for name in names
                ]

        status, _ = e.checked_ci(API(), SHA)
        self.assertEqual(status, "FAIL")

        class Missing(API):
            def jobs(self, workflow):
                return []

        status, _ = e.checked_ci(Missing(), SHA)
        self.assertEqual(status, "BLOCKED")

    def test_missing_push_can_use_full_exact_owner_dispatched_ci(self):
        class API:
            def runs(self, workflow, sha):
                return [run(10, workflow, event="workflow_dispatch")]

            def jobs(self, workflow):
                names = (
                    e.POLICY["jobs"]
                    if workflow["path"].endswith(e.POLICY["ci"])
                    else ["publication-hygiene"]
                )
                return [
                    {
                        "name": name,
                        "conclusion": "success",
                        "html_url": "https://github.com/synthetic",
                        "steps": [
                            {
                                "name": "Release requirement: full tests",
                                "conclusion": "success",
                            }
                        ],
                    }
                    for name in names
                ]

        status, references = e.checked_ci(API(), SHA)
        self.assertEqual(status, "PASS")
        self.assertTrue(
            all(r["source_event"] == "workflow_dispatch" for r in references)
        )
        for changes in [
            {"actor": {"login": "other"}},
            {"triggering_actor": {"login": "other"}},
            {"head_sha": "b" * 40},
            {"head_repository": {"full_name": "other/repository"}},
            {"run_attempt": 2},
            {"path": ".github/workflows/other.yml"},
        ]:

            class Untrusted(API):
                def runs(self, workflow, sha, changes=changes):
                    return [{**run(10, workflow), **changes}]

            with self.subTest(changes=changes), self.assertRaises(e.Rejected):
                e.checked_ci(Untrusted(), SHA)

        class Incomplete(API):
            def jobs(self, workflow):
                return []

        self.assertEqual(e.checked_ci(Incomplete(), SHA)[0], "BLOCKED")

        class SkippedRequirement(API):
            def jobs(self, workflow):
                result = super().jobs(workflow)
                result[0]["steps"][0]["conclusion"] = "skipped"
                return result

        with self.assertRaises(e.Rejected):
            e.checked_ci(SkippedRequirement(), SHA)

        for conclusion in ["failure", "cancelled", None]:

            class ExistingPush(API):
                def runs(self, workflow, sha, conclusion=conclusion):
                    return [
                        run(11, workflow),
                        {**run(10, workflow, event="push"), "conclusion": conclusion},
                    ]

            with self.subTest(push_conclusion=conclusion):
                self.assertNotEqual(e.checked_ci(ExistingPush(), SHA)[0], "PASS")

    def test_source_hash_is_legacy_algorithm(self):
        if e.PRODUCT == "onesa-ai-robot":
            return
        spec = e.importlib.util.spec_from_file_location(
            "original", e.ROOT / "scripts/release/qualify.py"
        )
        module = e.importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(e.source_hash(), module.source_hash())

    def test_freshness_expired_and_future(self):
        self.assertTrue(e.fresh(STAMP, NOW))
        self.assertFalse(e.fresh(STAMP, NOW + timedelta(days=1)))
        self.assertFalse(e.fresh(STAMP, NOW - timedelta(seconds=1)))

    def test_protection_cannot_be_assumed(self):
        github = e.GitHub()
        with (
            patch.object(
                github, "api", return_value={"protected": False, "commit": {"sha": SHA}}
            ),
            self.assertRaises(e.Rejected),
        ):
            github.protected_main(SHA)

    def test_security_blocker_and_artifact_mismatch(self):
        class API:
            def run(self, identifier):
                return run(identifier, e.POLICY["ci"], event="push")

            def artifact(self, workflow, name):
                return {
                    "repository": e.REPOSITORY,
                    "candidate_commit": SHA,
                    "image_digest": "sha256:" + "c" * 64,
                    "security": "FAIL",
                }, {}

        with self.assertRaises(e.Rejected):
            e.artifacts_for_ci(API(), [{"workflow": e.POLICY["ci"], "run_id": 10}])

    def test_superseded_or_pending_approval_rejects(self):
        class API:
            def protected_main(self, sha):
                pass

            def runs(self, workflow, sha):
                return [run(41, workflow), run(40, workflow)]

        with self.assertRaises(e.Rejected):
            e.promote(API(), SHA, 40)

    def test_hosted_staging_unavailable_rejects(self):
        if e.PRODUCT == "onesa-ai-robot":
            return
        import hosted

        record = self.evidence["staging"]["record"]
        record.update(
            {
                "render_service_id": hosted.STAGING_SERVICES[e.PRODUCT],
                "backend_origin": hosted.BACKEND_ORIGINS[e.PRODUCT],
                "frontend_origin": "https://synthetic.vercel.app",
            }
        )
        with (
            patch.object(hosted, "render", side_effect=e.Rejected("Unavailable")),
            patch.object(hosted, "verify_stage", return_value="PASS"),
            self.assertRaises(e.Rejected),
        ):
            hosted.recheck(self.evidence)

    def test_reviewed_build_encryption_roundtrip_and_tampering(self):
        if e.PRODUCT == "onesa-ai-robot":
            return
        import os
        import subprocess

        script = e.ROOT / "scripts/release/bundle.mjs"
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / ".vercel/output").mkdir(parents=True)
            (directory / ".vercel/output/config.json").write_text('{"version":3}')
            env = {
                **os.environ,
                "RELEASE_BUILD_KEY": "1" * 64,
                "GITHUB_SHA": SHA,
                "GITHUB_REPOSITORY": e.REPOSITORY,
                "GITHUB_RUN_ID": "50",
            }
            packed = subprocess.run(
                ["node", str(script), "pack", "bundle"],
                cwd=directory,
                env=env,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                packed.returncode, 0, "Synthetic Vercel bundle should encrypt"
            )
            blob = (directory / "bundle/bundle.enc").read_bytes()
            self.assertNotIn(b'"version":3', blob)
            (directory / ".vercel/output/config.json").unlink()
            restored = subprocess.run(
                ["node", str(script), "unpack", "bundle"],
                cwd=directory,
                env=env,
                capture_output=True,
                check=False,
            )
            self.assertEqual(restored.returncode, 0)
            self.assertEqual(
                (directory / ".vercel/output/config.json").read_text(), '{"version":3}'
            )
            for changed in [{"RELEASE_BUILD_KEY": "2" * 64}, {"GITHUB_SHA": "f" * 40}]:
                rejected = subprocess.run(
                    ["node", str(script), "unpack", "bundle"],
                    cwd=directory,
                    env={**env, **changed},
                    capture_output=True,
                    check=False,
                )
                self.assertNotEqual(rejected.returncode, 0)
            (directory / "bundle/bundle.enc").write_bytes(
                blob[:-1] + bytes([blob[-1] ^ 1])
            )
            rejected = subprocess.run(
                ["node", str(script), "unpack", "bundle"],
                cwd=directory,
                env=env,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)

    def test_generator_never_issues_human_or_hardware_approval(self):
        class API:
            def runs(self, workflow, sha):
                return []

        with patch.object(e, "source_hash", return_value=FINGERPRINT):
            record = e.generate(API(), SHA, run(30, "release-qualification.yml"))
        self.assertEqual(record["CODE_VERIFIED"], "BLOCKED")
        self.assertEqual(record["STAGING_VERIFIED"], "BLOCKED")
        self.assertEqual(record["OPERATIONS_VERIFIED"], "BLOCKED")
        self.assertEqual(record["CONTENT_LEGAL_APPROVED"], "BLOCKED")
        if e.PRODUCT == "onesa-ai-robot":
            self.assertEqual(record["ROS2_VERIFIED"], "NOT TESTED")
            self.assertEqual(record["PHYSICAL_HARDWARE_READY"], "BLOCKED")

    def test_missing_synthetic_credentials_remain_blocked(self):
        if e.PRODUCT == "onesa-ai-robot":
            return
        import hosted_suite

        with patch.dict("os.environ", {"GITHUB_SHA": SHA}, clear=True):
            record = hosted_suite.run_suite("https://synthetic.vercel.app")
        self.assertEqual(record["status"], "BLOCKED")
        self.assertNotIn("PASS", record["checks"].values())

    def test_synthetic_suite_failure_cannot_pass(self):
        if e.PRODUCT == "onesa-ai-robot":
            return
        import hosted_suite

        users = [
            {"email": "first@example.com", "password": "synthetic-only"},
            {"email": "second@example.com", "password": "synthetic-only"},
        ]
        config = {
            "scope": "approved-synthetic-staging",
            "project_id": "prj_synthetic",
            "users": users,
        }

        class Unavailable:
            def __init__(self, origin):
                pass

            def login(self, user):
                raise e.Rejected("Synthetic service unavailable")

        with (
            patch.dict(
                "os.environ",
                {
                    "GITHUB_SHA": SHA,
                    "VERCEL_PROJECT_ID": "prj_synthetic",
                    "STAGING_FIXTURES_JSON": json.dumps(config),
                },
                clear=True,
            ),
            patch.object(hosted_suite, "Session", Unavailable),
        ):
            record = hosted_suite.run_suite("https://synthetic.vercel.app")
        self.assertEqual(record["status"], "FAIL")
        self.assertEqual(record["checks"]["authentication"], "FAIL")
        self.assertEqual(record["checks"]["storage_integrations"], "BLOCKED")

    def test_foreign_fixture_project_rejected_before_login(self):
        if e.PRODUCT == "onesa-ai-robot":
            return
        import hosted_suite

        config = {
            "scope": "approved-synthetic-staging",
            "project_id": "prj_foreign",
            "users": [],
        }
        with (
            patch.dict(
                "os.environ",
                {
                    "GITHUB_SHA": SHA,
                    "VERCEL_PROJECT_ID": "prj_synthetic",
                    "STAGING_FIXTURES_JSON": json.dumps(config),
                },
                clear=True,
            ),
            self.assertRaises(e.Rejected),
        ):
            hosted_suite.run_suite("https://synthetic.vercel.app")

    def test_production_metrics_require_observed_signals_and_no_server_errors(self):
        if e.PRODUCT == "onesa-ai-robot":
            self.skipTest("Robot has no production promotion")
        import hosted

        key = "METRICS_TOKEN" if e.PRODUCT.endswith("portal") else "ONESA_METRICS_TOKEN"
        prefix = (
            "onesa_portal_http_requests_total"
            if e.PRODUCT.endswith("portal")
            else "onesa_http_requests_total"
        )
        good = (prefix + '{status="200"} 2\n').encode()
        with (
            patch.dict("os.environ", {"RENDER_API_KEY": "synthetic-only"}, clear=True),
            patch.object(
                hosted,
                "provider",
                return_value=[
                    {"envVar": {"key": key, "value": "synthetic-metrics-token"}}
                ],
            ),
            patch.object(hosted, "request", return_value=(200, good)),
        ):
            observed = hosted.production_metrics(
                "https://synthetic.onrender.com", "srv-synthetic"
            )
        self.assertEqual(observed["application_errors"], "PASS")
        self.assertEqual(observed["monitoring_signals"], "PASS")
        bad = good + (prefix + '{status="500"} 1\n').encode()
        with (
            patch.dict("os.environ", {"RENDER_API_KEY": "synthetic-only"}, clear=True),
            patch.object(
                hosted,
                "provider",
                return_value=[
                    {"envVar": {"key": key, "value": "synthetic-metrics-token"}}
                ],
            ),
            patch.object(hosted, "request", return_value=(200, bad)),
        ):
            observed = hosted.production_metrics(
                "https://synthetic.onrender.com", "srv-synthetic"
            )
        self.assertEqual(observed["application_errors"], "FAIL")
        with (
            patch.dict("os.environ", {"RENDER_API_KEY": "synthetic-only"}, clear=True),
            patch.object(hosted, "provider", return_value=[]),
        ):
            observed = hosted.production_metrics(
                "https://synthetic.onrender.com", "srv-synthetic"
            )
        self.assertEqual(observed["monitoring_signals"], "BLOCKED")

    def test_missing_production_fixture_never_passes_smoke(self):
        if e.PRODUCT == "onesa-ai-robot":
            self.skipTest("Robot has no production promotion")
        import hosted_suite

        with patch.dict("os.environ", {}, clear=True):
            observed = hosted_suite.production_probes("https://synthetic.vercel.app")
        self.assertNotIn("PASS", observed.values())

    def test_illustrative_dry_run_end_to_end(self):
        # Fixed synthetic timestamps/checks: this records software behavior, not hosted acceptance.
        class API:
            def protected_main(self, sha):
                e.require(sha == SHA, "Wrong main")

            def runs(self, workflow, sha):
                return [run(40, workflow)]

            def run(self, identifier):
                if identifier == 50:
                    return run(50, "release-build.yml")
                return run(
                    identifier,
                    "release-qualification.yml"
                    if identifier == 30
                    else "release-staging.yml",
                    branch="main" if identifier == 30 else e.POLICY["staging_branch"],
                )

            def artifact(inner, workflow, name, **kwargs):
                if name == "production-build-manifest":
                    return self.evidence["frontend_build"]["manifest"], self.evidence[
                        "frontend_build"
                    ]["artifact"]
                if name == "production-build-encrypted":
                    return b"synthetic-ciphertext", self.evidence["frontend_build"][
                        "bundle_artifact"
                    ]
                if name == "release-approval":
                    return self.approval, {}
                if name == "release-qualification":
                    return self.evidence, self.origin
                return self.evidence["staging"]["record"], self.evidence["staging"][
                    "artifact"
                ]

            def api(self, path):
                return {"state": "open", "user": {"login": e.OWNER}}

        if e.PRODUCT == "onesa-ai-robot":
            return
        with (
            patch.object(e, "source_hash", return_value=FINGERPRINT),
            patch.object(e, "fresh", return_value=True),
            patch.object(e, "checked_ci", return_value=("PASS", [])),
            patch.object(e, "artifacts_for_ci", return_value=self.evidence["builds"]),
        ):
            approved = e.promote(API(), SHA, 40)
        self.assertEqual(approved["qualification_status"], "APPROVED")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.json"
            e.save(approved, path)
            self.assertEqual(
                json.loads(path.read_text())["approval_provenance"]["approver"], e.OWNER
            )


if __name__ == "__main__":
    unittest.main()
