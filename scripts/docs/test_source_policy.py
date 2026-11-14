import tempfile
import unittest
from pathlib import Path

from source_policy import sources


class SourcePolicyTests(unittest.TestCase):
    def test_public_and_engineering_sources_exclude_private_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = [
                "public/introduction.md",
                "engineering/README.md",
                "internal/release-audit/report.md",
                "private/record.md",
                "confidential/record.md",
                "data/record.md",
                "records/company-facts.md",
            ]
            for path in paths:
                file = root / "docs" / path
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("Synthetic source")
            self.assertEqual(
                [str(file.relative_to(root / "docs")) for file in sources(root)],
                ["engineering/README.md", "public/introduction.md"],
            )

    def test_symlink_cannot_include_outside_private_record(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "docs").mkdir()
            record = root / "private-record.md"
            record.write_text("Synthetic private record")
            (root / "docs" / "alias.md").symlink_to(record)
            self.assertEqual(sources(root), [])
