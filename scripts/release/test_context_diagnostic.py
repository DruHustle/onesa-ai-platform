"""No hosted requests: diagnostic target, source and qualification boundaries."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import context_diagnostic as diagnostic
from evidence import ROOT, Rejected

SHA = "a" * 40
ORIGIN = "https://onesa-ai-platform-synthetic-druhustles-projects.vercel.app"


class ContextDiagnosticTests(unittest.TestCase):
    def test_only_an_owner_dispatched_first_attempt_temporary_staging_run(self):
        env = {
            "GITHUB_REPOSITORY": "DruHustle/onesa-ai-platform",
            "GITHUB_REF": "refs/heads/staging",
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_ACTOR": "DruHustle",
            "GITHUB_TRIGGERING_ACTOR": "DruHustle",
            "RUNNER_ENVIRONMENT": "github-hosted",
            "GITHUB_RUN_ATTEMPT": "1",
            "STAGING_FIXTURE_MODE": "temporary",
            "AI_CONTEXT_DIAGNOSTIC": "true",
            "AI_DIAGNOSTIC_DEPLOYED_COMMIT": SHA,
        }
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(diagnostic.execution_context(), SHA)
            for key, value in [
                ("GITHUB_REF", "refs/heads/main"),
                ("GITHUB_EVENT_NAME", "workflow_call"),
                ("GITHUB_ACTOR", "outsider"),
                ("GITHUB_TRIGGERING_ACTOR", "outsider"),
                ("RUNNER_ENVIRONMENT", "self-hosted"),
                ("GITHUB_RUN_ATTEMPT", "2"),
                ("STAGING_FIXTURE_MODE", "provided"),
                ("AI_CONTEXT_DIAGNOSTIC", "false"),
                ("AI_DIAGNOSTIC_DEPLOYED_COMMIT", "main"),
            ]:
                with (
                    self.subTest(key=key),
                    patch.dict(os.environ, {key: value}),
                    self.assertRaises(Rejected),
                ):
                    diagnostic.execution_context()

    def test_diagnostic_origin_cannot_target_production_or_another_product(self):
        self.assertEqual(diagnostic.preview_origin_value(ORIGIN), ORIGIN)
        for origin in [
            "https://platform.onesa.eu",
            "http://localhost:3100",
            ORIGIN + "/",
            ORIGIN + "?token=value",
            "https://onesa-docs-synthetic-druhustles-projects.vercel.app",
            "https://user@onesa-ai-platform-synthetic-druhustles-projects.vercel.app",
        ]:
            with self.subTest(origin=origin), self.assertRaises(Rejected):
                diagnostic.preview_origin_value(origin)

    def test_wrong_live_source_active_deployment_and_application_drift_reject(self):
        env = {
            "RENDER_SERVICE_ID": diagnostic.SERVICE,
            "VERCEL_PROJECT_ID": diagnostic.PROJECT,
            "RENDER_API_KEY": "synthetic",
            "GITHUB_SHA": "b" * 40,
        }
        verified = {
            "settings": {
                "ONESA_ENVIRONMENT": "staging",
                "ONESA_MODEL_BACKEND": "cloudflare",
                "ONESA_MODEL_NAME": diagnostic.MODEL,
                "ONESA_MODEL_BASE_URL": diagnostic.MODEL_BASE,
                "ONESA_PUBLIC_ORIGIN": ORIGIN,
            }
        }
        good = [
            {"deploy": {"id": "dep-synthetic", "status": "live", "commit": {"id": SHA}}}
        ]
        for rows, identities, accepted in [
            (good, ["same"] * 8, True),
            (
                [
                    {
                        "deploy": {
                            "id": "dep-wrong",
                            "status": "live",
                            "commit": {"id": "c" * 40},
                        }
                    }
                ],
                ["same"] * 8,
                False,
            ),
            (good + [{"deploy": {"status": "queued"}}], ["same"] * 8, False),
            (good, ["before", "after"], False),
        ]:
            with (
                patch.dict(os.environ, env),
                patch.object(diagnostic, "execution_context", return_value=SHA),
                patch.object(diagnostic, "preflight", return_value=verified),
                patch.object(diagnostic, "provider", return_value=rows),
                patch.object(diagnostic, "source_identity", side_effect=identities),
                patch.object(diagnostic, "frontend") as frontend,
            ):
                if accepted:
                    self.assertEqual(
                        diagnostic.verify_target(), (SHA, ORIGIN, "dep-synthetic")
                    )
                    frontend.assert_called_once_with(ORIGIN, SHA, "Staging")
                else:
                    with self.assertRaises(Rejected):
                        diagnostic.verify_target()
                    frontend.assert_not_called()

    def test_diagnostic_never_runs_deployment_or_emits_qualification(self):
        text = (ROOT / ".github/workflows/release-staging.yml").read_text()
        for title in [
            "Reuse the exact-source protected native Git Preview",
            "Bind only the approved staging API origin",
            "Deploy exact staging backend source",
            "Verify authenticated synthetic workflows",
            "Verify actual protected interfaces",
            "Release requirement: actual hosted staging acceptance",
        ]:
            step = text[text.index(title) :].split("\n    - ", 1)[0]
            self.assertIn("inputs.context_diagnostic != true", step)
        self.assertIn("if: always() && inputs.fixture_mode != 'provided'", text)
        self.assertIn("fixture_lifecycle.py cleanup", text)
        source = (ROOT / "scripts/release/context_diagnostic.py").read_text()
        self.assertNotIn("deploy_render", source)
        self.assertIn('"qualification_established": False', source)
        self.assertIn('"maximum_inference_requests": 2', source)
        self.assertNotIn("STAGING_VERIFIED", source)
        # The artifact is deliberately distinct from release evidence.
        self.assertIn("name: staging-context-diagnostic", text)

    def test_failed_first_generation_stops_model_calls_and_logs_out_owned_sessions(
        self,
    ):
        class SyntheticSession:
            def __init__(self, origin):
                self.calls = []

            def login(self, user):
                return None

            def call(self, method, path, body=None, expected=200):
                self.calls.append((method, path))
                if method == "POST" and path == "/api/v1/conversations":
                    return {"id": "synthetic"}
                if method == "GET" and expected != 404:
                    return {"messages": [{"role": "assistant", "status": "failed"}]}
                return {}

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "fixtures.json")
            path.write_text(json.dumps({"users": [{}, {}]}))
            path.chmod(0o600)
            sessions = [SyntheticSession(ORIGIN), SyntheticSession(ORIGIN)]
            records = []
            with (
                patch.dict(os.environ, {"GITHUB_SHA": SHA, "GITHUB_RUN_ID": "123"}),
                patch.object(
                    diagnostic,
                    "verify_target",
                    return_value=(SHA, ORIGIN, "dep-synthetic"),
                ),
                patch.object(diagnostic, "file_path", return_value=path),
                patch.object(diagnostic, "validate_owned"),
                patch.object(
                    diagnostic,
                    "parse_fixtures",
                    side_effect=lambda text, *_: json.loads(text),
                ),
                patch.object(diagnostic, "Session", side_effect=sessions),
                patch.object(
                    diagnostic,
                    "save",
                    side_effect=lambda value: records.append(
                        json.loads(json.dumps(value))
                    ),
                ),
                patch.object(
                    diagnostic,
                    "generation",
                    side_effect=Rejected("Hosted model returned empty content"),
                ) as generate,
                self.assertRaises(Rejected),
            ):
                diagnostic.probe()
            self.assertEqual(generate.call_count, 1)
            self.assertEqual(records[-1]["inference_requests_submitted"], 1)
            self.assertEqual(records[-1]["result"], "DIAGNOSTIC_FAILED")
            self.assertEqual(
                records[-1]["persisted_message_outcomes"],
                [{"role": "assistant", "status": "failed"}],
            )
            self.assertTrue(
                all(
                    ("POST", "/api/v1/auth/logout") in session.calls
                    for session in sessions
                )
            )
            self.assertFalse(records[-1]["qualification_established"])


if __name__ == "__main__":
    unittest.main()
