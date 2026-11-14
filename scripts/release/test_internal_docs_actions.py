"""Owner Actions custody is conditional data, never hosted acceptance or a grant."""

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evidence as e
import free_gate as f
from test_evidence import SHA
from test_internal_docs_conditional import InternalDocsConditionalTests
from test_internal_docs_metadata import PRODUCER


class InternalActionsTests(InternalDocsConditionalTests):
    def qualify(self):
        return f.qualification(
            self.github,
            SHA,
            self.github.run(30),
            None,
            "docs-internal",
            metadata_custody={
                "channel": "actions-native",
                "metadata": copy.deepcopy(self.github.metadata),
                "producer_sha256": PRODUCER,
            },
        )

    def test_owner_custody_is_conditional_with_no_hosted_or_production_pass(self):
        original = self.github.api

        def no_draft(path, **kwargs):
            self.assertNotIn("/releases/", path)
            return original(path, **kwargs)

        with patch.object(self.github, "api", side_effect=no_draft):
            self.prepare()
            result = self.verify()
        self.assertEqual(result["status"], "CONDITIONAL_EXTERNAL_HANDOFF")
        self.assertEqual(
            result["staging"]["custody"],
            {
                "channel": "actions-native",
                "workflow_run_id": 30,
                "metadata_sha256": e.digest(self.github.metadata),
            },
        )
        for record in [
            self.github.record,
            self.github.approval,
            result,
            result["staging"],
        ]:
            self.assertEqual(record["STAGING_VERIFIED"], "BLOCKED")
            for key in [
                "production_deployment_authorized",
                "application_deployment_authorized",
                "backend_deployment_authorized",
            ]:
                self.assertIs(record[key], False)

    def test_current_draft_asset_metadata_and_producer_custody_are_revalidated(self):
        self.prepare()
        for key, value in [
            ("workflow_run_id", 999),
            ("metadata_sha256", "0" * 64),
            ("channel", "draft"),
        ]:
            saved = copy.deepcopy(self.github.record["staging"]["custody"])
            self.github.record["staging"]["custody"][key] = value
            with self.assertRaises(e.Rejected):
                self.verify()
            self.github.record["staging"]["custody"] = saved
        self.github.metadata["staging"]["source_commit"] = "0" * 40
        with self.assertRaises(e.Rejected):
            self.qualify()

    def test_unavailable_draft_read_fails_closed_without_permissions_fallback(self):
        # Native custody never falls back to a draft or to wider permissions.
        with patch.object(f, "_internal_docs_asset_bytes", side_effect=AssertionError):
            self.prepare()
            self.verify()

    def test_internal_event_is_explicit_and_cannot_mix_public_or_draft_inputs(self):
        inputs = {
            "delivery_scope": "docs-internal",
            "staging_run": "",
            "native_custody_mode": "actions-native",
            "native_metadata": json.dumps(self.github.metadata),
            "metadata_producer_sha256": PRODUCER,
        }
        with tempfile.TemporaryDirectory() as temporary:
            file = Path(temporary) / "event.json"

            def read(value):
                file.write_text(json.dumps({"inputs": value}))
                with patch.dict(
                    os.environ,
                    {
                        "GITHUB_EVENT_PATH": str(file),
                        "GITHUB_EVENT_NAME": "workflow_dispatch",
                    },
                ):
                    return f.public_docs_native_event(
                        str(file), "docs-internal", PRODUCER, ""
                    )

            self.assertEqual(read(inputs)["metadata"], self.github.metadata)
            for key, value in [
                ("delivery_scope", "docs-public"),
                ("staging_run", "20"),
                ("metadata_release_id", "100"),
                ("native_custody_mode", "none"),
                ("metadata_producer_sha256", "0" * 64),
            ]:
                with self.subTest(key=key), self.assertRaises(e.Rejected):
                    read({**inputs, key: value})


if __name__ == "__main__":
    unittest.main()
