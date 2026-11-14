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
    def test_restore_uses_exact_hosted_schema_without_downgrading_enabled_features(
        self,
    ):
        binding = {"component": "twins-api", "candidate_commit": "a" * 40}
        plan = {
            "binding": binding,
            "mode": "twins",
            "expected_schema_revision": "20261026_cybersecurity",
        }
        self.assertEqual(
            t.restore_revision(plan, binding, "twins"), "20261026_cybersecurity"
        )
        for changed, profile in [
            ({**plan, "expected_schema_revision": "20261010_capacity"}, "twins"),
            ({**plan, "expected_schema_revision": "head"}, "twins"),
            ({**plan, "binding": {**binding, "candidate_commit": "b" * 40}}, "twins"),
            ({**plan, "mode": "cybersecurity"}, "twins"),
            (
                {
                    **plan,
                    "mode": "cybersecurity",
                    "expected_schema_revision": "20261025_twins",
                },
                "cybersecurity",
            ),
        ]:
            with (
                self.subTest(plan=changed, profile=profile),
                self.assertRaises(t.r.Refused),
            ):
                t.restore_revision(changed, binding, profile)

    def test_cybersecurity_restore_excludes_foreign_owners_and_requires_real_workflow(
        self,
    ):
        owners = [str(uuid4()), str(uuid4())]
        binding, operation = {"candidate_commit": "a" * 40}, str(uuid4())
        tables = {name: [{"user_id": owners[0]}] for name in t.CYBER_TABLES}
        tables["users"] = [
            {"id": owner, "email": "release-audit-123-" + str(i) * 24 + "@example.com"}
            for i, owner in enumerate(owners)
        ]
        bundle = {
            "binding": binding,
            "operation_id": operation,
            "scope": "new-owned-release-fixtures-only",
            "profile": "cybersecurity",
            "tables": tables,
        }
        self.assertEqual(t.validate(bundle, binding, operation), [])
        for invalid in ["foreign_owner", "incomplete", "wrong_profile", "wrong_source"]:
            value = json.loads(json.dumps(bundle))
            if invalid == "foreign_owner":
                value["tables"]["cyber_events"][0]["user_id"] = str(uuid4())
            elif invalid == "incomplete":
                value["tables"]["cyber_summaries"] = []
            elif invalid == "wrong_profile":
                value["profile"] = "other"
            else:
                value["binding"]["candidate_commit"] = "b" * 40
            with self.subTest(invalid=invalid), self.assertRaises(t.r.Refused):
                t.validate(value, binding, operation)

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
