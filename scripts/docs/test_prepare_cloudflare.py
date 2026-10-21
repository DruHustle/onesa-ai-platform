"""Packaging never permits public provenance, existing outputs or symlink artifacts."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import prepare_cloudflare
from protected_sources import REFERENCES


def private_provenance():
    documents = {
        path: {
            "sha256": "0" * 64,
            "repository": "onesa-ai-platform",
            "source_revision": "a" * 40,
            "source_path": path,
        }
        for path in REFERENCES
    }
    digest = hashlib.sha256(
        json.dumps(documents, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "classification": "internal",
        "revision": "a" * 40,
        "sources": {path: "0" * 64 for path in REFERENCES},
        "protected_document_sources": {
            "schema_version": 1,
            "classification": "internal",
            "documents": documents,
            "bundle_sha256": digest,
        },
    }


class PackagingTests(unittest.TestCase):
    def test_placeholder_never_reads_or_copies_engineering_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "onesa-ai-platform-frontend/apps/docs/build-internal"
            source.mkdir(parents=True)
            (source / "private.pdf").write_text("INTERNAL_CANARY")
            output = root / "bootstrap"
            with (
                patch.object(prepare_cloudflare, "ROOT", root),
                patch.object(prepare_cloudflare.subprocess, "check_output") as git,
            ):
                record = prepare_cloudflare.prepare(output, placeholder=True)
                git.assert_not_called()
                self.assertEqual(record["scope"], "placeholder")
                self.assertFalse(record["contains_engineering_content"])
                self.assertFalse(record["deployment_requested"])
                self.assertFalse(record["hosted_access_verified"])
                self.assertEqual(
                    {file.name for file in output.iterdir()},
                    {"index.html", "robots.txt", "_headers"},
                )
                self.assertTrue(
                    all(
                        "INTERNAL_CANARY" not in file.read_text()
                        for file in output.iterdir()
                    )
                )
                self.assertEqual(output.stat().st_mode & 0o077, 0)
                self.assertTrue(
                    all(file.stat().st_mode & 0o077 == 0 for file in output.iterdir())
                )
                for invalid in [output, source / "bootstrap", root]:
                    with self.assertRaises(ValueError):
                        prepare_cloudflare.prepare(invalid, placeholder=True)

    def test_placeholder_works_without_documentation_build_or_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(prepare_cloudflare, "ROOT", root):
                output = root / "bootstrap"
                prepare_cloudflare.prepare(output, placeholder=True)
                self.assertIn(
                    "Documentation is not available yet",
                    (output / "index.html").read_text(),
                )

    def test_internal_package_protects_all_routes_without_uploading(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "onesa-ai-platform-frontend/apps/docs/build-internal"
            (source / "generated").mkdir(parents=True)
            (source / "generated/provenance.json").write_text(
                json.dumps(private_provenance())
            )
            (source / "index.html").write_text("Synthetic internal fixture")
            worker = root / "infra/cloudflare-docs/worker.mjs"
            worker.parent.mkdir(parents=True)
            worker.write_text("Synthetic worker fixture")
            output = root / "private-package"
            with (
                patch.object(prepare_cloudflare, "ROOT", root),
                patch.object(
                    prepare_cloudflare.subprocess, "check_output", return_value="a" * 40
                ),
            ):
                manifest = source / "generated/provenance.json"
                complete = private_provenance()
                manifest.write_text(
                    json.dumps({"classification": "internal", "revision": "a" * 40})
                )
                with self.assertRaisesRegex(ValueError, "private-document provenance"):
                    prepare_cloudflare.prepare(output)
                self.assertFalse(output.exists())
                manifest.write_text(json.dumps(complete))
                record = prepare_cloudflare.prepare(output)
                self.assertFalse(record["deployment_requested"])
                self.assertFalse(record["hosted_access_verified"])
                self.assertEqual(
                    json.loads((output / "_routes.json").read_text())["exclude"], []
                )
                self.assertEqual(output.stat().st_mode & 0o077, 0)
                with self.assertRaises(ValueError):
                    prepare_cloudflare.prepare(output)
                (source / "generated/provenance.json").write_text(
                    '{"classification":"public"}'
                )
                with self.assertRaises(ValueError):
                    prepare_cloudflare.prepare(root / "other")

    def test_symlink_artifacts_and_stale_revision_fail_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "onesa-ai-platform-frontend/apps/docs/build-internal"
            (source / "generated").mkdir(parents=True)
            manifest = source / "generated/provenance.json"
            manifest.write_text(json.dumps(private_provenance()))
            output = root / "package"
            with (
                patch.object(prepare_cloudflare, "ROOT", root),
                patch.object(
                    prepare_cloudflare.subprocess, "check_output", return_value="b" * 40
                ),
            ):
                with self.assertRaisesRegex(ValueError, "stale"):
                    prepare_cloudflare.prepare(output)
                self.assertFalse(output.exists())
                (source / "private.pdf").symlink_to(manifest)
                with self.assertRaisesRegex(ValueError, "symlinks"):
                    prepare_cloudflare.prepare(output)
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
