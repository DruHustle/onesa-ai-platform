"""Adverse tests for identity release scope; no provider or owner record is issued."""

import base64
import copy
import datetime as dt
import hashlib
import json
import os
import stat
import tempfile
import types
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import oracle_ai_runner as r


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def fixture():
    binding = {
        "repository": r.profiles.REPOSITORY,
        "component": "identity-api",
        "candidate_commit": "a" * 40,
        "source_tree": "b" * 40,
        "source_sha256": "c" * 64,
        "artifact_digest": "sha256:" + "d" * 64,
    }
    identity = {
        "profile": "shared-identity-v1",
        "source_commit": binding["candidate_commit"],
        "source_tree": binding["source_tree"],
        "source_sha256": binding["source_sha256"],
        "credentials_sha256": "e" * 64,
        "environments": {},
    }
    runtimes, accounts = {}, {}
    for i, environment in enumerate(["staging", "production"]):
        issuer = (
            "https://portal-staging.onesa.eu" if i == 0 else "https://portal.onesa.eu"
        )
        origin = (
            "https://platform-staging.onesa.eu"
            if i == 0
            else "https://platform.onesa.eu"
        )
        secret = str(i) * 48
        encryption = base64.urlsafe_b64encode(bytes([i]) * 32).decode()
        values = {
            "ONESA_IDENTITY_ENABLED": "true",
            "ONESA_IDENTITY_ISSUER": issuer + "/api/v1/identity",
            "ONESA_IDENTITY_CLIENT_ID": "onesa-ai-client-" + environment,
            "ONESA_IDENTITY_CLIENT_SECRET": secret,
            "ONESA_IDENTITY_ENCRYPTION_KEY": encryption,
            "ONESA_IDENTITY_CALLBACK_URL": origin + "/api/v1/auth/onesa/callback",
            "ONESA_PUBLIC_ORIGIN": origin,
            "ONESA_ENVIRONMENT": environment,
            "ONESA_DATABASE_URL": "postgresql://runtime:synthetic@"
            + environment
            + ".example.test/onesa",
            "ONESA_DIGITAL_TWINS_ENABLED": "true",
            "ONESA_CYBERSECURITY_ENABLED": "true",
            "ONESA_MODEL_BACKEND": "ollama",
            "ONESA_SESSION_KEY": "retained-synthetic-key",
        }
        metadata = {
            "primary": {
                "subject": "00000000-0000-4000-8000-000000000001",
                "email": "onesa-acceptance-primary@example.test",
                "local_user_id": "00000000-0000-4000-8000-000000000003",
            },
            "foreign": {
                "subject": "00000000-0000-4000-8000-000000000002",
                "email": "onesa-acceptance-foreign@example.test",
                "local_user_id": "00000000-0000-4000-8000-000000000004",
            },
        }
        identity["environments"][environment] = {
            "issuer": values["ONESA_IDENTITY_ISSUER"],
            "client_id": values["ONESA_IDENTITY_CLIENT_ID"],
            "client_secret_sha256": digest(secret),
            "encryption_key_sha256": digest(encryption),
            "callback_url": values["ONESA_IDENTITY_CALLBACK_URL"],
            "portal_bypass_sha256": digest(""),
            "accounts": metadata,
        }
        runtimes[environment] = values
        accounts[environment] = {
            "portal_bypass": "",
            "accounts": {
                role: {
                    **row,
                    "password": "synthetic-credential-for-tests-only",
                    "local_password": "separate-native-synthetic-password",
                    "totp_secret": "JBSWY3DPEHPK3PXP",
                }
                for role, row in metadata.items()
            },
        }
    current = r.now()
    custody = {
        "schema_version": 1,
        "candidate_commit": binding["candidate_commit"],
        "created_at": (current - dt.timedelta(minutes=1)).isoformat(),
        "expires_at": (current + dt.timedelta(minutes=40)).isoformat(),
        "scope": "existing-owned-synthetic-identities",
        "environments": accounts,
    }
    plan = {
        "binding": binding,
        "mode": "identity",
        "identity": identity,
        "migration_revision": r.IDENTITY_SCHEMA,
        "expected_schema_revision": r.IDENTITY_SCHEMA,
    }
    return binding, plan, runtimes, custody


