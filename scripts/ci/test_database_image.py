"""Bound fixture download recovery; no registry, daemon, credentials or application."""

import contextlib
import io
import json
import subprocess
import unittest
from unittest.mock import patch

import pull_image

IMAGE = "pgvector/pgvector:pg16@sha256:" + "a" * 64
BLOB_ERROR = (
    b"unknown: failed to copy: httpReadSeeker: failed open: "
    b"unexpected status from GET request to "
    b"https://registry-1.docker.io/v2/pgvector/pgvector/blobs/sha256:"
    b"b3e09271b7213599bbf0d8ede6a4c8a5b00b4ea7272a1550860d7197214d6de3"
    b": 502 Bad Gateway"
)


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

    def test_observed_registry_blob_502_recovers_only_same_immutable_read(self):
        run, delay = self.execute([response(1, BLOB_ERROR), response(), identity()])
        self.assertEqual(run.call_count, 3)
        for call in run.call_args_list[:2]:
            self.assertEqual(call.args[0], ["docker", "image", "pull", IMAGE])
            self.assertEqual(call.kwargs["timeout"], 90)
        self.assertEqual(
            run.call_args_list[2].args[0][0:4], ["docker", "image", "inspect", IMAGE]
        )
        delay.assert_called_once_with(3)

    def test_other_approved_blob_5xx_reads_have_the_same_bound(self):
        for status in [
            b"500 Internal Server Error",
            b"503 Service Unavailable",
            b"504 Gateway Timeout",
        ]:
            with self.subTest(status=status):
                error = BLOB_ERROR.replace(b"502 Bad Gateway", status)
                run, delay = self.execute([response(1, error), response(), identity()])
                self.assertEqual(run.call_count, 3)
                self.assertEqual(run.call_args_list[0].args, run.call_args_list[1].args)
                delay.assert_called_once_with(3)

    def assert_blob_error_refused(self, error):
        marker = b" synthetic-private-marker"
        with (
            patch.object(
                pull_image.subprocess, "run", return_value=response(1, error + marker)
            ) as run,
            patch.object(pull_image.time, "sleep") as delay,
            contextlib.redirect_stdout(io.StringIO()) as output,
            self.assertRaisesRegex(RuntimeError, "no retry") as caught,
        ):
            pull_image.pull(IMAGE, database=True)
        self.assertEqual(run.call_count, 1)
        delay.assert_not_called()
        self.assertNotIn(marker.decode(), str(caught.exception) + output.getvalue())

    def test_unapproved_blob_error_shapes_never_retry_or_leak(self):
        replacements = {
            "http": (b"https://", b"http://"),
            "wrong_host": (
                b"registry-1.docker.io",
                b"registry-1.docker.io.example.invalid",
            ),
            "userinfo": (b"https://", b"https://synthetic@"),
            "wrong_repository": (b"pgvector/pgvector", b"pgvector/other"),
            "wrong_path": (b"/blobs/", b"/manifests/"),
            "short_digest": (b"sha256:b3", b"sha256:b"),
            "long_digest": (b"sha256:b3", b"sha256:b33"),
            "nonhex_digest": (b"sha256:b3", b"sha256:g3"),
            "digest_query": (b": 502", b"?download=1: 502"),
            "digest_fragment": (b": 502", b"#part: 502"),
            "wrong_method": (b"GET request", b"POST request"),
        }
        for label, (original, replacement) in replacements.items():
            with self.subTest(shape=label):
                self.assert_blob_error_refused(
                    BLOB_ERROR.replace(original, replacement)
                )
        for status in [
            b"400",
            b"401",
            b"403",
            b"404",
            b"408",
            b"429",
            b"501",
            b"505",
            b"5020",
            b"502x",
        ]:
            with self.subTest(status=status):
                self.assert_blob_error_refused(BLOB_ERROR.replace(b"502", status))

    def test_fatal_errors_take_precedence_over_blob_502(self):
        for fatal in [
            b"unauthorized",
            b"denied",
            b"manifest unknown",
            b"not found",
            b"Cannot connect to the Docker daemon",
        ]:
            with self.subTest(fatal=fatal):
                self.assert_blob_error_refused(fatal + b"; " + BLOB_ERROR)

    def test_exhausted_blob_502_stops_before_build_or_start(self):
        with (
            patch.object(
                pull_image.subprocess, "run", return_value=response(1, BLOB_ERROR)
            ) as run,
            patch.object(pull_image.time, "sleep") as delay,
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaisesRegex(RuntimeError, "Application checks have not started"),
        ):
            pull_image.pull(IMAGE, database=True)
        self.assertEqual(run.call_count, 2)
        self.assertTrue(
            all(
                call.args[0] == ["docker", "image", "pull", IMAGE]
                for call in run.call_args_list
            )
        )
        delay.assert_called_once_with(3)

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
            self.assertRaisesRegex(
                RuntimeError, "configuration timed out; no retry"
            ) as error,
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
