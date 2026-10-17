import hashlib
import tempfile
import unittest
from pathlib import Path

from ecosystem import validate_portal_diagrams


class PortalDiagramProvenance(unittest.TestCase):
    schema = "CREATE TABLE users (id uuid);\nCREATE TABLE sessions (id uuid);\n"

    def check(self, entities, digest=None):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            sha = digest or hashlib.sha256(self.schema.encode()).hexdigest()
            (folder / "portal-database-identity.mmd").write_text(
                "%% Portal source schema SHA256: "
                + sha
                + "\nerDiagram\n"
                + "".join(
                    "  " + name + " {\n    uuid id PK\n  }\n" for name in entities
                )
            )
            validate_portal_diagrams(self.schema, folder)

    def test_matching_schema_and_complete_declared_tables(self):
        self.check(["users", "sessions"])

    def test_schema_change_requires_reverification(self):
        with self.assertRaisesRegex(AssertionError, "provenance"):
            self.check(["users", "sessions"], "0" * 64)

    def test_omitted_or_invented_entities_fail_closed(self):
        for entities in [["users"], ["users", "sessions", "invented"]]:
            with (
                self.subTest(entities=entities),
                self.assertRaisesRegex(AssertionError, "coverage"),
            ):
                self.check(entities)
