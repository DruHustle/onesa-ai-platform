"""Metadata-only diagnostics never replace the strict preservation comparison."""

import json
import unittest

import oracle_ai_probe as p


class PreservationDiagnosticTests(unittest.TestCase):
    def test_summary_detects_account_and_table_changes_without_exporting_identity(self):
        before = {
            "private-account-identifier": "a" * 64,
            "__persistent_tables__": {
                "bounded_uploads": {"count": 2, "sha256": "b" * 64}
            },
        }
        summary = p.preservation_summary(before)
        self.assertEqual(summary["accounts"]["count"], 1)
        self.assertNotIn("private-account-identifier", json.dumps(summary))
        changed = before | {"private-account-identifier": "c" * 64}
        self.assertNotEqual(p.preservation_summary(changed), summary)
        changed = before | {
            "__persistent_tables__": {
                "bounded_uploads": {"count": 1, "sha256": "d" * 64}
            }
        }
        self.assertNotEqual(p.preservation_summary(changed), summary)
        self.assertEqual(
            p.preservation_summary(dict(reversed(list(before.items())))), summary
        )
