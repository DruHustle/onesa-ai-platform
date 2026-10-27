"""Disposable CLI custody/authentication gates; no provider credential or authority."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import oracle_ai_frontend as f

r = f.r


class CliAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.image = "sha256:" + "a" * 64
        self.auth = {
            "token": "synthetic-loopback-only",
            "expiresAt": int(r.now().timestamp()) + 7200,
            "cachedUser": {"username": "untrusted-cache"},
        }
        self.write_auth()
        (self.root / "config.json").write_text("{}")
        self.image_metadata = [
            {
                "Id": self.image,
                "Architecture": "arm64",
                "Config": {"Labels": {"org.onesa.vercel-cli": "65.2.0"}},
            }
        ]

    def write_auth(self):
        (self.root / "auth.json").write_text(json.dumps(self.auth))
        (self.root / "auth.json").chmod(0o600)

    def call(self, result=None, error=None):
        with (
            patch.object(f, "CLI_AUTH", self.root),
            patch.object(r, "private", side_effect=lambda p, **kw: Path(p)),
            patch.object(
                r, "trusted_toolchain", return_value={"cli_image": self.image}
            ),
            patch.object(
                r, "docker", return_value=json.dumps(self.image_metadata).encode()
            ),
            patch.object(
                r,
                "command",
                return_value=result
                or b'{"user":{"username":"druhustle","email":"synthetic@example.com"}}',
                side_effect=error,
            ) as command,
        ):
            value = f.cli_authentication({"verifier_store": "disposable-fixture"})
            args = command.call_args.args[0]
            self.assertIn("/v2/user", args)
            self.assertEqual(args[args.index("-X") + 1], "GET")
            self.assertIn("--pull=never", args)
            self.assertNotIn("deploy", args)
            self.assertNotIn("--token", args)
            self.assertNotIn("synthetic-loopback-only", " ".join(args))
            self.assertFalse(any("/workspace" in a for a in args))
            self.assertNotIn("synthetic@example.com", json.dumps(value))
            return value

    def test_current_oauth_snapshot_is_checked_through_actual_cli_command(self):
        result = self.call()
        self.assertEqual(result["state"], "PINNED_CLI_AUTHENTICATED_READ_ONLY")
        self.assertEqual(result["provider_create_requests"], 0)

    def test_legacy_nonexpiring_custody_remains_supported(self):
        del self.auth["expiresAt"]
        self.write_auth()
        self.call()

    def test_stale_short_or_invalid_expiry_fails_before_any_container_or_request(self):
        for expiry in [0, int(r.now().timestamp()) + 60, True, "future"]:
            self.auth["expiresAt"] = expiry
            self.write_auth()
            with (
                self.subTest(expiry=expiry),
                patch.object(f, "CLI_AUTH", self.root),
                patch.object(r, "private", side_effect=lambda p, **kw: Path(p)),
                patch.object(r, "docker") as docker,
                patch.object(r, "command") as command,
                self.assertRaisesRegex(r.Refused, "CLI_AUTH_STATE_EXPIRED"),
            ):
                f.cli_authentication({})
            docker.assert_not_called()
            command.assert_not_called()

    def test_wrong_real_owner_and_failed_http_do_not_trust_cached_user(self):
        with self.assertRaisesRegex(r.Refused, "PINNED_CLI_AUTHENTICATION_FAILED"):
            self.call(b'{"user":{"username":"foreign"}}')
        with self.assertRaisesRegex(r.Refused, "PINNED_CLI_AUTHENTICATION_FAILED"):
            self.call(error=r.Refused("untrusted private provider diagnostic"))

    def test_wrong_tool_architecture_fails_before_authentication(self):
        self.image_metadata[0]["Architecture"] = "amd64"
        with self.assertRaisesRegex(r.Refused, "PINNED_CLI_TOOL_REQUIRED"):
            self.call()

    def test_concurrent_credential_replacement_refuses_the_observation(self):
        def replace(*args, **kwargs):
            (self.root / "config.json").write_text('{"concurrent":true}')
            return b'{"user":{"username":"druhustle"}}'

        with self.assertRaisesRegex(r.Refused, "CLI_CUSTODY_CHANGED"):
            self.call(error=replace)


class RunnerFailureTests(unittest.TestCase):
    def test_early_failure_is_retained_without_private_input_or_retry_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = "a" * 40
            folder = root / "artifacts" / candidate
            folder.mkdir(parents=True)
            identifier = str(uuid4())
            request = {
                "binding": {
                    "repository": "DruHustle/onesa-ai-platform",
                    "component": "api",
                    "candidate_commit": candidate,
                },
                "context": {
                    "context_id": identifier,
                    "owner_token": "must-not-persist",
                    "approval": "caller-json-is-not-authority",
                },
            }
            with (
                patch.object(r, "ROOT", root),
                patch.object(r, "private", side_effect=lambda p, **kw: Path(p)),
            ):
                r.record_runner_failure(
                    "staging", request, ValueError("private-token-must-not-persist")
                )
            files = list((folder / "failures").glob("*.json"))
            self.assertEqual(len(files), 1)
            raw = files[0].read_text()
            value = json.loads(raw)
            self.assertEqual(value["status"], "FAILED_NOT_QUALIFIED")
            self.assertTrue(value["diagnostic_only"])
            self.assertFalse(value["provider_retry_allowed"])
            self.assertEqual(value["failure_code"], "ValueError")
            self.assertEqual(value["record_ids"], {"context_id": identifier})
            self.assertNotIn("must-not-persist", raw)
            self.assertNotIn("caller-json", raw)

    def test_main_records_preproducer_failure_and_returns_redacted_error(self):
        request = {"binding": {}, "context": {}}
        with (
            patch.object(r.os, "geteuid", return_value=0),
            patch.object(r.os, "getenv", return_value=None),
            patch.object(r.sys, "argv", ["runner", "staging"]),
            patch.object(
                r.sys,
                "stdin",
                SimpleNamespace(buffer=io.BytesIO(json.dumps(request).encode())),
            ),
            patch.object(r, "run_request", side_effect=KeyError("must-not-echo")),
            patch.object(r, "record_runner_failure") as record,
            self.assertRaisesRegex(r.Refused, "PINNED_RUNNER_FAILED_INSPECT"),
        ):
            r.main()
        record.assert_called_once()
