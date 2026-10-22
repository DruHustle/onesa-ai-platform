"""Bound fixture download recovery; no registry, daemon, credentials or application."""

import contextlib
import io
import json
import subprocess
import unittest
from unittest.mock import patch

import pull_image

IMAGE = "pgvector/pgvector:pg16@sha256:" + "a" * 64


def response(code=0, error=b""):
    return subprocess.CompletedProcess([], code, b"", error)


def identity(digest="a" * 64):
    return subprocess.CompletedProcess(
        [], 0, json.dumps(["pgvector/pgvector@sha256:" + digest]), ""
    )


class DatabaseImageTests(unittest.TestCase):
    def execute(self, sequence):
        with (
            patch.object(pull_image.subprocess, "run", side_effect=sequence) as run,
            patch.object(pull_image.time, "sleep") as delay,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            pull_image.pull(IMAGE, database=True)
        return run, delay

    def test_success_verifies_digest_without_retry(self):
        run, delay = self.execute([response(), identity()])
        self.assertEqual(run.call_count, 2)
        delay.assert_not_called()

    def test_registry_500_recovers_only_same_immutable_read(self):
        run, delay = self.execute(
            [
                response(
                    1, b"received unexpected HTTP status: 500 Internal Server Error"
                ),
                response(),
                identity(),
            ]
        )
        self.assertEqual(run.call_args_list[0].args, run.call_args_list[1].args)
        self.assertEqual(run.call_args_list[0].kwargs["timeout"], 90)
        delay.assert_called_once_with(3)
        self.assertTrue(all("up" not in call.args[0] for call in run.call_args_list))

    def test_timeout_has_one_bounded_read_recovery(self):
        run, _ = self.execute(
            [
                subprocess.TimeoutExpired(["docker", "image", "pull"], 90),
                response(),
                identity(),
            ]
        )
        self.assertEqual(run.call_count, 3)

    def test_exhausted_transport_stops_before_build_or_start(self):
        with (
            patch.object(
                pull_image.subprocess,
                "run",
                return_value=response(
                    1, b"received unexpected HTTP status: 503 Service Unavailable"
                ),
            ) as run,
            patch.object(pull_image.time, "sleep"),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaisesRegex(RuntimeError, "Application checks have not started"),
        ):
            pull_image.pull(IMAGE, database=True)
        self.assertEqual(run.call_count, 2)

    def test_auth_manifest_and_unknown_errors_never_retry_or_leak(self):
        marker = b"synthetic-private-marker"
        for error in [b"unauthorized", b"manifest unknown", b"daemon unavailable"]:
            with (
                patch.object(
                    pull_image.subprocess,
                    "run",
                    return_value=response(1, error + marker),
                ) as run,
                patch.object(pull_image.time, "sleep") as delay,
                contextlib.redirect_stdout(io.StringIO()) as output,
                self.assertRaisesRegex(RuntimeError, "no retry") as caught,
            ):
                pull_image.pull(IMAGE, database=True)
            self.assertEqual(run.call_count, 1)
            delay.assert_not_called()
            self.assertNotIn(marker.decode(), str(caught.exception) + output.getvalue())

    def test_fatal_error_is_not_hidden_by_transport_text(self):
        with (
            patch.object(
                pull_image.subprocess,
                "run",
                return_value=response(
                    1, b"unauthorized; received unexpected HTTP status: 500"
                ),
            ) as run,
            self.assertRaisesRegex(RuntimeError, "no retry"),
        ):
            pull_image.pull(IMAGE, database=True)
        self.assertEqual(run.call_count, 1)

    def test_malformed_identity_is_not_retried_or_reported_as_success(self):
        for output in ["not-json", '"not-a-digest-list"', "[]"]:
            with self.assertRaisesRegex(RuntimeError, "identity"):
                self.execute(
                    [response(), subprocess.CompletedProcess([], 0, output, "")]
                )

    def test_changed_digest_is_never_retried(self):
        with self.assertRaisesRegex(RuntimeError, "identity"):
            self.execute([response(), identity("b" * 64)])

    def test_unpinned_wrong_repository_or_tag_rejected_before_read(self):
        with patch.object(pull_image.subprocess, "run") as run:
            for image in [
                "pgvector/pgvector:pg16",
                "other/db:pg16@sha256:" + "a" * 64,
                IMAGE.replace(":pg16@", ":latest@"),
                None,
            ]:
                with self.assertRaises(ValueError):
                    pull_image.pull(image, database=True)
        run.assert_not_called()

    def test_configuration_timeout_stops_before_image_read_without_leaking(self):
        with (
            patch.object(
                pull_image.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired(
                    ["docker", "compose", "config"],
                    30,
                    output="synthetic-private-configuration",
                ),
            ) as run,
            patch.object(pull_image, "pull") as pull,
            self.assertRaisesRegex(RuntimeError, "configuration timed out; no retry") as error,
        ):
            pull_image.main(database=True)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.kwargs["timeout"], 30)
        pull.assert_not_called()
        self.assertNotIn("synthetic-private-configuration", str(error.exception))

    def test_database_config_selects_only_db_without_printing_configuration(self):
        config = json.dumps(
            {
                "services": {
                    "db": {
                        "image": IMAGE,
                        "environment": {"private": "synthetic-marker"},
                    },
                    "other": {"image": "unapproved/image"},
                }
            }
        )
        with (
            patch.object(
                pull_image.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, config, ""),
            ) as run,
            patch.object(pull_image, "pull") as pull,
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            pull_image.main(database=True)
        pull.assert_called_once_with(IMAGE, database=True)
        self.assertEqual(
            run.call_args.args[0], ["docker", "compose", "config", "--format", "json"]
        )
        self.assertNotIn("synthetic-marker", output.getvalue())
        self.assertEqual(run.call_args.kwargs["timeout"], 30)
        self.assertLessEqual(30 + 2 * 90 + 3 + 10, 240)
