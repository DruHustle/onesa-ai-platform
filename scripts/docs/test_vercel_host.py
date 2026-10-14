"""A docs release must match its dedicated project and exact verified revision."""

import io
import json
import os
import runpy
import sys
import unittest
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
            patch("urllib.request.urlopen", side_effect=response),
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


if __name__ == "__main__":
    unittest.main()
