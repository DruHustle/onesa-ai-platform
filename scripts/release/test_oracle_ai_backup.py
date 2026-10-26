"""Read-only snapshot/file coordination boundaries with disposable data."""

import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import oracle_ai_backup as b


class BackupTests(unittest.TestCase):
    def test_snapshot_revision_comes_from_the_same_dump_and_fails_closed(self):
        def copy(value):
            return (
                "-- pg_restore output\nCOPY public.alembic_version (version_num) FROM stdin;\n"
                + value
                + "\n\\.\n"
            ).encode()

        for revision in [
            "20261010_capacity",
            "20261021_industrial",
            "20261025_twins",
            "20261026_cybersecurity",
        ]:
            self.assertEqual(b.snapshot_revision(copy(revision)), revision)
        value = copy("20261026_cybersecurity")
        for invalid in [
            b"-- no revision table",
            copy(""),
            copy("unknown"),
            copy("20261025_twins\n20261026_cybersecurity"),
            value + value,
            value.replace(b"\n\\.\n", b"\n"),
            value.replace(b"(version_num)", b"(other)"),
        ]:
            with self.subTest(invalid=invalid), self.assertRaises(b.custody.Refused):
                b.snapshot_revision(invalid)

    def test_copy_rows_are_parsed_without_executing_sql(self):
        owner = str(uuid4())
        digest = "a" * 64
        data = f'-- Read-only pg_restore output\nCOPY public.twin_files (details, sha256, size, user_id) FROM stdin;\n{{"x":"\\\\n"}}\t{digest}\t5\t{owner}\n\\.\n'.encode()
        self.assertEqual(
            b.references(data), [{"owner": owner, "sha256": digest, "size": 5}]
        )
        for malformed in [
            data.replace(b"\n\\.\n", b""),
            data.replace(b"\t5\t", b"\t4194305\t"),
            data.replace(owner.encode(), b"../escape"),
            data + data,
        ]:
            with self.assertRaises((b.custody.Refused, ValueError)):
                b.references(malformed)

    def test_snapshot_selects_exact_referenced_immutable_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            a = "a" * 64
            z = "b" * 64
            owner = str(uuid4())
            ref = {"owner": owner, "sha256": a, "size": 5}
            (p / a).write_bytes(b"bytes")
            (p / z).write_bytes(b"extra")
            self.assertEqual(
                b.select_files([ref], {(owner, a): ref}, p), [{"sha256": a, "size": 5}]
            )
            self.assertFalse((p / z).exists())
            with self.assertRaises(b.custody.Refused):
                b.select_files([{**ref, "sha256": z}], {(owner, a): ref}, p)

    def test_upload_during_snapshot_or_deleted_file_cannot_publish_success(self):
        owner = str(uuid4())
        ref = {"owner": owner, "sha256": "a" * 64, "size": 5}
        with (
            tempfile.TemporaryDirectory() as temp,
            self.assertRaises(b.custody.Refused),
        ):
            b.select_files([ref], {}, Path(temp))

    def test_private_copy_validates_hash_and_rejects_alias(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            root.mkdir()
            output = Path(temp) / "output"
            output.mkdir()
            owner = str(uuid4())
            folder = root / owner
            folder.mkdir()
            data = b"private synthetic model"
            digest = hashlib.sha256(data).hexdigest()
            (folder / digest).write_bytes(data)
            # Unit fixture permission boundary is independent of root Linux custody.
            with patch.object(
                b.custody, "private", side_effect=lambda p, **kw: Path(p)
            ):
                result = b.copy_candidates(root, output, uid=os.getuid())
                self.assertEqual(result[(owner, digest)]["size"], len(data))
                (folder / digest).write_bytes(b"changed")
                with self.assertRaises(b.custody.Refused):
                    b.copy_candidates(root, output, uid=os.getuid())

    def test_backup_identity_distinguishes_tool_candidate_and_actual_runtime(self):
        config = {
            "source_commit": "a" * 40,
            "release_candidate_commit": "b" * 40,
            "producer_sha256": "c" * 64,
        }
        runtime = {
            "source_commit": "d" * 40,
            "image": "sha256:" + "e" * 64,
            "container_id": "fixture",
            "runtime_sha256": "f" * 64,
        }
        receipt = {**config, "application_runtime": runtime}
        with patch.object(b, "application_runtime", return_value=runtime):
            b.receipt_binding(receipt, config)
            for key in config:
                with self.subTest(key=key), self.assertRaises(b.custody.Refused):
                    b.receipt_binding({**receipt, key: "changed"}, config)
            with self.assertRaises(b.custody.Refused):
                b.receipt_binding(
                    {
                        **receipt,
                        "application_runtime": {**runtime, "source_commit": "b" * 40},
                    },
                    config,
                )

    def test_backup_transport_receives_only_existing_s3_custody(self):
        allowed = {
            "AWS_ACCESS_KEY_ID": "fixture",
            "AWS_SECRET_ACCESS_KEY": "fixture",
            "S3_ENDPOINT": "https://fixture.invalid",
            "S3_REGION": "fixture",
            "S3_BUCKET": "fixture",
        }
        with patch.object(
            b.custody,
            "runtime_values",
            return_value={
                **allowed,
                "ONESA_DATABASE_URL": "never-forward",
                "SESSION_SECRET": "never-forward",
            },
        ):
            self.assertEqual(
                b.transport_values({"existing_transport_env": "/fixture.env"}), allowed
            )
        with (
            patch.object(
                b.custody, "runtime_values", return_value={"S3_BUCKET": "fixture"}
            ),
            self.assertRaises(b.custody.Refused),
        ):
            b.transport_values({"existing_transport_env": "/fixture.env"})
