"""Verify archive authenticity before any database operation; no credentials or DB needed."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.exceptions import InvalidTag

spec = importlib.util.spec_from_file_location(
    "worker", Path(__file__).with_name("worker.py")
)
assert spec and spec.loader
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class ArchiveIntegrity(unittest.TestCase):
    def test_roundtrip_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source, encrypted = folder / "source", folder / "encrypted"
            source.write_bytes(b"Synthetic private database fixture" * 40000)
            with patch.object(worker, "encryption_key", return_value=b"A" * 32):
                worker.encrypt(source, encrypted)
                worker.decrypt(encrypted, folder / "restored")
                self.assertEqual(
                    source.read_bytes(), (folder / "restored").read_bytes()
                )
                changed = bytearray(encrypted.read_bytes())
                changed[len(worker.MAGIC) + 20] ^= 1
                (folder / "tampered").write_bytes(changed)
                with self.assertRaises(InvalidTag):
                    worker.decrypt(folder / "tampered", folder / "rejected")
            with (
                patch.object(worker, "encryption_key", return_value=b"B" * 32),
                self.assertRaises(InvalidTag),
            ):
                worker.decrypt(encrypted, folder / "wrong-key")
            (folder / "truncated").write_bytes(worker.MAGIC + b"short")
            with self.assertRaises(ValueError):
                worker.decrypt(folder / "truncated", folder / "short-result")


if __name__ == "__main__":
    unittest.main()
