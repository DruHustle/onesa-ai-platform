"""Real disposable signatures and atomic custody; no hosted or production claims."""

import base64
import copy
import json
import subprocess
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import oracle_docs_native as native
import oracle_owner as owner
from test_oracle_owner import OwnerStoreTests


class NativeCustodyTests(unittest.TestCase):
    open = OwnerStoreTests.open
    settings = OwnerStoreTests.settings
    commission_fixture = OwnerStoreTests.commission_fixture

    @classmethod
    def setUpClass(cls):
        OwnerStoreTests.setUpClass.__func__(cls)

    def setUp(self):
        OwnerStoreTests.setUp(self)
        self.store.db.close()
        profile = self.policy["components"].pop("DruHustle/onesa-company-portal:api")
        profile["qualification_attempt_limit"] = 1
        self.binding.update(
            repository="DruHustle/onesa-ai-platform", component="docs-public"
        )
        self.policy["components"]["DruHustle/onesa-ai-platform:docs-public"] = profile
        self.policy["toolchain"] = {"native_producer_sha256": "9" * 64}
        (self.root / "policy.json").write_bytes(owner.canonical(self.policy))
        trust = json.loads((self.root / "trust.json").read_bytes())
        trust["policy_sha256"] = owner.file_digest(self.root / "policy.json")
        (self.root / "trust.json").write_bytes(owner.canonical(trust))
        self.commission_fixture()
        self.ci.token = "synthetic-owner-token-not-a-real-credential"
        self.store = self.open()
        self.addCleanup(self.store.db.close)
        self.key = self.root / "native-fixture-signing.pem"
        subprocess.run(
            [owner.OPENSSL, "genpkey", "-algorithm", "ED25519", "-out", str(self.key)],
            check=True,
            capture_output=True,
        )
        self.key.chmod(0o600)
        self.public_native = subprocess.check_output(
            [owner.OPENSSL, "pkey", "-in", str(self.key), "-pubout"]
        ).decode()
        self.preview_id = str(uuid4())

        def validate(_store, challenge, payload):
            owner.require(
                payload["evidence"] == {"synthetic_fixture": True}
                and payload["environment"] == challenge["details"]["environment"],
                "SYNTHETIC_NATIVE_CHECK_FAILED",
            )

        self.enterContext(
            patch.dict(
                sys.modules,
                {
                    "oracle_docs_runner": SimpleNamespace(
                        preview_for_binding=lambda _store, _binding: {
                            "id": self.preview_id,
                            "parent": self.preview_id,
                        },
                        target_for_observation=lambda *_args, **_kwargs: {
                            "synthetic_target": True
                        },
                        validate_native=validate,
                    )
                },
            )
        )

    def sign(self, raw):
        public = self.root / "native-fixture-public.pem"
        public.write_text(self.public_native)
        public.chmod(0o600)
        return base64.b64encode(owner.signed_bytes(self.key, public, raw)).decode()

    def registered(self, *, commissioned=True):
        result = native.register(self.store, self.binding, self.public_native)["record"]
        if commissioned:
            native.commission(
                self.store, result["id"], self.sign(native.possession(result))
            )
        return result

    def session(self):
        registered = self.registered()
        context = self.store.issue_context(self.binding)["record"]
        challenge = native.begin_qualification(
            self.store, context["id"], registered["id"]
        )["record"]
        return registered, context, challenge

    def envelope(self, registered, challenge, **changes):
        payload = {
            "purpose": native.DOMAIN,
            "schema_version": 1,
            "receipt_id": str(uuid4()),
            "challenge_id": challenge["id"],
            "registration_id": registered["id"],
            "binding": copy.deepcopy(self.binding),
            "workflow_run_id": 0,
            "environment": "staging",
            "observed_at": self.store.clock().isoformat(),
            "producer_sha256": "9" * 64,
            "evidence": {"synthetic_fixture": True},
        }
        payload.update(changes)
        return {"payload": payload, "signature": self.sign(owner.canonical(payload))}

    def test_registration_is_untrusted_until_separate_commission_and_possession(self):
        registered = self.registered(commissioned=False)
        self.assertFalse((self.root / "native-trust.json").exists())
        with self.assertRaises(owner.Rejected):
            native.active(self.store, registered["id"], self.binding)
        with self.assertRaises(owner.Rejected):
            native.commission(
                self.store, registered["id"], base64.b64encode(b"x" * 64).decode()
            )
        native.commission(
            self.store, registered["id"], self.sign(native.possession(registered))
        )
        self.assertEqual(
            native.active(self.store, registered["id"], self.binding)["id"],
            registered["id"],
        )

    def test_valid_zero_run_native_receipt_is_not_authorization_and_context_consumes_once(
        self,
    ):
        registered, context, challenge = self.session()
        signed = self.envelope(registered, challenge)
        record = native.import_observation(self.store, owner.canonical(signed))[
            "record"
        ]
        self.assertEqual(record["workflow_run_id"], 0)
        self.assertFalse(record["details"]["production_deployment_authorized"])
        self.assertEqual(
            self.store.db.execute(
                "SELECT state FROM contexts WHERE id=?", (context["id"],)
            ).fetchone()[0],
            "reserved",
        )
        qualification = native.complete_qualification(self.store, context["id"])[
            "record"
        ]
        self.assertEqual(qualification["kind"], "qualification")
        with self.assertRaises(owner.Rejected):
            native.complete_qualification(self.store, context["id"])
        self.assertEqual(
            self.store.db.execute("SELECT count(*) FROM deployments").fetchone()[0], 0
        )

    def test_unsigned_modified_foreign_and_uncommissioned_payloads_refuse(self):
        registered, _context, challenge = self.session()
        envelope = self.envelope(registered, challenge)
        changed = copy.deepcopy(envelope)
        changed["payload"]["evidence"] = {"synthetic_fixture": False}
        with self.assertRaises(owner.Rejected):
            native.import_observation(self.store, owner.canonical(changed))
        for bad in [
            {"payload": envelope["payload"]},
            {"payload": envelope["payload"], "signature": "PASS"},
        ]:
            with self.subTest(bad=bad.keys()), self.assertRaises(owner.Rejected):
                native.import_observation(self.store, owner.canonical(bad))
        anchor = json.loads((self.root / "native-trust.json").read_bytes())
        anchor["producers"][registered["id"]]["active"] = False
        (self.root / "native-trust.json").write_bytes(owner.canonical(anchor))
        with self.assertRaises(owner.Rejected):
            native.import_observation(self.store, owner.canonical(envelope))

    def test_actions_run_wrong_component_source_environment_or_artifact_refuse(self):
        registered, _context, challenge = self.session()
        for changes in [
            {"workflow_run_id": 123},
            {"workflow_run_id": False},
            {"environment": "production"},
            {"producer_sha256": "8" * 64},
            {"purpose": "actions-owner-approval"},
        ]:
            with self.subTest(changes=changes), self.assertRaises(owner.Rejected):
                native.import_observation(
                    self.store,
                    owner.canonical(self.envelope(registered, challenge, **changes)),
                )
        for field, value in [
            ("candidate_commit", "b" * 40),
            ("artifact_digest", "sha256:" + "2" * 64),
            ("component", "docs-internal"),
            ("target_environment", "staging"),
        ]:
            binding = {**self.binding, field: value}
            with self.subTest(field=field), self.assertRaises(owner.Rejected):
                native.import_observation(
                    self.store,
                    owner.canonical(
                        self.envelope(registered, challenge, binding=binding)
                    ),
                )

    def test_expired_future_revoked_incomplete_native_evidence_refuses(self):
        registered, _context, challenge = self.session()
        for offset in [-301, 60]:
            stamp = (self.store.clock() + timedelta(seconds=offset)).isoformat()
            with self.subTest(offset=offset), self.assertRaises(owner.Rejected):
                native.import_observation(
                    self.store,
                    owner.canonical(
                        self.envelope(registered, challenge, observed_at=stamp)
                    ),
                )
        for evidence in [{}, {"synthetic_fixture": False}, {"mandatory": "skipped"}]:
            with self.subTest(evidence=evidence), self.assertRaises(owner.Rejected):
                native.import_observation(
                    self.store,
                    owner.canonical(
                        self.envelope(registered, challenge, evidence=evidence)
                    ),
                )
        envelope = self.envelope(registered, challenge)
        self.store.revoke(registered["id"])
        with self.assertRaises(owner.Rejected):
            native.import_observation(self.store, owner.canonical(envelope))

    def test_concurrent_begin_reserves_one_context_and_emits_one_challenge(self):
        registered = self.registered()
        context = self.store.issue_context(self.binding)["record"]
        barrier = threading.Barrier(2)

        def attempt(_):
            store = self.open()
            try:
                barrier.wait(timeout=10)
                return native.begin_qualification(
                    store, context["id"], registered["id"]
                )["record"]["id"]
            except owner.Rejected:
                return None
            finally:
                store.db.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertEqual(sum(value is not None for value in results), 1)
        self.assertEqual(
            self.store.db.execute(
                "SELECT count(*) FROM records WHERE kind=?", (native.CHALLENGE,)
            ).fetchone()[0],
            1,
        )

    def test_changed_source_and_interrupted_completion_never_issue_qualification(self):
        registered, context, challenge = self.session()
        native.import_observation(
            self.store, owner.canonical(self.envelope(registered, challenge))
        )
        self.ci.fail = True
        with self.assertRaises(owner.Rejected):
            native.complete_qualification(self.store, context["id"])
        self.ci.fail = False
        with self.assertRaises(owner.Rejected):
            native.complete_qualification(self.store, context["id"])
        self.assertEqual(
            self.store.db.execute(
                "SELECT count(*) FROM records WHERE kind='qualification'"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.store.db.execute("SELECT count(*) FROM deployments").fetchone()[0], 0
        )

    def test_receipt_reimport_is_inspection_only_and_different_evidence_cannot_reuse_nonce(
        self,
    ):
        registered, _context, challenge = self.session()
        envelope = self.envelope(registered, challenge)
        first = native.import_observation(self.store, owner.canonical(envelope))
        again = native.import_observation(self.store, owner.canonical(envelope))
        self.assertEqual(first["record"]["id"], again["record"]["id"])
        with self.assertRaises(owner.Rejected):
            native.import_observation(
                self.store, owner.canonical(self.envelope(registered, challenge))
            )

    def test_wrong_key_or_duplicate_json_cannot_enter_the_owner_store(self):
        registered, _context, challenge = self.session()
        envelope = self.envelope(registered, challenge)
        self.key.write_bytes(type(self).key)
        envelope["signature"] = self.sign(owner.canonical(envelope["payload"]))
        with self.assertRaises(owner.Rejected):
            native.import_observation(self.store, owner.canonical(envelope))
        with self.assertRaises(owner.Rejected):
            native.decode(b'{"payload":{},"payload":{},"signature":"x"}')


if __name__ == "__main__":
    unittest.main()
