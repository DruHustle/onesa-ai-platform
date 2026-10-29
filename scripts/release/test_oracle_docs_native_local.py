"""Actual disposable Ed25519 producer keys; no owner account or hosted evidence."""

import base64
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import oracle_docs_native as root_native
import oracle_docs_native_local as local
import oracle_owner as owner


class NativeLocalTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.root.chmod(0o700)
        self.openssl = (
            "/opt/homebrew/bin/openssl"
            if Path("/opt/homebrew/bin/openssl").exists()
            else "/usr/bin/openssl"
        )
        self.cfg = {
            "runtime": {"openssl": self.openssl},
            "producer": {
                "private_key": str(self.root / "new.pem"),
                "public_key": str(self.root / "new.pub.pem"),
                "sha256": "a" * 64,
            },
            "issuer": {"key_id": "b" * 64},
            "binding": {
                "repository": "DruHustle/onesa-ai-platform",
                "component": "docs-public",
                "candidate_commit": "c" * 40,
            },
            "journal": str(self.root),
        }

    def registration(self):
        public = Path(self.cfg["producer"]["public_key"])
        return {
            "id": str(uuid4()),
            "binding": self.cfg["binding"],
            "details": {
                "purpose": local.DOMAIN,
                "state": "PENDING_EXPLICIT_OWNER_COMMISSION",
                "producer_sha256": "a" * 64,
                "public_key_sha256": owner.file_digest(public),
            },
        }

    def test_new_key_does_not_register_or_commission_and_cannot_overwrite_existing_key(
        self,
    ):
        result = local.generate_key(self.cfg)
        self.assertEqual(
            result["state"], "NEW_NATIVE_KEY_CREATED_UNREGISTERED_UNCOMMISSIONED"
        )
        self.assertFalse(result["production_deployment_authorized"])
        key = Path(self.cfg["producer"]["private_key"])
        initial = key.read_bytes()
        self.assertEqual(key.stat().st_mode & 0o777, 0o600)
        self.assertEqual(
            {p.name for p in self.root.iterdir()}, {"new.pem", "new.pub.pem"}
        )
        with self.assertRaises(owner.Rejected):
            local.generate_key(self.cfg)
        self.assertEqual(key.read_bytes(), initial)

    def test_possession_signature_verifies_only_for_the_exact_registration_contract(
        self,
    ):
        local.generate_key(self.cfg)
        registered = self.registration()
        output = local.sign_possession(self.cfg, registered)
        record = json.loads(Path(output["possession_path"]).read_bytes())
        raw = root_native.possession(registered)
        original = owner.OPENSSL
        owner.OPENSSL = self.openssl
        self.addCleanup(setattr, owner, "OPENSSL", original)
        public = Path(self.cfg["producer"]["public_key"])
        signature = base64.b64decode(record["possession_signature"], validate=True)
        owner.signed_bytes(None, public, raw, signature)
        changed = copy.deepcopy(registered)
        changed["binding"]["candidate_commit"] = "d" * 40
        with self.assertRaises(owner.Rejected):
            owner.signed_bytes(None, public, root_native.possession(changed), signature)
        self.assertFalse((self.root / "native-trust.json").exists())

    def test_wrong_purpose_producer_or_public_key_is_rejected_before_private_key_read(
        self,
    ):
        local.generate_key(self.cfg)
        baseline = self.registration()
        for field, value in [
            ("purpose", "arbitrary-message"),
            ("producer_sha256", "f" * 64),
            ("public_key_sha256", "e" * 64),
        ]:
            registered = copy.deepcopy(baseline)
            registered["details"][field] = value
            with (
                self.subTest(field=field),
                patch.object(owner, "signed_bytes") as signer,
            ):
                with self.assertRaises(owner.Rejected):
                    local.sign_possession(self.cfg, registered)
                signer.assert_not_called()

    def test_partial_key_generation_is_retained_without_trust_or_retry(self):
        with (
            patch.object(
                subprocess, "run", return_value=type("Failed", (), {"returncode": 1})()
            ),
            self.assertRaises(owner.Rejected),
        ):
            local.generate_key(self.cfg)
        self.assertTrue(Path(self.cfg["producer"]["private_key"]).exists())
        self.assertFalse(Path(self.cfg["producer"]["public_key"]).exists())
        with self.assertRaises(owner.Rejected):
            local.generate_key(self.cfg)

    def test_key_path_alias_is_refused_without_following_symlink(self):
        target = self.root / "retained"
        target.write_bytes(b"retained fixture")
        Path(self.cfg["producer"]["private_key"]).symlink_to(target)
        with self.assertRaises(owner.Rejected):
            local.generate_key(self.cfg)
        self.assertEqual(target.read_bytes(), b"retained fixture")


if __name__ == "__main__":
    unittest.main()
