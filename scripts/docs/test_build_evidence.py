"""The CI producer cannot turn local checks into a hosted or deployment grant."""

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "release"))
from test_docs_scope import SHA, acceptance

spec = importlib.util.spec_from_file_location(
    "docs_build_evidence", Path(__file__).with_name("build_evidence.py")
)
producer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(producer)


class BuildEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.checks = {name: acceptance(name) for name in ["staging", "production"]}

    def test_actual_local_contexts_remain_local_and_use_real_actions_id(self):
        result = producer.record(SHA, 123, self.checks)
        self.assertEqual(result["actions_build_run_id"], 123)
        for key in [
            "hosted_qualification",
            "production_deployment_authorized",
            "application_deployment_authorized",
            "backend_deployment_authorized",
        ]:
            self.assertIs(result[key], False)

    def test_run_zero_failed_checks_wrong_source_context_or_missing_views_refuse(self):
        for run in [0, -1, True, "123"]:
            with self.subTest(run=run), self.assertRaises(producer.e.Rejected):
                producer.record(SHA, run, self.checks)
        for field, value in [
            ("result", "FAIL"),
            ("environment_context", "production"),
            ("provenance", {"revision": "f" * 40, "classification": "public"}),
            ("accessibility", ["PASS"] * 124),
        ]:
            checks = copy.deepcopy(self.checks)
            checks["staging"][field] = value
            with self.subTest(field=field), self.assertRaises(producer.e.Rejected):
                producer.record(SHA, 123, checks)


if __name__ == "__main__":
    unittest.main()
