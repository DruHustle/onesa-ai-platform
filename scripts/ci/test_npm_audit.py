"""Advisory transport recovery must never turn missing data or findings into PASS."""

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import npm_audit


def report(severity=None):
    counts = {key: int(key == severity) for key in npm_audit.LEVELS}
    return json.dumps(
        {
            "auditReportVersion": 2,
            "vulnerabilities": {"synthetic-package": {"severity": severity}}
            if severity
            else {},
            "metadata": {"vulnerabilities": {**counts, "total": sum(counts.values())}},
        }
    ).encode()


def result(body, code=0):
    return subprocess.CompletedProcess([], code, body, b"")


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.prefix = Path(self.directory.name)
        for name in ("package.json", "package-lock.json"):
            (self.prefix / name).write_text("{}")

    def run_audit(self, responses):
        output = io.StringIO()
        with (
            patch.object(npm_audit.subprocess, "run", side_effect=responses) as run,
            patch.object(npm_audit.time, "sleep") as sleep,
            contextlib.redirect_stdout(output),
        ):
            code = npm_audit.audit(self.prefix)
        return code, run, sleep, output.getvalue()

    def test_clean_report_requires_success_and_preserves_low_threshold(self):
        code, run, sleep, _ = self.run_audit([result(report())])
        self.assertEqual(code, 0)
        self.assertEqual(run.call_count, 1)
        sleep.assert_not_called()
        args = run.call_args.args[0]
        self.assertIn("--audit-level=low", args)
        self.assertIn("--fetch-retries=0", args)
        self.assertFalse({"fix", "--force", "--omit=dev"} & set(args))
        self.assertEqual(run.call_args.kwargs["timeout"], 100)

    def test_every_blocking_severity_stops_without_retry(self):
        for severity in npm_audit.LEVELS[1:]:
            with self.subTest(severity=severity):
                code, run, sleep, _ = self.run_audit([result(report(severity), 1)])
                self.assertEqual(code, 1)
                self.assertEqual(run.call_count, 1)
                sleep.assert_not_called()

    def test_findings_block_even_if_cli_incorrectly_returns_success(self):
        self.assertEqual(self.run_audit([result(report("high"))])[0], 1)

    def test_original_npm_timeout_shape_retries_once_then_requires_real_report(self):
        error = json.dumps(
            {
                "message": "network timeout at: https://registry.npmjs.org/-/npm/v1/security/advisories/bulk",
                "headers": {"authorization": "synthetic-never-log"},
            }
        ).encode()
        code, run, sleep, output = self.run_audit([result(error, 1), result(report())])
        self.assertEqual(code, 0)
        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once_with(3)
        self.assertNotIn("synthetic-never-log", output)
        self.assertIn("TRANSPORT_UNAVAILABLE", output)

    def test_two_transport_failures_remain_non_successful(self):
        error = result(b'{"error":{"code":"ECONNRESET"}}', 1)
        code, run, sleep, _ = self.run_audit([error, error])
        self.assertEqual(code, 2)
        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once()

    def test_process_deadline_is_bounded_and_not_a_success(self):
        error = subprocess.TimeoutExpired("npm", 100)
        code, run, _, _ = self.run_audit([error, error])
        self.assertEqual(code, 2)
        self.assertEqual(run.call_count, 2)

    def test_partial_findings_are_not_discarded_after_timeout(self):
        code, run, sleep, _ = self.run_audit(
            [subprocess.TimeoutExpired("npm", 100, output=report("critical"))]
        )
        self.assertEqual(code, 1)
        self.assertEqual(run.call_count, 1)
        sleep.assert_not_called()

    def test_authentication_and_unknown_errors_never_retry(self):
        for value in [
            b'{"error":{"code":"E401"}}',
            b'{"error":{"code":"E403"}}',
            b'{"error":{"code":"ENOLOCK"}}',
            b'{"message":"unknown"}',
            b"not json",
            b"[]",
        ]:
            with self.subTest(value=value):
                code, run, sleep, _ = self.run_audit([result(value, 1)])
                self.assertEqual(code, 2)
                self.assertEqual(run.call_count, 1)
                sleep.assert_not_called()

    def test_official_http_read_errors_only_retry_known_transient_statuses(self):
        for status in [408, 429, 502, 503, 504]:
            value = json.dumps(
                {
                    "uri": "https://registry.npmjs.org/-/npm/v1/security/advisories/bulk",
                    "statusCode": status,
                }
            ).encode()
            self.assertEqual(npm_audit.classify(value, 1)[0], "TRANSPORT_UNAVAILABLE")
        for value in [
            {"uri": "https://untrusted.example/", "statusCode": 503},
            {
                "uri": "https://registry.npmjs.org/-/npm/v1/security/advisories/bulk",
                "statusCode": 401,
            },
            {"message": "network timeout at: https://untrusted.example/"},
        ]:
            self.assertNotEqual(
                npm_audit.classify(json.dumps(value).encode(), 1)[0],
                "TRANSPORT_UNAVAILABLE",
            )

    def test_malformed_or_inconsistent_reports_fail_closed(self):
        values = [json.loads(report()) for _ in range(5)]
        values[0]["auditReportVersion"] = 3
        values[1]["metadata"]["vulnerabilities"]["total"] = 1
        values[2]["metadata"]["vulnerabilities"]["low"] = True
        values[3]["vulnerabilities"] = {"hidden": {"severity": "high"}}
        values[4]["error"] = {"code": "E401"}
        for value in values:
            self.assertEqual(
                npm_audit.classify(json.dumps(value).encode(), 0)[0], "INVALID_REPORT"
            )
        self.assertEqual(npm_audit.classify(report(), 1)[0], "INVALID_REPORT")
        self.assertEqual(
            npm_audit.classify(
                b'{"vulnerabilities":{},"error":{"code":"ETIMEDOUT"}}', 1
            )[0],
            "INVALID_REPORT",
        )

    def test_changed_inputs_stop_without_retry_or_restoration(self):
        def changed(*args, **kwargs):
            (self.prefix / "package-lock.json").write_text('{"changed":true}')
            return result(report())

        with (
            patch.object(npm_audit.subprocess, "run", side_effect=changed) as run,
            self.assertRaisesRegex(ValueError, "inputs changed"),
        ):
            npm_audit.audit(self.prefix)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(
            (self.prefix / "package-lock.json").read_text(), '{"changed":true}'
        )


if __name__ == "__main__":
    unittest.main()
