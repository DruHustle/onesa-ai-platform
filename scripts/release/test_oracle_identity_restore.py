"""Source-bound identity restore and retained-image failures, without live services."""

import copy
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import oracle_ai_runner as r
import oracle_identity_rollback as rollback
import oracle_twin_restore as restore
from test_oracle_ai_identity_release import fixture
from test_oracle_identity_rollback_cleanup import DockerFixture


def bundle_fixture():
    binding, plan, _, _ = fixture()
    selected = plan["identity"]["environments"]["staging"]
    accounts = selected["accounts"]
    owners = [account["local_user_id"] for account in accounts.values()]
    tables = {name: [{"user_id": owners[0]}] for name in restore.CYBER_TABLES}
    tables["users"] = [
        {"id": account["local_user_id"], "email": account["email"], "status": "active"}
        for account in accounts.values()
    ]
    tables["shared_identities"] = [
        {
            "id": str(uuid4()),
            "user_id": account["local_user_id"],
            "issuer": selected["issuer"],
            "subject": account["subject"],
        }
        for account in accounts.values()
    ]
    operation = str(uuid4())
    return (
        binding,
        plan,
        operation,
        {
            "binding": binding,
            "operation_id": operation,
            "scope": "existing-owned-identity-fixtures-only",
            "profile": "cybersecurity",
            "tables": tables,
        },
    )


class IdentityRestoreTests(unittest.TestCase):
    def test_exact_existing_principals_and_durable_mappings_replace_no_legacy_scope(
        self,
    ):
        binding, plan, operation, bundle = bundle_fixture()
        self.assertEqual(restore.validate(bundle, binding, operation, plan=plan), [])
        self.assertEqual(
            restore.fixture_tables(bundle)[:2], ["users", "shared_identities"]
        )
        changed = copy.deepcopy(bundle)
        changed["binding"]["component"] = "cybersecurity-api"
        with self.assertRaisesRegex(r.Refused, "FIXTURE_BINDING"):
            restore.validate(changed, changed["binding"], operation, plan=plan)

    def test_foreign_mapping_user_email_or_profile_never_enters_restore(self):
        binding, plan, operation, bundle = bundle_fixture()
        for mutation in [
            "subject",
            "issuer",
            "local",
            "email",
            "disabled",
            "duplicate",
            "foreign_data",
            "old_schema",
            "old_scope",
        ]:
            changed, selected = copy.deepcopy(bundle), copy.deepcopy(plan)
            mappings, users = (
                changed["tables"]["shared_identities"],
                changed["tables"]["users"],
            )
            if mutation == "subject":
                mappings[0]["subject"] = str(uuid4())
            elif mutation == "issuer":
                mappings[0]["issuer"] = "https://foreign.example/api/v1/identity"
            elif mutation == "local":
                mappings[0]["user_id"] = str(uuid4())
            elif mutation == "email":
                users[0]["email"] = "foreign@example.test"
            elif mutation == "disabled":
                users[0]["status"] = "disabled"
            elif mutation == "duplicate":
                mappings[1] = mappings[0]
            elif mutation == "foreign_data":
                changed["tables"]["cyber_events"][0]["user_id"] = str(uuid4())
            elif mutation == "old_schema":
                selected["expected_schema_revision"] = "20261026_cybersecurity"
            else:
                changed["scope"] = "new-owned-release-fixtures-only"
            with self.subTest(mutation=mutation), self.assertRaises(r.Refused):
                restore.validate(changed, binding, operation, plan=selected)

    def test_identity_restore_revision_preserves_the_actual_native_workflow(self):
        binding, plan, _, _ = fixture()
        for twins, cyber, expected in [
            (True, True, "twins"),
            (True, False, "twins"),
            (False, True, "cybersecurity"),
            (False, False, "foundation"),
        ]:
            values = {
                "ONESA_DIGITAL_TWINS_ENABLED": str(twins).lower(),
                "ONESA_CYBERSECURITY_ENABLED": str(cyber).lower(),
            }
            with patch.object(r, "runtime_values", return_value=values):
                for profile in ["twins", "cybersecurity"]:
                    with self.subTest(twins=twins, cyber=cyber, profile=profile):
                        if profile == expected:
                            self.assertEqual(
                                restore.restore_revision(plan, binding, profile),
                                r.IDENTITY_SCHEMA,
                            )
                        else:
                            with self.assertRaisesRegex(r.Refused, "SCHEMA_PROFILE"):
                                restore.restore_revision(plan, binding, profile)


class RollbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.binding, self.plan, current, _ = fixture()
        self.binding["target_environment"] = "production"
        self.binding["configuration_sha256"] = {}
        retained = {
            **self.binding,
            "component": "twins-api",
            "candidate_commit": "1" * 40,
            "artifact_digest": "sha256:" + "2" * 64,
            "configuration_sha256": {},
        }
        self.plan.update(
            {
                "verifier_store": "/synthetic-verifier",
                "rollback": {
                    "binding": retained,
                    "image": retained["artifact_digest"],
                    "operation_id": str(uuid4()),
                    "compatible_schema_revision": r.IDENTITY_SCHEMA,
                    "retain_additive_schema_and_files": True,
                },
            }
        )
        self.operation = str(uuid4())
        self.paths = {}
        for environment, values in current.items():
            for selected, configuration in [
                (self.binding, values),
                (
                    retained,
                    {
                        key: value
                        for key, value in values.items()
                        if key not in r.IDENTITY_KEYS
                    },
                ),
            ]:
                path = self.folder / (
                    selected["component"] + "-" + environment + ".env"
                )
                path.write_text(
                    "".join(
                        key + "=" + value + "\n" for key, value in configuration.items()
                    )
                )
                selected["configuration_sha256"][environment] = r.sha(path)
                self.paths[(selected["component"], environment)] = path
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(
            patch.object(r, "private", side_effect=lambda path, **kw: Path(path))
        )
        self.stack.enter_context(
            patch.object(
                r,
                "candidate_environment",
                side_effect=lambda binding, env: self.paths[
                    (binding["component"], env)
                ],
            )
        )
        self.verify = self.stack.enter_context(
            patch.object(r, "verify_invocation", return_value=[])
        )

    def test_both_native_configurations_are_accepted_and_exactly_hash_bound(self):
        result = rollback.bound_environments(self.binding, self.plan)
        self.assertEqual(set(result), {"staging", "production"})
        self.assertTrue(
            all(
                row["enabled_features"] == ["cybersecurity", "twins"]
                and row["identity_enabled"] is False
                for row in result.values()
            )
        )
        self.assertTrue(self.verify.call_args.kwargs["dependency"])
        self.assertEqual(
            self.verify.call_args.args[0], self.plan["rollback"]["binding"]
        )
        self.paths[("twins-api", "production")].write_text(
            "ONESA_IDENTITY_ENABLED=false\n"
        )
        with self.assertRaisesRegex(r.Refused, "CONFIGURATION_BINDING"):
            rollback.bound_environments(self.binding, self.plan)

    def test_retained_identity_enable_or_native_flag_changes_refuse_even_if_hash_bound(
        self,
    ):
        for change in [
            "ONESA_DIGITAL_TWINS_ENABLED=false",
            "ONESA_IDENTITY_ENABLED=true",
        ]:
            path = self.paths[("twins-api", "staging")]
            original = path.read_text()
            key = change.split("=", 1)[0]
            path.write_text(
                "\n".join(
                    line
                    for line in original.splitlines()
                    if not line.startswith(key + "=")
                )
                + "\n"
                + change
                + "\n"
            )
            self.plan["rollback"]["binding"]["configuration_sha256"]["staging"] = r.sha(
                path
            )
            with self.subTest(change=change), self.assertRaises(r.Refused):
                rollback.bound_environments(self.binding, self.plan)
            path.write_text(original)
            self.plan["rollback"]["binding"]["configuration_sha256"]["staging"] = r.sha(
                path
            )
        self.verify.side_effect = r.Refused("ACCEPTED_API_VERIFICATION_REQUIRED")
        with self.assertRaisesRegex(r.Refused, "ACCEPTED_API"):
            rollback.bound_environments(self.binding, self.plan)

    def test_private_runtime_program_has_no_hosted_authority_or_credential_mount(self):
        response = {
            "enabled_features": ["twins"],
            "identity_enabled": False,
            "checks": {key: "PASS" for key in rollback.CHECKS},
            "fixture": {"synthetic": True},
        }
        owned = rollback.OwnedContainer(
            self.folder,
            self.operation,
            "staging-seed",
            self.binding["artifact_digest"],
            binds=[(self.folder, "/var/run/postgresql", False)],
        )
        with patch.object(owned, "run", return_value=r.canonical(response)) as execute:
            self.assertEqual(
                rollback.application(
                    self.binding["artifact_digest"],
                    self.folder,
                    "onesa_identity_rollback_test",
                    ["twins"],
                    owned=owned,
                ),
                response,
            )
        args, kwargs = execute.call_args.args, execute.call_args.kwargs
        self.assertEqual(args, ("python", ["-c", rollback.PROGRAM]))
        self.assertIn("ONESA_IDENTITY_ENABLED=false", kwargs["environment"])
        self.assertEqual(len(kwargs["environment"]), 3)
        self.assertIn(
            "ONESA_DATABASE_URL=postgresql+psycopg://onesa_restore@/onesa_identity_rollback_test?host=/var/run/postgresql",
            kwargs["environment"],
        )
        self.assertEqual(json.loads(kwargs["data"])["phase"], "seed")
        with self.assertRaises(r.Refused):
            rollback.application(
                self.binding["artifact_digest"],
                self.folder,
                "neondb",
                ["twins"],
                owned=owned,
            )
        response["checks"]["native_features"] = "SKIPPED"
        with (
            patch.object(owned, "run", return_value=r.canonical(response)),
            self.assertRaisesRegex(r.Refused, "CANNOT_SERVE"),
        ):
            rollback.application(
                self.binding["artifact_digest"],
                self.folder,
                "onesa_identity_rollback_test",
                ["twins"],
                owned=owned,
            )

    def fake_docker(self, changed_manifest=False, changed_cleanup=False):
        daemon = DockerFixture(self.folder, self.binding, self.plan, self.operation)
        self.commands = daemon.commands
        daemon.manifest_changed = changed_manifest
        if changed_cleanup:

            def changed(role, cidfile, row):
                if role == "database":
                    row["HostConfig"]["NetworkMode"] = "host"

            daemon.after_run = changed
        return daemon

    def application(self, image, socket, database, enabled, *, owned, fixture=None):
        result = {
            "enabled_features": enabled,
            "identity_enabled": False,
            "checks": {key: "PASS" for key in rollback.CHECKS},
        }
        if fixture is None:
            result["fixture"] = {"owned": "synthetic-only"}
        return result

    def test_receipt_requires_both_exact_images_restore_and_original_flags(self):
        with (
            patch.object(r, "docker", side_effect=self.fake_docker()),
            patch.object(rollback.os, "chown"),
            patch.object(
                rollback, "application", side_effect=self.application
            ) as application,
        ):
            observed = rollback.check(
                self.folder, self.binding, self.operation, self.plan
            )
        self.assertEqual(
            observed,
            json.loads((self.folder / "identity-rollback-receipt.json").read_text()),
        )
        self.assertEqual(observed["schema_revision"], r.IDENTITY_SCHEMA)
        self.assertEqual(observed["production_writes"], 0)
        self.assertEqual(
            [call.args[0] for call in application.call_args_list],
            [self.binding["artifact_digest"], self.plan["rollback"]["image"]] * 2,
        )
        self.assertTrue(
            all(
                call.args[3] == ["cybersecurity", "twins"]
                for call in application.call_args_list
            )
        )
        self.assertTrue(any(args[:2] == ("rm", "-f") for args, _ in self.commands))
        self.assertFalse((self.folder / "identity-rollback-socket").exists())

    def test_incompatible_image_manifest_or_cleanup_never_leaves_success(self):
        for failure in ["image", "manifest", "cleanup"]:
            folder = self.folder / failure
            folder.mkdir()

            def application(*args, selected_failure=failure, **kwargs):
                if (
                    selected_failure == "image"
                    and args[0] == self.plan["rollback"]["image"]
                ):
                    raise r.Refused("RETAINED_IMAGE_CANNOT_SERVE_IDENTITY_SCHEMA")
                return self.application(*args, **kwargs)

            original = self.folder
            self.folder = folder
            try:
                with (
                    patch.object(
                        r,
                        "docker",
                        side_effect=self.fake_docker(
                            failure == "manifest", failure == "cleanup"
                        ),
                    ),
                    patch.object(rollback.os, "chown"),
                    patch.object(rollback, "application", side_effect=application),
                    self.subTest(failure=failure),
                    self.assertRaises(r.Refused),
                ):
                    rollback.check(folder, self.binding, self.operation, self.plan)
                self.assertFalse((folder / "identity-rollback-receipt.json").exists())
                self.assertEqual(
                    any(args[:2] == ("rm", "-f") for args, _ in self.commands),
                    failure != "cleanup",
                )
            finally:
                self.folder = original


if __name__ == "__main__":
    unittest.main()