class IdentityReleaseTests(unittest.TestCase):
    def test_only_explicit_current_source_identity_profile_can_select_the_adapter(self):
        binding, plan, _, _ = fixture()
        self.assertIs(r.identity_profile(binding, plan), plan["identity"])
        for component in r.profiles.SCOPED:
            with self.subTest(component=component), self.assertRaises(ValueError):
                r.identity_profile({**binding, "component": component}, plan)
        for key in ["source_commit", "source_tree", "source_sha256", "profile"]:
            changed = copy.deepcopy(plan)
            changed["identity"][key] = "foreign"
            with self.subTest(key=key), self.assertRaises(ValueError):
                r.identity_profile(binding, changed)
        changed = copy.deepcopy(plan)
        changed["identity"]["extra_authority"] = True
        with self.assertRaises(ValueError):
            r.identity_profile(binding, changed)

    def test_identity_activation_preserves_every_native_runtime_setting(self):
        binding, plan, runtimes, _ = fixture()
        for environment, values in runtimes.items():
            current = {
                key: value
                for key, value in values.items()
                if key not in r.IDENTITY_KEYS
            }
            self.assertEqual(
                r.identity_runtime(binding, plan, environment, values, current),
                plan["identity"]["environments"][environment],
            )
            for key, value in [
                ("ONESA_DIGITAL_TWINS_ENABLED", "false"),
                ("ONESA_CYBERSECURITY_ENABLED", "false"),
                ("ONESA_MODEL_BACKEND", "mock"),
                ("ONESA_SESSION_KEY", "different"),
                ("ONESA_DATABASE_URL", values["ONESA_DATABASE_URL"] + "-other"),
            ]:
                changed = {**values, key: value}
                with (
                    self.subTest(environment=environment, key=key),
                    self.assertRaises(r.Refused),
                ):
                    r.identity_runtime(binding, plan, environment, changed, current)

    def test_mail_schema_requires_exact_plan_and_preserves_runtime_identity(self):
        binding, plan, runtimes, _ = fixture()
        values = runtimes["staging"]
        for schema in [r.IDENTITY_SCHEMA, r.MAIL_PRESENTATION_SCHEMA]:
            candidate = {
                **plan,
                "migration_revision": schema,
                "expected_schema_revision": schema,
            }
            self.assertTrue(
                r.identity_runtime(binding, candidate, "staging", values, values)
            )
        for migration, expected in [
            (r.MAIL_PRESENTATION_SCHEMA, r.IDENTITY_SCHEMA),
            (r.IDENTITY_SCHEMA, r.MAIL_PRESENTATION_SCHEMA),
            ("unknown", "unknown"),
        ]:
            candidate = {
                **plan,
                "migration_revision": migration,
                "expected_schema_revision": expected,
            }
            with (
                self.subTest(migration=migration, expected=expected),
                self.assertRaises(r.Refused),
            ):
                r.identity_runtime(binding, candidate, "staging", values, values)

    def test_enabled_identity_cannot_rotate_existing_credentials_or_issuer(self):
        binding, plan, runtimes, _ = fixture()
        values = runtimes["staging"]
        self.assertTrue(r.identity_runtime(binding, plan, "staging", values, values))
        current = {**values, "ONESA_IDENTITY_CLIENT_SECRET": "old-secret"}
        with self.assertRaisesRegex(r.Refused, "CANNOT_ROTATE"):
            r.identity_runtime(binding, plan, "staging", values, current)
        current = {**values, "ONESA_IDENTITY_ENABLED": "yes"}
        with self.assertRaises(r.Refused):
            r.identity_runtime(binding, plan, "staging", values, current)

    def test_fixed_issuer_and_callback_refuse_credential_egress_and_environment_crossover(
        self,
    ):
        binding, plan, _, _ = fixture()
        for environment, field, value in [
            ("staging", "issuer", "https://portal.onesa.eu/api/v1/identity"),
            ("production", "issuer", "https://foreign.example/api/v1/identity"),
            ("production", "issuer", "https://portal.onesa.eu:443/api/v1/identity"),
            (
                "production",
                "issuer",
                "https://user:password@portal.onesa.eu/api/v1/identity",
            ),
            (
                "production",
                "callback_url",
                "https://platform.onesa.eu/api/v1/auth/onesa/callback?next=x",
            ),
            (
                "staging",
                "callback_url",
                "https://attacker.example/api/v1/auth/onesa/callback",
            ),
            ("production", "portal_bypass_sha256", "f" * 64),
        ]:
            changed = copy.deepcopy(plan)
            changed["identity"]["environments"][environment][field] = value
            with (
                self.subTest(environment=environment, field=field, value=value),
                self.assertRaises(ValueError),
            ):
                r.identity_profile(binding, changed)

    def test_unknown_accounts_duplicate_owners_and_noncanonical_ids_are_refused(self):
        binding, plan, _, _ = fixture()
        for field, value in [
            ("subject", "not-a-uuid"),
            ("local_user_id", "00000000000040008000000000000003"),
            ("email", "invalid address"),
        ]:
            changed = copy.deepcopy(plan)
            changed["identity"]["environments"]["staging"]["accounts"]["primary"][
                field
            ] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                r.identity_profile(binding, changed)
        changed = copy.deepcopy(plan)
        accounts = changed["identity"]["environments"]["staging"]["accounts"]
        accounts["foreign"]["subject"] = accounts["primary"]["subject"]
        with self.assertRaises(ValueError):
            r.identity_profile(binding, changed)

    def test_invalid_fernet_key_wrong_secret_and_unbound_callback_are_refused(self):
        binding, plan, runtimes, _ = fixture()
        values = runtimes["staging"]
        current = {
            key: value for key, value in values.items() if key not in r.IDENTITY_KEYS
        }
        for key, value in [
            ("ONESA_IDENTITY_CLIENT_SECRET", "x" * 48),
            ("ONESA_IDENTITY_CALLBACK_URL", "https://other.example/callback"),
            ("ONESA_IDENTITY_ENABLED", "false"),
        ]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                r.identity_runtime(
                    binding, plan, "staging", {**values, key: value}, current
                )
        changed = copy.deepcopy(plan)
        changed["identity"]["environments"]["staging"]["encryption_key_sha256"] = (
            digest("not-fernet")
        )
        with self.assertRaisesRegex(r.Refused, "ENCRYPTION_KEY"):
            r.identity_runtime(
                binding,
                changed,
                "staging",
                {**values, "ONESA_IDENTITY_ENCRYPTION_KEY": "not-fernet"},
                current,
            )

    def test_custody_is_exact_source_hash_bounded_time_and_owned_accounts_only(self):
        binding, plan, _, custody = fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "custody.json"

            def seal(value):
                path.write_bytes(r.canonical(value))
                plan["identity"]["credentials_sha256"] = r.identity_credentials_digest(
                    value
                )

            with (
                patch.object(r, "IDENTITY_CREDENTIALS", path),
                patch.object(r, "private", side_effect=lambda path, **kw: Path(path)),
            ):
                seal(custody)
                self.assertEqual(r.identity_credentials(binding, plan), path)
                changed_bytes = copy.deepcopy(custody)
                changed_bytes["environments"]["production"]["accounts"]["primary"][
                    "password"
                ] = "unreviewed-credential-change"
                path.write_bytes(r.canonical(changed_bytes))
                with self.assertRaisesRegex(r.Refused, "CUSTODY"):
                    r.identity_credentials(binding, plan)
                for field, value in [
                    ("candidate_commit", "f" * 40),
                    ("scope", "production-users"),
                    ("expires_at", (r.now() - dt.timedelta(seconds=1)).isoformat()),
                    ("expires_at", (r.now() + dt.timedelta(hours=2)).isoformat()),
                    ("created_at", (r.now() + dt.timedelta(minutes=1)).isoformat()),
                    ("schema_version", True),
                ]:
                    changed = {**custody, field: value}
                    seal(changed)
                    with (
                        self.subTest(field=field, value=value),
                        self.assertRaises(ValueError),
                    ):
                        r.identity_credentials(binding, plan)
                changed = copy.deepcopy(custody)
                changed["environments"]["staging"]["accounts"]["primary"]["email"] = (
                    "another@example.test"
                )
                seal(changed)
                with self.assertRaisesRegex(r.Refused, "CREDENTIALS"):
                    r.identity_credentials(binding, plan)
                changed = copy.deepcopy(custody)
                changed["environments"]["production"]["portal_bypass"] = "unexpected"
                seal(changed)
                with self.assertRaises(ValueError):
                    r.identity_credentials(binding, plan)

    def test_every_native_feature_gate_survives_identity_mode(self):
        for component in r.profiles.IDENTITY:
            for features in [
                set(),
                {"twins"},
                {"cybersecurity"},
                {"twins", "cybersecurity"},
            ]:
                binding = {"component": component}
                checks = r.required_probe_checks(
                    binding, "staging", "identity", features
                )
                self.assertTrue(r.IDENTITY_CHECKS <= checks)
                self.assertTrue(
                    {
                        "authentication",
                        "owner_isolation",
                        "database_persistence",
                        "session_persistence",
                    }
                    <= checks
                )
                if "twins" in features:
                    self.assertTrue(
                        {"twins_saved_state", "twins_inspection", "file_persistence"}
                        <= checks
                    )
                if "cybersecurity" in features:
                    self.assertTrue(
                        {
                            "cybersecurity_decisions",
                            "cybersecurity_revocation",
                            "cybersecurity_ui",
                        }
                        <= checks
                    )
                if not features:
                    self.assertTrue(
                        {
                            "ordinary_workflows",
                            "twins_disabled",
                            "cybersecurity_disabled",
                        }
                        <= checks
                    )
        with self.assertRaisesRegex(r.Refused, "ACTUAL_ENABLED"):
            r.required_probe_checks(
                {"component": "identity-api"}, "staging", "identity"
            )

    def test_identity_cleanup_preserves_owned_accounts_and_retires_only_probe_sessions(
        self,
    ):
        binding, _, _, _ = fixture()
        valid = {
            "fixture_identities_preserved": True,
            "fixture_identities_disabled": False,
            "identity_sessions_retired": True,
            "existing_records_preserved": True,
        }
        self.assertTrue(r.fixture_cleanup_complete(binding, valid))
        for field, value in valid.items():
            with self.subTest(field=field):
                self.assertFalse(
                    r.fixture_cleanup_complete(binding, {**valid, field: not value})
                )
        legacy = {
            "fixture_identities_disabled": True,
            "existing_records_preserved": True,
        }
        self.assertFalse(r.fixture_cleanup_complete(binding, legacy))
        self.assertTrue(r.fixture_cleanup_complete({"component": "api"}, legacy))

    def test_runtime_fingerprint_binds_actual_configuration_without_revealing_it(self):
        row = {
            "Id": "1" * 64,
            "Image": "sha256:" + "2" * 64,
            "Config": {
                "Labels": {"org.onesa.source-commit": "a" * 40},
                "Env": ["SECRET=synthetic"],
            },
            "HostConfig": {"NetworkMode": "host"},
            "Mounts": [],
            "NetworkSettings": {"Networks": {"host": {"NetworkID": "actual-network"}}},
        }
        expected = r.runtime_target(row)
        self.assertEqual(
            set(expected),
            {"container_id", "image_id", "source_commit", "configuration_sha256"},
        )
        self.assertNotIn("synthetic", json.dumps(expected))
        changed = copy.deepcopy(row)
        changed["Config"]["Env"] = ["SECRET=other"]
        self.assertNotEqual(
            r.runtime_target(changed)["configuration_sha256"],
            expected["configuration_sha256"],
        )
        changed = copy.deepcopy(row)
        changed["NetworkSettings"]["Networks"]["host"]["NetworkID"] = "foreign"
        self.assertNotEqual(
            r.runtime_target(changed)["configuration_sha256"],
            expected["configuration_sha256"],
        )

    def test_identity_migration_requires_actual_twenty_four_table_grants(self):
        binding, plan, _, _ = fixture()
        runtime = {
            "ONESA_DATABASE_URL": "postgresql://synthetic:synthetic@example.test/onesa"
        }
        response = {
            "migration_revision": r.IDENTITY_SCHEMA,
            "runtime_DDL_granted": False,
            "runtime_new_tables_DML_granted": 24,
        }
        with (
            patch.object(r, "runtime_values", return_value=runtime),
            patch.object(r, "docker", return_value=r.canonical(response)) as docker,
        ):
            self.assertEqual(
                r.migrate(binding, "staging", "ignored-in-this-pure-adapter", plan),
                response,
            )
            request = json.loads(docker.call_args.kwargs["data"])
            self.assertEqual(request["target_revision"], r.IDENTITY_SCHEMA)
            for grants in [9, 21, 25]:
                docker.return_value = r.canonical(
                    {**response, "runtime_new_tables_DML_granted": grants}
                )
                with self.subTest(grants=grants), self.assertRaises(r.Refused):
                    r.migrate(binding, "staging", "ignored-in-this-pure-adapter", plan)

    def test_new_schema_rollback_requires_fresh_proof_for_both_native_configurations(
        self,
    ):
        binding, plan, _, _ = fixture()
        binding["target_environment"] = "production"
        old = {
            **binding,
            "component": "api",
            "candidate_commit": "f" * 40,
            "artifact_digest": "sha256:" + "e" * 64,
        }
        context = "00000000-0000-4000-8000-000000000005"
        plan.update(
            {
                "artifact_folder": "/private/current-artifact",
                "qualification_context_id": context,
                "verifier_store": "/private/current-store",
                "rollback": {
                    "binding": old,
                    "image": old["artifact_digest"],
                    "operation_id": "accepted-old-operation",
                },
            }
        )
        proof = {
            "binding": binding,
            "operation_id": context,
            "candidate_image": binding["artifact_digest"],
            "rollback_image": old["artifact_digest"],
            "retained_source": old["candidate_commit"],
            "schema_revision": r.IDENTITY_SCHEMA,
            "status": "PASS",
            "synthetic_database_restore": "PASS",
            "production_writes": 0,
            "environments": {
                environment: {
                    "enabled_features": ["twins"],
                    "identity_enabled": False,
                    "checks": {
                        key: "PASS"
                        for key in [
                            "core_readiness",
                            "local_authentication",
                            "ordinary_workflows",
                            "native_features",
                        ]
                    },
                }
                for environment in ["staging", "production"]
            },
        }
        with (
            patch.object(
                r,
                "verify_invocation",
                return_value=[{"kind": "context", "id": "accepted-old-context"}],
            ) as verify,
            patch.object(r, "read", return_value=proof) as read,
            patch.object(r, "sha", return_value="1" * 64),
            patch.object(
                r,
                "runtime_values",
                return_value={"ONESA_DIGITAL_TWINS_ENABLED": "true"},
            ),
        ):
            self.assertEqual(r.accepted_rollback_proof(plan), "1" * 64)
            mail_plan = {
                **plan,
                "migration_revision": r.MAIL_PRESENTATION_SCHEMA,
                "expected_schema_revision": r.MAIL_PRESENTATION_SCHEMA,
            }
            with self.assertRaisesRegex(r.Refused, "FRESH_IDENTITY_SCHEMA"):
                r.accepted_rollback_proof(mail_plan)
            read.return_value = {**proof, "schema_revision": r.MAIL_PRESENTATION_SCHEMA}
            self.assertEqual(r.accepted_rollback_proof(mail_plan), "1" * 64)
            with self.assertRaisesRegex(r.Refused, "FRESH_IDENTITY_SCHEMA"):
                r.accepted_rollback_proof(plan)
            read.return_value = proof
            self.assertTrue(verify.call_args.kwargs["dependency"])
            self.assertEqual(
                read.call_args.args[0].name, "identity-rollback-receipt.json"
            )
            for field, value in [
                ("schema_revision", "20261026_cybersecurity"),
                ("retained_source", binding["candidate_commit"]),
                ("rollback_image", binding["artifact_digest"]),
                ("production_writes", 1),
            ]:
                read.return_value = {**proof, field: value}
                with self.subTest(field=field), self.assertRaises(r.Refused):
                    r.accepted_rollback_proof(plan)
            changed = copy.deepcopy(proof)
            changed["environments"]["production"]["enabled_features"] = []
            read.return_value = changed
            with self.assertRaisesRegex(r.Refused, "PRESERVE_NATIVE"):
                r.accepted_rollback_proof(plan)
            read.return_value = proof
            verify.side_effect = r.Refused("OLD_ACCEPTANCE_REVOKED")
            with self.assertRaisesRegex(r.Refused, "REVOKED"):
                r.accepted_rollback_proof(plan)

            # A previously accepted native-profile bridge may use the same
            # immutable source/image, but identity activation has its own scope
            # and exact distinct runtime configurations in both environments.
            verify.side_effect = None
            bridge = copy.deepcopy(plan)
            bridge["binding"]["configuration_sha256"] = {env: "5" * 64 for env in r.ENV}
            bridge_old = bridge["rollback"]["binding"]
            bridge_old.update(
                candidate_commit=binding["candidate_commit"],
                artifact_digest=binding["artifact_digest"],
                configuration_sha256={env: "6" * 64 for env in r.ENV},
            )
            bridge["rollback"]["image"] = binding["artifact_digest"]
            read.return_value = {
                **proof,
                "binding": bridge["binding"],
                "rollback_image": binding["artifact_digest"],
                "retained_source": binding["candidate_commit"],
            }
            self.assertEqual(r.accepted_rollback_proof(bridge), "1" * 64)
            bridge_old["component"] = "identity-api"
            with self.assertRaisesRegex(r.Refused, "ROLLBACK_SOURCE"):
                r.accepted_rollback_proof(bridge)
            bridge_old["component"] = "api"
            bridge_old["configuration_sha256"]["production"] = "5" * 64
            with self.assertRaisesRegex(r.Refused, "ROLLBACK_SOURCE"):
                r.accepted_rollback_proof(bridge)


