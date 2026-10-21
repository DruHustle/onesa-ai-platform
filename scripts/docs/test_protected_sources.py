"""A public build cannot consult the private source bundle or expose its text."""

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from protected_sources import (
    ProtectedSourceError,
    content,
    provenance,
    validate_publication,
)


class ProtectedDocuments(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "repo/docs/engineering/DEPLOYMENT.md"
        self.source.parent.mkdir(parents=True)
        self.stub = "# Deployment\n<!-- onesa-protected-source: ai-deployment -->\nProtected reference.\n"
        self.source.write_text(self.stub)
        self.repo = self.root / "repo"
        self.bundle = self.root / "bundle"
        self.bundle.mkdir(mode=0o700)
        self.private = self.bundle / "ai-deployment.md"
        self.private.write_text(
            "# Private operational guide\nSYNTHETIC_PRIVATE_CONTENT\n"
        )
        self.private.chmod(0o600)
        self.record = {
            "file": self.private.name,
            "sha256": hashlib.sha256(self.private.read_bytes()).hexdigest(),
            "repository": "onesa-ai-platform",
            "source_revision": "a" * 40,
            "source_path": "docs/engineering/DEPLOYMENT.md",
            "classification": "restricted-operational-document",
        }
        self.manifest = self.bundle / "manifest.json"
        self.write_manifest()
        self.env = patch.dict(
            os.environ, {"ONESA_INTERNAL_DOCS_SOURCE_ROOT": str(self.bundle)}
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temporary.cleanup()

    def write_manifest(self):
        self.manifest.write_text(
            json.dumps(
                {"schema_version": 1, "documents": {"ai-deployment": self.record}}
            )
        )
        self.manifest.chmod(0o600)

    def test_public_scope_never_opens_private_bundle_even_when_required(self):
        with (
            patch.dict(os.environ, {"ONESA_REQUIRE_PROTECTED_SOURCES": "1"}),
            patch(
                "protected_sources._bundle",
                side_effect=AssertionError("Private read forbidden"),
            ),
        ):
            self.assertEqual(content(self.source, self.repo, "public"), self.stub)
            self.assertIsNone(provenance("public"))

    def test_internal_exact_hash_content_only(self):
        self.assertEqual(content(self.source, self.repo), self.private.read_text())

    def test_unconfigured_ci_uses_public_safe_reference(self):
        with patch.dict(
            os.environ,
            {
                "ONESA_INTERNAL_DOCS_SOURCE_ROOT": "",
                "ONESA_REQUIRE_PROTECTED_SOURCES": "",
            },
        ):
            self.assertEqual(content(self.source, self.repo), self.stub)
            self.assertIsNone(provenance())

    def test_required_private_publication_refuses_missing_bundle(self):
        with (
            patch.dict(
                os.environ,
                {
                    "ONESA_INTERNAL_DOCS_SOURCE_ROOT": "",
                    "ONESA_REQUIRE_PROTECTED_SOURCES": "1",
                },
            ),
            self.assertRaises(ProtectedSourceError),
        ):
            content(self.source, self.repo)

    def test_modified_body_cannot_match_provenance(self):
        self.private.write_text("modified")
        with self.assertRaises(ProtectedSourceError):
            content(self.source, self.repo)

    def test_private_file_permissions_enforced(self):
        self.private.chmod(0o644)
        with self.assertRaises(ProtectedSourceError):
            content(self.source, self.repo)

    def test_manifest_permissions_enforced(self):
        self.manifest.chmod(0o644)
        with self.assertRaises(ProtectedSourceError):
            content(self.source, self.repo)

    def test_bundle_permissions_enforced(self):
        self.bundle.chmod(0o755)
        with self.assertRaises(ProtectedSourceError):
            content(self.source, self.repo)

    def test_manifest_cannot_redirect_to_another_file(self):
        for path in ["../ai-deployment.md", "/private/unknown.md", "other.md"]:
            with self.subTest(path=path):
                self.record["file"] = path
                self.write_manifest()
                with self.assertRaises(ProtectedSourceError):
                    content(self.source, self.repo)

    def test_symlink_is_not_a_private_source(self):
        other = self.bundle / "other.md"
        self.private.rename(other)
        self.private.symlink_to(other)
        with self.assertRaises(ProtectedSourceError):
            content(self.source, self.repo)

    def test_unmapped_or_incorrect_marker_is_rejected(self):
        self.source.write_text(self.stub.replace("ai-deployment", "other"))
        with self.assertRaises(ProtectedSourceError):
            content(self.source, self.repo)
        self.source = self.source.with_name("UNMAPPED.md")
        self.source.write_text(self.stub)
        with self.assertRaises(ProtectedSourceError):
            content(self.source, self.repo)

    def test_source_revision_and_classification_are_verified(self):
        for key, value in [
            ("source_revision", "latest"),
            ("classification", "public"),
            ("repository", "unapproved"),
        ]:
            with self.subTest(key=key):
                original = self.record[key]
                self.record[key] = value
                self.write_manifest()
                with self.assertRaises(ProtectedSourceError):
                    content(self.source, self.repo)
                self.record[key] = original

    def test_invalid_private_encoding_does_not_enter_exception_text(self):
        self.private.write_bytes(b"\xffSYNTHETIC_PRIVATE_CONTENT")
        self.record["sha256"] = hashlib.sha256(self.private.read_bytes()).hexdigest()
        self.write_manifest()
        with self.assertRaises(ProtectedSourceError) as caught:
            content(self.source, self.repo)
        self.assertNotIn("SYNTHETIC_PRIVATE_CONTENT", str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)

    def test_unknown_scope_is_not_private_access(self):
        with self.assertRaises(ProtectedSourceError):
            content(self.source, self.repo, "unknown")

    def test_normal_public_safe_reference_is_not_replaced(self):
        self.source = self.source.with_name("PUBLIC_SAFE.md")
        self.source.write_text("# Sanitized architecture\n")
        with patch(
            "protected_sources._bundle",
            side_effect=AssertionError("Private read forbidden"),
        ):
            self.assertEqual(
                content(self.source, self.repo), "# Sanitized architecture\n"
            )

    def test_complete_private_provenance_matches_actual_content_and_records_original_source(
        self,
    ):
        with patch(
            "protected_sources.REFERENCES",
            {"docs/engineering/DEPLOYMENT.md": "ai-deployment"},
        ):
            result = provenance()
            record = {
                "sources": {"docs/engineering/DEPLOYMENT.md": self.record["sha256"]},
                "protected_document_sources": result,
            }
            self.assertEqual(validate_publication(record), result["bundle_sha256"])
            self.assertEqual(
                result["documents"]["docs/engineering/DEPLOYMENT.md"][
                    "source_revision"
                ],
                "a" * 40,
            )
            record["sources"]["docs/engineering/DEPLOYMENT.md"] = "f" * 64
            with self.assertRaises(ProtectedSourceError):
                validate_publication(record)

    def test_partial_private_bundle_cannot_be_claimed_complete(self):
        with self.assertRaises(ProtectedSourceError):
            provenance()
        for record in [
            {},
            {"protected_document_sources": None},
            {
                "protected_document_sources": {
                    "schema_version": 1,
                    "classification": "internal",
                    "documents": {},
                    "bundle_sha256": "0" * 64,
                }
            },
        ]:
            with self.assertRaises(ProtectedSourceError):
                validate_publication(record)


if __name__ == "__main__":
    unittest.main()
