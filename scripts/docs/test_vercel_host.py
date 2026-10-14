"""A docs release must match its dedicated project and exact verified revision."""

import http.server
import io
import json
import os
import runpy
import sys
import tempfile
import threading
import unittest
import urllib.request
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("vercel_host.py")
REVISION = "a" * 40
PROJECT = "prj_Dtm2zO8sQQFqmnospPZgxbCi9Bbr"


class DeploymentIdentityTests(unittest.TestCase):
    def run_check(self, project, deployment):
        requests = []

        def response(request, timeout):
            requests.append(request)
            payload = project if "/projects/" in request.full_url else deployment
            return io.BytesIO(json.dumps(payload).encode())

        env = {
            "VERCEL_TOKEN": "test",
            "VERCEL_ORG_ID": "team_ZCFijEEeYUAKYka9HEyEeyGm",
            "DOCS_DEPLOYMENT_URL": "https://onesa-docs-test.vercel.app",
            "GITHUB_SHA": REVISION,
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(sys, "argv", [str(SCRIPT), "verify-deployment"]),
            patch("urllib.request.OpenerDirector.open", side_effect=response),
            redirect_stdout(io.StringIO()) as output,
        ):
            try:
                runpy.run_path(str(SCRIPT), run_name="__main__")
            except SystemExit as error:
                return error.code, output.getvalue(), requests
        self.fail("The operator check must terminate with an explicit result")

    def test_verified_docs_revision_is_read_only(self):
        code, output, requests = self.run_check(
            {"name": "onesa-docs", "id": PROJECT},
            {
                "id": "dpl_test",
                "projectId": PROJECT,
                "readyState": "READY",
                "target": None,
                "meta": {"onesaSourceRevision": REVISION},
            },
        )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["sourceRevision"], REVISION)
        self.assertEqual(json.loads(output)["projectId"], PROJECT)
        self.assertIsNone(json.loads(output)["target"])
        self.assertTrue(all(r.get_method() == "GET" for r in requests))

    def test_different_application_project_is_rejected_before_deployment_lookup(self):
        code, _, requests = self.run_check(
            {"name": "onesa-ai-platform", "id": "prj_application"}, {}
        )
        self.assertIn("differently named", code)
        self.assertEqual(len(requests), 1)

    def test_unready_wrong_project_and_wrong_revision_are_rejected(self):
        for fields in [
            {"readyState": "ERROR"},
            {"projectId": "prj_application"},
            {"meta": {"onesaSourceRevision": "b" * 40}},
        ]:
            deployment = {
                "projectId": PROJECT,
                "readyState": "READY",
                "target": None,
                "meta": {"onesaSourceRevision": REVISION},
                **fields,
            }
            with self.subTest(fields=fields):
                code, _, _ = self.run_check(
                    {"name": "onesa-docs", "id": PROJECT}, deployment
                )
                self.assertIn("verification failed", code)

    def test_same_name_foreign_project_is_rejected_before_lookup(self):
        code, _, requests = self.run_check(
            {"name": "onesa-docs", "id": "prj_other"}, {}
        )
        self.assertIn("scope mismatch", code)
        self.assertEqual(len(requests), 1)

    def test_absent_provider_target_is_not_reinterpreted_as_preview(self):
        code, _, _ = self.run_check(
            {"name": "onesa-docs", "id": PROJECT},
            {
                "id": "dpl_test",
                "projectId": PROJECT,
                "readyState": "READY",
                "meta": {"onesaSourceRevision": REVISION},
            },
        )
        self.assertIn("verification failed", code)