class IdentityCredentialRenewalTests(unittest.TestCase):
    def setUp(self):
        self.binding, self.plan, _, self.custody = fixture()
        created = r.now() - dt.timedelta(hours=2)
        self.custody.update(
            created_at=created.isoformat(),
            expires_at=(created + dt.timedelta(minutes=45)).isoformat(),
        )
        self.plan["identity"]["credentials_sha256"] = r.identity_credentials_digest(
            self.custody
        )
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.path = self.folder / "custody.json"
        self.path.write_bytes(r.canonical(self.custody))
        self.path.chmod(0o600)
        self.context = {"context_id": "11111111-1111-4111-8111-111111111111"}
        self.expiry = r.now() + dt.timedelta(minutes=35)
        self.records = [
            {
                "id": self.context["context_id"],
                "binding": self.binding,
                "expires_at": self.expiry.isoformat(),
            }
        ]
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(r, "IDENTITY_CREDENTIALS", self.path))
        self.stack.enter_context(
            patch.object(r, "private", side_effect=lambda path, **kw: Path(path))
        )
        self.artifact = self.stack.enter_context(
            patch.object(r, "artifact_folder", return_value=self.folder)
        )
        self.verify = self.stack.enter_context(
            patch.object(r, "verify_invocation", return_value=self.records)
        )
        self.stack.enter_context(patch.object(r.os, "geteuid", return_value=0))
        original_stat = os.fstat
        self.stack.enter_context(
            patch.object(
                r.os,
                "fstat",
                side_effect=lambda fd: types.SimpleNamespace(
                    st_uid=0,
                    st_nlink=original_stat(fd).st_nlink,
                    st_mode=original_stat(fd).st_mode,
                    st_ino=original_stat(fd).st_ino,
                ),
            )
        )
        self.stack.enter_context(patch.dict(r.os.environ, {}, clear=True))

    def renew(self):
        return r.renew_identity_credentials(
            self.binding, self.plan, self.context, "staging"
        )

    def test_failed_intent_directory_sync_preserves_custody_and_blocks_retry(self):
        original = self.path.read_bytes()
        real_sync = os.fsync

        def fail_intent_directory(descriptor):
            info = os.fstat(descriptor)
            folder = self.folder / "identity-credential-leases"
            if (
                stat.S_ISDIR(info.st_mode)
                and folder.exists()
                and info.st_ino == folder.stat().st_ino
            ):
                raise OSError("simulated intent directory sync failure")
            return real_sync(descriptor)

        with (
            patch.object(r.os, "fsync", side_effect=fail_intent_directory),
            self.assertRaises(OSError),
        ):
            self.renew()
        self.assertEqual(self.path.read_bytes(), original)
        with self.assertRaisesRegex(r.Refused, "INCOMPLETE_NO_AUTOMATIC_RETRY"):
            self.renew()

    def test_only_timestamps_renew_after_current_signed_context_without_changing_plan_or_payload(
        self,
    ):
        previous_plan, previous_payload = (
            copy.deepcopy(self.plan),
            r.identity_credentials_digest(self.custody),
        )
        with self.assertRaisesRegex(r.Refused, "FRESH_BOUNDED"):
            r.identity_credentials(self.binding, self.plan)
        self.assertEqual(self.renew(), self.path)
        renewed = json.loads(self.path.read_bytes())
        self.assertEqual(r.identity_credentials_digest(renewed), previous_payload)
        self.assertEqual(self.plan, previous_plan)
        self.assertLessEqual(
            dt.datetime.fromisoformat(renewed["expires_at"]), self.expiry
        )
        self.assertLessEqual(
            dt.datetime.fromisoformat(renewed["expires_at"])
            - dt.datetime.fromisoformat(renewed["created_at"]),
            dt.timedelta(hours=1),
        )
        receipt = json.loads(
            (
                self.folder
                / "identity-credential-leases"
                / (self.context["context_id"] + ".json")
            ).read_bytes()
        )
        self.assertEqual(
            (
                receipt["records_issued"],
                receipt["provider_requests"],
                receipt["runtime_configuration_changed"],
            ),
            (0, 0, False),
        )
        self.assertEqual(receipt["envelope_sha256"], r.sha(self.path))
        before = self.path.read_bytes()
        self.renew()
        self.assertEqual(self.path.read_bytes(), before)

    def test_wrong_phase_revoked_context_or_changed_secret_cannot_renew(self):
        for phase in ["operations", "production", "preflight"]:
            with (
                self.subTest(phase=phase),
                self.assertRaisesRegex(r.Refused, "OWNER_PHASE"),
            ):
                r.renew_identity_credentials(
                    self.binding, self.plan, self.context, phase
                )
        self.verify.side_effect = r.Refused("SYNTHETIC_REVOKED_CONTEXT")
        with self.assertRaisesRegex(r.Refused, "REVOKED"):
            self.renew()
        self.verify.side_effect = None
        changed = copy.deepcopy(self.custody)
        changed["environments"]["production"]["accounts"]["primary"]["password"] = (
            "unreviewed-password-change"
        )
        self.path.write_bytes(r.canonical(changed))
        with self.assertRaisesRegex(r.Refused, "CUSTODY"):
            self.renew()
        self.assertFalse((self.folder / "identity-credential-leases").exists())

    def test_lease_cannot_outlive_an_earlier_signed_qualification_ancestor(self):
        context = {
            "operation_id": self.context["context_id"],
            "authorization_id": "22222222-2222-4222-8222-222222222222",
        }
        earlier = r.now() + dt.timedelta(minutes=5)
        self.records.extend(
            [
                {
                    "id": context["authorization_id"],
                    "binding": self.binding,
                    "expires_at": self.expiry.isoformat(),
                },
                {
                    "id": "33333333-3333-4333-8333-333333333333",
                    "binding": self.binding,
                    "expires_at": earlier.isoformat(),
                },
            ]
        )
        r.renew_identity_credentials(self.binding, self.plan, context, "deploy")
        renewed = json.loads(self.path.read_bytes())
        self.assertEqual(dt.datetime.fromisoformat(renewed["expires_at"]), earlier)

    def test_changed_signed_chain_preserves_custody_and_retains_uncertain_intent(self):
        original = self.path.read_bytes()
        changed = copy.deepcopy(self.records)
        changed[0]["expires_at"] = (self.expiry + dt.timedelta(minutes=10)).isoformat()
        self.verify.side_effect = [self.records, changed]
        with self.assertRaisesRegex(r.Refused, "SIGNED_CHAIN_CHANGED"):
            self.renew()
        self.assertEqual(self.path.read_bytes(), original)
        folder = self.folder / "identity-credential-leases"
        self.assertTrue(
            (folder / (self.context["context_id"] + "-intent.json")).is_file()
        )
        self.assertFalse((folder / (self.context["context_id"] + ".json")).exists())
        self.verify.side_effect = None
        with self.assertRaisesRegex(r.Refused, "INCOMPLETE_NO_AUTOMATIC_RETRY"):
            self.renew()

    def test_concurrent_custody_change_is_preserved_and_leaves_an_uncertain_intent(
        self,
    ):
        changed = {**self.custody, "scope": "foreign-owner-change"}
        calls = 0

        def concurrent(*_args, **_kw):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.path.write_bytes(r.canonical(changed))
            return self.records

        self.verify.side_effect = concurrent
        with self.assertRaisesRegex(r.Refused, "CHANGED_DURING_RENEWAL"):
            self.renew()
        self.assertEqual(json.loads(self.path.read_bytes()), changed)
        self.assertTrue(
            (
                self.folder
                / "identity-credential-leases"
                / (self.context["context_id"] + "-intent.json")
            ).is_file()
        )
        self.assertFalse(
            (
                self.folder
                / "identity-credential-leases"
                / (self.context["context_id"] + ".json")
            ).exists()
        )

    def test_interrupted_envelope_replacement_cannot_be_automatically_retried(self):
        original = self.path.read_bytes()
        with (
            patch.object(
                r.os, "replace", side_effect=OSError("synthetic interruption")
            ),
            self.assertRaises(OSError),
        ):
            self.renew()
        self.assertEqual(self.path.read_bytes(), original)
        with self.assertRaisesRegex(r.Refused, "INCOMPLETE_NO_AUTOMATIC_RETRY"):
            self.renew()

    def test_frontend_lease_uses_its_independent_artifact_custody(self):
        import oracle_ai_frontend

        self.binding["component"] = "identity-frontend"
        frontend = self.folder / "frontend"
        frontend.mkdir(mode=0o700)
        with patch.object(oracle_ai_frontend, "artifact_folder", return_value=frontend):
            self.renew()
        self.artifact.assert_not_called()
        self.assertTrue(
            (
                frontend
                / "identity-credential-leases"
                / (self.context["context_id"] + ".json")
            ).is_file()
        )


if __name__ == "__main__":
    unittest.main()
