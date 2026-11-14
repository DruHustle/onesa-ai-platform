"""Review discovery cannot claim hosted coverage or expose an internal build as public."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import review_package as review


class ReviewPackageTests(unittest.TestCase):
    def test_wrong_classification_or_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "generated").mkdir()
            (root / "generated/provenance.json").write_text(
                json.dumps({"classification": "internal", "revision": "a" * 40})
            )
            with self.assertRaises(ValueError):
                review.artifacts(root, "public")
            (root / "private.html").symlink_to(root / "generated/provenance.json")
            with self.assertRaises(ValueError):
                review.artifacts(root, "internal")

    def test_discovered_pages_are_never_attested_as_hosted_tests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "generated").mkdir()
            (root / "generated/provenance.json").write_text(
                json.dumps({"classification": "public", "revision": "a" * 40})
            )
            (root / "index.html").write_text("<main>Synthetic documentation</main>")
            result = review.artifacts(root, "public")
            self.assertEqual(
                result["pages"][0]["hosted_test_status"], "NOT_INFERRED_FROM_BUILD"
            )

    def test_existing_output_is_not_overwritten_and_output_never_approves_production(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "review"
            with patch.object(
                review, "project", return_value={"head_commit": "a" * 40}
            ):
                result = review.build(root, output)
            self.assertFalse(result["authorizes_production"])
            self.assertEqual(
                result["independent_review_status"], "PENDING_EXTERNAL_REVIEW"
            )
            self.assertEqual((output / "manifest.json").stat().st_mode & 0o777, 0o600)
            with self.assertRaises(ValueError):
                review.build(root, output)


if __name__ == "__main__":
    unittest.main()
