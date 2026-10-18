import json
import tempfile
import unittest
from pathlib import Path

from documentation_identity import sync_release_summary, validate_identity


class DocumentationIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = self.root / "onesa-ai-platform-frontend/apps/docs"
        self.app.mkdir(parents=True)
        (self.app / "package.json").write_text('{"version":"9.8.7"}')
        (self.root / "docs/public").mkdir(parents=True)
        self.summary = self.root / "docs/public/release-notes.md"
        self.summary.write_text(
            "<!-- documentation-version:start -->old<!-- documentation-version:end -->\nHistorical 0.2.0"
        )
        sync_release_summary(self.root)
        self.files = [self.app / ".cache/authoritative/provenance.json"] + [
            self.app / f".generated/{scope}/static/generated/provenance.json"
            for scope in ["public", "internal"]
        ]
        for p in self.files:
            p.parent.mkdir(parents=True)
            p.write_text(json.dumps({"documentation_version": "9.8.7"}))
        self.manuals = self.app / ".generated/public/static/generated/manuals.json"
        self.manuals.write_text('[{"version":"9.8.7"}]')

    def test_current_metadata_agrees_and_history_is_preserved(self):
        self.assertEqual(validate_identity(self.root), "9.8.7")
        self.assertIn("Historical 0.2.0", self.summary.read_text())

    def test_each_generated_metadata_mismatch_is_rejected(self):
        for p in self.files:
            good = p.read_text()
            p.write_text('{"documentation_version":"0.2.0"}')
            with self.assertRaisesRegex(ValueError, "Generated documentation"):
                validate_identity(self.root)
            p.write_text(good)

    def test_export_mismatch_is_rejected(self):
        self.manuals.write_text('[{"version":"0.2.0"}]')
        with self.assertRaisesRegex(ValueError, "Export documentation"):
            validate_identity(self.root)

    def test_current_summary_mismatch_is_rejected(self):
        self.summary.write_text(self.summary.read_text().replace("9.8.7", "0.2.0"))
        with self.assertRaisesRegex(ValueError, "Current release summary"):
            validate_identity(self.root)

    def test_site_footer_mismatch_is_rejected(self):
        site = self.app / "build-public/index.html"
        site.parent.mkdir(parents=True)
        site.write_text("<footer>Documentation v9.8.7</footer>")
        self.assertEqual(validate_identity(self.root), "9.8.7")
        site.write_text("<footer>Documentation v0.2.0</footer>")
        with self.assertRaisesRegex(ValueError, "Site footer"):
            validate_identity(self.root)
