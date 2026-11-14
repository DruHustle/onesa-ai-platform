"""Early probe diagnostics cannot expose credentials or become qualification evidence."""

import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import oracle_ai_probe as p


class ProbeBoundaryTests(unittest.TestCase):
    def test_early_http_and_validation_failures_are_scoped_and_redacted(self):
        for error, code, status in [
            (
                urllib.error.HTTPError(
                    "https://fixture.invalid/?token=synthetic-secret",
                    503,
                    "private body",
                    {},
                    None,
                ),
                None,
                503,
            ),
            (p.Refused("PROBE_BINDING"), "PROBE_BINDING", None),
            (p.Refused("postgresql://synthetic-secret@fixture"), None, None),
            (RuntimeError("synthetic-secret"), None, None),
        ]:
            with (
                self.subTest(error=type(error).__name__),
                tempfile.TemporaryDirectory() as directory,
                patch.object(p, "OUTPUT", Path(directory)),
            ):
                request = {
                    "binding": {
                        "repository": "DruHustle/onesa-ai-platform",
                        "component": "api",
                        "candidate_commit": "a" * 40,
                        "unexpected": "synthetic-secret",
                    },
                    "operation_id": str(uuid4()),
                }
                p.record_boundary_failure("staging", request, error)
                raw = (Path(directory) / "failure.json").read_text()
                value = json.loads(raw)
                self.assertNotIn("synthetic-secret", raw)
                self.assertEqual(value["status"], "FAILED_NOT_QUALIFIED")
                self.assertTrue(value["diagnostic_only"])
                self.assertEqual(value["failure_code"], code)
                self.assertEqual(value["http_status"], status)
                p.record_boundary_failure(
                    "staging", request, p.Refused("DIFFERENT_FAILURE")
                )
                self.assertEqual((Path(directory) / "failure.json").read_text(), raw)

    def test_foreign_scope_and_invalid_identifiers_create_no_diagnostic(self):
        for repo, operation, environment in [
            ("foreign/repo", str(uuid4()), "staging"),
            ("DruHustle/onesa-ai-platform", "not-a-uuid", "staging"),
            ("DruHustle/onesa-ai-platform", str(uuid4()), "foreign"),
        ]:
            with (
                tempfile.TemporaryDirectory() as directory,
                patch.object(p, "OUTPUT", Path(directory)),
            ):
                p.record_boundary_failure(
                    environment,
                    {
                        "binding": {
                            "repository": repo,
                            "component": "api",
                            "candidate_commit": "a" * 40,
                        },
                        "operation_id": operation,
                    },
                    p.Refused("SYNTHETIC"),
                )
                self.assertFalse((Path(directory) / "failure.json").exists())
