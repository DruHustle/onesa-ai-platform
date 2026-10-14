"""Source-bound producer rejects foreign classification and unpublished variants."""

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "release"))
from test_docs_scope import SHA, DocsGitHub

spec = importlib.util.spec_from_file_location(
    "docs_release_preview", Path(__file__).with_name("release_preview.py")
)
producer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(producer)


class PreviewProducerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir="/private/tmp")
        self.addCleanup(self.tmp.cleanup)
        self.folders = []
        for name, classification in [
            ("preview", "public"),
            ("internal", "internal"),
            ("production", "public"),
        ]:
            folder = Path(self.tmp.name) / name
            (folder / "generated").mkdir(parents=True)
            (folder / "generated/provenance.json").write_text(
                json.dumps({"revision": SHA, "classification": classification})
            )
            (folder / "index.html").write_text(name)
            self.folders.append(folder)
        self.proof = DocsGitHub().docs["scopes"]["public"]

    def produce(self):
        return producer.preview_record(
            SHA,
            "20",
            self.folders[0],
            self.folders[1],
            self.proof["hosted_acceptance"],
            self.proof["preview"],
            "a" * 64,
            self.folders[2],
            self.proof["production_acceptance"],
            "b" * 64,
        )

    def test_distinct_accepted_production_bytes_and_actual_preview_are_recorded(self):
        with patch.object(producer.e, "source_hash", return_value="c" * 64):
            record = self.produce()
        proof = record["scopes"]["public"]
        self.assertNotEqual(
            proof["build_sha256"], proof["preview_artifact"]["build_sha256"]
        )
        self.assertEqual(proof["build_environment"], "production")
        self.assertFalse(record["application_deployment_authorized"])
        self.assertFalse(record["backend_deployment_authorized"])
        self.assertEqual(record["scopes"]["internal"]["status"], "BLOCKED")

    def test_source_and_classification_are_checked_for_every_build(self):
        for folder in self.folders:
            path = folder / "generated/provenance.json"
            original = path.read_text()
            for value in [
                {"revision": "d" * 40, "classification": "public"},
                {"revision": SHA, "classification": "private-unapproved"},
            ]:
                path.write_text(json.dumps(value))
                with (
                    self.subTest(folder=folder.name, value=value),
                    self.assertRaises(producer.e.Rejected),
                ):
                    self.produce()
            path.write_text(original)

    def test_symlinked_content_and_missing_actual_provider_target_are_rejected(self):
        alias = self.folders[2] / "alias"
        alias.symlink_to(self.folders[0] / "index.html")
        with self.assertRaises(producer.e.Rejected):
            self.produce()
        alias.unlink()
        del self.proof["preview"]["target"]
        with self.assertRaises(producer.e.Rejected):
            self.produce()

    def test_production_acceptance_cannot_be_substituted_for_staging_proof(self):
        for name, value in [
            ("environment_context", "staging"),
            ("provenance", {"revision": SHA, "classification": "internal"}),
            ("navigation", []),
            ("icons", []),
            ("result", "FAIL"),
        ]:
            saved = copy.deepcopy(self.proof["production_acceptance"])
            self.proof["production_acceptance"][name] = value
            with self.subTest(name=name), self.assertRaises(producer.e.Rejected):
                self.produce()
            self.proof["production_acceptance"] = saved


if __name__ == "__main__":
    unittest.main()
