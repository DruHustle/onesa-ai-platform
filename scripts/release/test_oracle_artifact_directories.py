"""Credential-free cold artifact/journal fixtures; no provider or release authority."""

import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import oracle_ai_runner as runner


class ArtifactDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.root.chmod(0o700)

        def private(path, *, directory=False):
            path = Path(path)
            runner.require(
                directory
                and path
                in [self.root, self.root / "operations", self.root / "observations"]
                and not path.is_symlink()
                and path.is_dir()
                and path.stat().st_uid == os.getuid()
                and path.stat().st_mode & 0o077 == 0,
                "PRIVATE_CUSTODY_REQUIRED",
            )
            return path

        self.enterContext(patch.object(runner, "private", side_effect=private))

    def test_cold_initialization_creates_only_private_empty_journal_parents(self):
        runner.prepare_artifact_directories(self.root)
        self.assertEqual(
            {p.name for p in self.root.iterdir()}, {"operations", "observations"}
        )
        for path in self.root.iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o700)
            self.assertEqual(list(path.iterdir()), [])

    def test_concurrent_initialization_preserves_existing_operation_evidence(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(
                pool.map(
                    lambda _n: runner.prepare_artifact_directories(self.root), range(16)
                )
            )
        operation = self.root / "operations" / "existing-operation"
        operation.mkdir(mode=0o700)
        marker = operation / "intent.json"
        marker.write_bytes(b"preserved original intent")
        marker.chmod(0o600)
        runner.prepare_artifact_directories(self.root)
        self.assertEqual(marker.read_bytes(), b"preserved original intent")

    def test_alias_file_and_writable_parent_are_refused_without_repair(self):
        target = self.root / "operations"
        for kind in ["symlink", "file", "writable"]:
            if kind == "symlink":
                target.symlink_to(self.root)
            elif kind == "file":
                target.write_bytes(b"existing unrelated bytes")
            else:
                target.mkdir(mode=0o755)
                target.chmod(0o755)
            with self.subTest(kind=kind), self.assertRaises(runner.Refused):
                runner.prepare_artifact_directories(self.root)
            self.assertFalse((self.root / "observations").exists())
            if kind == "writable":
                self.assertEqual(target.stat().st_mode & 0o777, 0o755)
                target.rmdir()
            else:
                if kind == "file":
                    self.assertEqual(target.read_bytes(), b"existing unrelated bytes")
                target.unlink()


if __name__ == "__main__":
    unittest.main()
