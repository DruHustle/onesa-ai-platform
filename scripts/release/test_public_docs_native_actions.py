"""Synthetic artifact custody is immutable data, never a hosted or production grant."""

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evidence as e
import free_gate as f
import test_public_docs_native as native
from test_evidence import SHA
from test_public_docs_native import PRODUCER


class ActionsNativeTests(unittest.TestCase):
    setUp = native.PublicNativeTests.setUp
    prepare = native.PublicNativeTests.prepare
    verify = native.PublicNativeTests.verify

    def custody(self):
        return {
            "channel": "actions-native",
            "metadata": copy.deepcopy(self.github.metadata_record),
            "producer_sha256": PRODUCER,
        }

    def read(self):
        return f.public_docs_actions_preview_metadata(
            self.github, SHA, 20, self.custody(), self.github.run(30)
        )

    def test_artifact_custody_is_conditional_and_never_calls_draft_endpoints(self):
        api = self.github.api

        def no_draft(path, *args, **kwargs):
            self.assertNotIn("/releases/", path)
            return api(path, *args, **kwargs)

        with patch.object(self.github, "api", side_effect=no_draft):
            self.prepare()
            result = self.verify()
        self.assertEqual(result["status"], "CONDITIONAL_EXTERNAL_HANDOFF")
        for record in [self.github.record, self.github.approval, result]:
            self.assertEqual(record["STAGING_VERIFIED"], "BLOCKED")
            for key in [
                "production_deployment_authorized",
                "application_deployment_authorized",
                "backend_deployment_authorized",
            ]:
                self.assertIs(record[key], False)
        self.assertFalse(result["deployment_triggered"])
        self.assertEqual(result["staging"]["custody"]["channel"], "actions-native")
        self.assertEqual(result["qualification_artifact"]["run_id"], 30)

    def test_default_full_private_and_current_unpinned_public_consumers_refuse(self):
        native.PublicNativeTests.test_default_full_private_and_unpinned_current_public_consumers_refuse(
            self
        )

    def test_reader_and_authorization_require_an_independent_producer_pin(self):
        self.prepare()
        for pin in [None, "", True, "PASS", "d" * 64]:
            with self.subTest(pin=pin), self.assertRaises(e.Rejected):
                f.public_docs_live_qualification(
                    self.github, SHA, 30, expected_producer_sha256=pin
                )
            with self.subTest(pin=pin), self.assertRaises(e.Rejected):
                self.verify(pin)

    def test_foreign_owner_rerun_wrong_event_and_failed_ci_refuse(self):
        native.PublicNativeTests.test_failed_skipped_ci_foreign_owner_and_rerun_refused(
            self
        )
        for field, value in [
            ("actor", {"login": "foreign"}),
            ("triggering_actor", {"login": "foreign"}),
            ("run_attempt", 2),
            ("event", "workflow_run"),
        ]:
            previous = copy.deepcopy(self.github.runs_by_id[30])
            self.github.runs_by_id[30][field] = value
            with self.subTest(field=field), self.assertRaises(e.Rejected):
                self.read()
            self.github.runs_by_id[30] = previous

    def test_source_preview_and_actual_archives_cannot_be_replaced(self):
        native.PublicNativeTests.test_legacy_pass_missing_pending_or_wrong_project_source_and_target_refused(
            self
        )
        native.PublicNativeTests.test_archive_bytes_ids_and_digest_substitution_refused(
            self
        )

    def test_typed_local_contexts_counts_and_no_grants_are_mandatory(self):
        native.PublicNativeTests.test_false_or_missing_local_context_and_typed_views_refused(
            self
        )
        native.PublicNativeTests.test_unknown_identity_sitebytes_caller_pass_and_boolean_counts_refused(
            self
        )
        for field in [
            "production_deployment_authorized",
            "application_deployment_authorized",
            "backend_deployment_authorized",
        ]:
            self.github.metadata_record[field] = True
            with self.subTest(field=field), self.assertRaises(e.Rejected):
                self.read()
            self.github.metadata_record[field] = False

    def test_artifact_record_custody_and_expiration_are_rechecked(self):
        self.prepare()
        for key, value in [
            ("workflow_run_id", 999),
            ("metadata_sha256", "d" * 64),
            ("channel", "draft"),
        ]:
            previous = copy.deepcopy(self.github.record["staging"]["custody"])
            self.github.record["staging"]["custody"][key] = value
            with self.subTest(key=key), self.assertRaises(e.Rejected):
                self.verify()
            self.github.record["staging"]["custody"] = previous
        self.github.record["verified_at"] = "2020-01-01T00:00:00Z"
        with self.assertRaises(e.Rejected):
            self.verify()

    def test_binding_failure_names_only_the_fixed_category(self):
        for field, value, category in [
            ("source_sha256", "d" * 64, "source"),
            ("producer_sha256", "d" * 64, "producer"),
            ("ci_sha256", "d" * 64, "ci"),
            ("preview_artifact_id", 999, "preview-id"),
            ("production_artifact_sha256", "d" * 64, "production-archive"),
            ("production_deployment_authorized", True, "no-grants"),
        ]:
            previous = copy.deepcopy(self.github.metadata_record)
            self.github.metadata_record[field] = value
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(
                    e.Rejected, "^Public metadata mismatch: " + category + "$"
                ) as caught,
            ):
                self.read()
            self.assertNotIn(str(value), str(caught.exception))
            self.github.metadata_record = previous
        self.assertEqual(self.read()["STAGING_VERIFIED"], "BLOCKED")

    def test_newer_authorization_revokes_prior_conditional_handoff(self):
        self.prepare()
        self.github.runs_by_id[41] = {**self.github.runs_by_id[40], "id": 41}
        self.github.latest = 41
        with self.assertRaises(e.Rejected):
            self.verify()