class PreviewCredentialTests(unittest.TestCase):
    def check(self, project, folder):
        requests = []

        def response(request, timeout):
            requests.append(request)
            return io.BytesIO(json.dumps(project).encode())

        env = {
            "VERCEL_TOKEN": "synthetic-only",
            "VERCEL_ORG_ID": "team_ZCFijEEeYUAKYka9HEyEeyGm",
            "RUNNER_TEMP": str(folder),
            "DOCS_PREVIEW_ACCESS_FILE": str(folder / "access.json"),
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(sys, "argv", [str(SCRIPT), "prepare-preview-access"]),
            patch("urllib.request.OpenerDirector.open", side_effect=response),
            redirect_stdout(io.StringIO()) as output,
        ):
            try:
                runpy.run_path(str(SCRIPT), run_name="__main__")
            except SystemExit as error:
                return error.code, output.getvalue(), requests
        self.fail("Explicit terminal result required")

    def test_existing_named_project_credential_is_private_read_only_and_not_logged(
        self,
    ):
        credential_value = "synthetic-only-credential-value"
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp).resolve()
            code, output, requests = self.check(
                {
                    "name": "onesa-docs",
                    "id": PROJECT,
                    "protectionBypass": {
                        credential_value: {
                            "scope": "automation-bypass",
                            "note": "onesa-docs-preview-qualification-v1",
                        }
                    },
                },
                folder,
            )
            self.assertEqual(code, 0)
            self.assertNotIn(credential_value, output)
            self.assertEqual(
                json.loads((folder / "access.json").read_text()),
                {"projectId": PROJECT, "secret": credential_value},
            )
            self.assertEqual((folder / "access.json").stat().st_mode & 0o077, 0)
            self.assertEqual(len(requests), 1)
            self.assertEqual(requests[0].get_method(), "GET")

    def test_missing_wrong_scope_wrong_note_multiple_and_foreign_credentials_do_not_write(
        self,
    ):
        good = {
            "scope": "automation-bypass",
            "note": "onesa-docs-preview-qualification-v1",
        }
        for project in [
            {"name": "onesa-docs", "id": PROJECT},
            {
                "name": "onesa-docs",
                "id": PROJECT,
                "protectionBypass": {
                    "synthetic-only-value": {**good, "scope": "shareable-link"}
                },
            },
            {
                "name": "onesa-docs",
                "id": PROJECT,
                "protectionBypass": {
                    "synthetic-only-value": {**good, "note": "another-owner-tool"}
                },
            },
            {
                "name": "onesa-docs",
                "id": PROJECT,
                "protectionBypass": {
                    "synthetic-only-value-one": good,
                    "synthetic-only-value-two": good,
                },
            },
            {
                "name": "onesa-docs",
                "id": "prj_other",
                "protectionBypass": {"synthetic-only-value": good},
            },
        ]:
            with self.subTest(project=project), tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp).resolve()
                code, _, requests = self.check(project, folder)
                self.assertNotEqual(code, 0)
                self.assertFalse((folder / "access.json").exists())
                self.assertTrue(all(r.get_method() == "GET" for r in requests))

    def test_existing_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp).resolve()
            (folder / "access.json").write_text("concurrent-owner-data")
            code, _, _ = self.check(
                {
                    "name": "onesa-docs",
                    "id": PROJECT,
                    "protectionBypass": {
                        "synthetic-only-credential-value": {
                            "scope": "automation-bypass",
                            "note": "onesa-docs-preview-qualification-v1",
                        }
                    },
                },
                folder,
            )
            self.assertNotEqual(code, 0)
            self.assertEqual(
                (folder / "access.json").read_text(), "concurrent-owner-data"
            )


class ProviderTransportTests(unittest.TestCase):
    def test_actual_redirect_never_forwards_provider_bearer(self):
        foreign_headers = []

        class Foreign(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                foreign_headers.append(self.headers.get("Authorization"))
                self.send_response(200)
                self.end_headers()

            def log_message(self, *args):
                pass

        foreign = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Foreign)

        class Provider(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header(
                    "Location", "http://127.0.0.1:" + str(foreign.server_port) + "/"
                )
                self.end_headers()

            def log_message(self, *args):
                pass

        provider = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Provider)
        threads = [
            threading.Thread(target=server.serve_forever, daemon=True)
            for server in [provider, foreign]
        ]
        for thread in threads:
            thread.start()
        actual_request = urllib.request.Request

        def loopback_request(url, *args, **kwargs):
            self.assertTrue(
                url.startswith("https://api.vercel.com/v9/projects/onesa-docs?teamId=")
            )
            return actual_request(
                "http://127.0.0.1:" + str(provider.server_port) + "/", *args, **kwargs
            )

        try:
            with (
                patch.dict(
                    os.environ,
                    {
                        "VERCEL_TOKEN": "synthetic-only",
                        "VERCEL_ORG_ID": "team_ZCFijEEeYUAKYka9HEyEeyGm",
                    },
                    clear=True,
                ),
                patch.object(sys, "argv", [str(SCRIPT), "prepare-preview-access"]),
                patch("urllib.request.Request", side_effect=loopback_request),
                redirect_stdout(io.StringIO()) as output,
                self.assertRaises(SystemExit) as failure,
            ):
                runpy.run_path(str(SCRIPT), run_name="__main__")
            self.assertIn("HTTP 302", str(failure.exception))
            self.assertNotIn("synthetic-only", str(failure.exception))
            self.assertEqual(output.getvalue(), "")
            self.assertEqual(foreign_headers, [])
        finally:
            for server in [provider, foreign]:
                server.shutdown()
                server.server_close()
            for thread in threads:
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
