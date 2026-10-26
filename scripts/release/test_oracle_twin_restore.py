"""Only newly created fixture owners' referenced files enter the restore probe."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import oracle_twin_restore as t


class FixtureFileTests(unittest.TestCase):
    def setup_files(self, folder):
        storage = folder / "storage"
        storage.mkdir()
        output = folder / "output"
        output.mkdir()
        owners = [str(uuid4()), str(uuid4())]
        data = b"owned synthetic model"
        digest = hashlib.sha256(data).hexdigest()
        tables = {name: [] for name in t.TABLES}
        tables["users"] = [
            {"id": owner, "email": "release-audit-123-" + str(n) * 24 + "@example.com"}
            for n, owner in enumerate(owners)
        ]
        tables["twin_files"] = [
            {"user_id": owner, "sha256": digest, "size": len(data)} for owner in owners
        ]
        binding = {"candidate_commit": "a" * 40}
        operation = str(uuid4())
        bundle = {
            "binding": binding,
            "operation_id": operation,
            "scope": "new-owned-release-fixtures-only",
            "tables": tables,
        }
        for owner in owners:
            parent = storage / owner
            parent.mkdir()
            (parent / digest).write_bytes(data)
        (output / "restore-fixtures.json").write_text(json.dumps(bundle))
        return storage, output, binding, operation, owners, digest, data

    def test_capture_reads_only_exact_fixture_file_references(self):
        with tempfile.TemporaryDirectory() as temp:
            storage, output, binding, operation, _owners, digest, data = (
                self.setup_files(Path(temp))
            )
            (storage / "unrelated-private-file").write_bytes(b"never read")
            with patch.object(t.r, "private", side_effect=lambda p, **kw: Path(p)):
                t.capture_fixture_files(output, binding, operation, storage)
            self.assertEqual(
                sorted(
                    p.read_bytes() for p in (output / "restore-files").rglob(digest)
                ),
                [data, data],
            )
            self.assertEqual(len(list((output / "restore-files").iterdir())), 2)

    def test_changed_or_aliased_content_never_publishes_restore_success(self):
        for alias in [False, True]:
            with tempfile.TemporaryDirectory() as temp:
                storage, output, binding, operation, owners, digest, _data = (
                    self.setup_files(Path(temp))
                )
                source = storage / owners[0] / digest
                if alias:
                    source.unlink()
                    source.symlink_to(storage / owners[1] / digest)
                else:
                    source.write_bytes(b"changed")
                with (
                    patch.object(t.r, "private", side_effect=lambda p, **kw: Path(p)),
                    self.assertRaises((t.r.Refused, OSError)),
                ):
                    t.capture_fixture_files(output, binding, operation, storage)
                self.assertFalse((output / "restore-receipt.json").exists())