class NativeEventTests(unittest.TestCase):
    def event(self, inputs=None, raw=None, scope="docs-public", pin=PRODUCER):
        with tempfile.TemporaryDirectory() as temporary:
            file = Path(temporary) / "event.json"
            file.write_text(raw if raw is not None else json.dumps({"inputs": inputs}))
            with patch.dict(
                os.environ,
                {
                    "GITHUB_EVENT_PATH": str(file),
                    "GITHUB_EVENT_NAME": "workflow_dispatch",
                },
            ):
                return f.public_docs_native_event(str(file), scope, pin, "20")

    def inputs(self):
        return {
            "delivery_scope": "docs-public",
            "staging_run": "20",
            "native_custody_mode": "actions-native",
            "native_metadata": "{}",
            "metadata_producer_sha256": PRODUCER,
        }

    def test_explicit_artifact_mode_parses_only_bounded_data(self):
        value = self.event(self.inputs())
        self.assertEqual(
            value,
            {"channel": "actions-native", "metadata": {}, "producer_sha256": PRODUCER},
        )
        self.assertIsNone(self.event({}))
        self.assertIsNone(self.event(None))

    def test_default_full_private_and_mixed_draft_inputs_refuse(self):
        for scope in ["full", "docs-internal"]:
            with self.subTest(scope=scope), self.assertRaises(e.Rejected):
                self.event(self.inputs(), scope=scope)
        for key, value in [
            ("native_custody_mode", "none"),
            ("native_custody_mode", "PASS"),
            ("metadata_release_id", "100"),
            ("metadata_asset_id", "200"),
            ("metadata_asset_digest", "sha256:" + "a" * 64),
            ("staging_run", "21"),
            ("delivery_scope", "full"),
            ("metadata_producer_sha256", "d" * 64),
            ("extra_input", "PASS"),
            ("native_custody_mode", []),
        ]:
            inputs = self.inputs()
            inputs[key] = value
            with self.subTest(key=key), self.assertRaises(e.Rejected):
                self.event(inputs)

    def test_duplicate_nonfinite_invalid_and_oversized_payload_refuse(self):
        for payload in [
            '{"x":1,"x":2}',
            '{"x":NaN}',
            "not-json",
            "x" * 32769,
            '"' + "é" * 16384 + '"',
        ]:
            inputs = self.inputs()
            inputs["native_metadata"] = payload
            with self.subTest(size=len(payload)), self.assertRaises(e.Rejected):
                self.event(inputs)
        for inputs in [False, [], "text"]:
            with self.subTest(inputs=inputs), self.assertRaises(e.Rejected):
                self.event(inputs)
        with self.assertRaises(e.Rejected):
            self.event(raw='{"inputs":{},"inputs":{}}')

    def test_event_scope_path_symlink_and_size_are_bounded(self):
        with tempfile.TemporaryDirectory() as temporary:
            file = Path(temporary) / "event.json"
            file.write_text(json.dumps({"inputs": self.inputs()}))
            link = Path(temporary) / "link.json"
            link.symlink_to(file)
            for path, envpath, event in [
                (file, link, "workflow_dispatch"),
                (link, link, "workflow_dispatch"),
                (file, file, "push"),
            ]:
                with (
                    patch.dict(
                        os.environ,
                        {"GITHUB_EVENT_PATH": str(envpath), "GITHUB_EVENT_NAME": event},
                    ),
                    self.assertRaises(e.Rejected),
                ):
                    f.public_docs_native_event(str(path), "docs-public", PRODUCER, "20")
            file.write_bytes(b"x" * (1024 * 1024 + 1))
            with (
                patch.dict(os.environ, {"GITHUB_EVENT_PATH": str(file)}),
                self.assertRaises(e.Rejected),
            ):
                f.public_docs_native_event(str(file), "docs-public", PRODUCER, "20")

    def test_workflow_checks_the_build_environment_in_local_acceptance(self):
        import yaml

        workflow = yaml.safe_load(
            (f.e.ROOT / ".github/workflows/docs-hosting.yml").read_text()
        )
        job = workflow["jobs"]["documentation"]
        self.assertEqual(
            job["env"]["ONESA_DOCS_EXPECTED_ENVIRONMENT"],
            job["env"]["ONESA_DOCS_ENVIRONMENT"],
        )
        steps = job["steps"]
        staging = next(
            step
            for step in steps
            if "docs-staging-acceptance.json" in step.get("run", "")
        )
        self.assertNotIn("ONESA_DOCS_EXPECTED_ENVIRONMENT", staging.get("env", {}))
        production = next(
            step
            for step in steps
            if "docs-production-acceptance.json" in step.get("run", "")
        )
        self.assertIn(
            "ONESA_DOCS_EXPECTED_ENVIRONMENT=production node scripts/docs/acceptance.mjs",
            production["run"],
        )

    def test_workflow_keeps_eight_inputs_read_permissions_and_no_shell_json(self):
        workflow = (f.e.ROOT / ".github/workflows/free-qualification.yml").read_text()
        import yaml

        inputs = yaml.safe_load(workflow)["on"]["workflow_dispatch"]["inputs"]
        self.assertEqual(len(inputs), 8)
        self.assertEqual(inputs["native_custody_mode"]["default"], "none")
        self.assertNotIn("${{ inputs.native_metadata }}", workflow)
        self.assertIn('--native-metadata-event "$GITHUB_EVENT_PATH"', workflow)
        self.assertEqual(
            yaml.safe_load(workflow)["permissions"],
            {
                "contents": "read",
                "actions": "read",
                "issues": "read",
                "pull-requests": "read",
            },
        )


if __name__ == "__main__":
    unittest.main()
