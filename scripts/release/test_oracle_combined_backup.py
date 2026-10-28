"""Combined activation must not inherit a backup from the previous container."""

import copy
import datetime as dt
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import oracle_ai_runner as r


class CombinedBackupTests(unittest.TestCase):
    def setUp(self):
        self.binding = {"component": "cybersecurity-api", "candidate_commit": "a" * 40}
        self.runtime = {
            "source_commit": "a" * 40,
            "image": "sha256:" + "e" * 64,
            "container_id": "f" * 64,
            "runtime_sha256": "d" * 64,
        }
        self.row = {
            "Config": {"Labels": {"org.onesa.source-commit": "a" * 40}},
            "Image": self.runtime["image"],
            "Id": self.runtime["container_id"],
        }
        self.plan = {
            "mode": "cybersecurity",
            "storage": {"production": "/private/twins"},
        }
        self.registration = {
            "storage_root": "/private/twins",
            "source_commit": "b" * 40,
            "release_candidate_commit": "a" * 40,
            "producer_sha256": "c" * 64,
            "automatic_deletion": False,
            "cap_bytes": 64 * 1024 * 1024,
        }
        self.observation = {
            "status": "PASS",
            "coordinated_snapshot": True,
            "encrypted": True,
            "off_instance_readback": "PASS",
            "source_commit": "b" * 40,
            "release_candidate_commit": "a" * 40,
            "application_runtime": self.runtime,
            "producer_sha256": "c" * 64,
            "verified_at": r.now().isoformat(),
        }

    def observe(self, value):
        with (
            patch.object(r, "read", return_value=self.registration),
            patch.object(r, "private", side_effect=lambda p, **_kw: Path(p)),
            patch.object(
                r,
                "sha",
                side_effect=lambda path: (
                    "d" * 64 if path == r.ENV["production"] else "c" * 64
                ),
            ),
            patch.object(
                r, "trusted_toolchain", return_value={"source_commit": "b" * 40}
            ),
            patch.object(
                r, "inventory", return_value={r.TARGET["production"]: self.row}
            ),
            patch.object(
                r, "command", return_value=json.dumps(value).encode()
            ) as command,
        ):
            result = r.coordinated_backup_observation(self.binding, self.plan)
            self.assertEqual(command.call_args.args[0][-1], "--inspect")
            return result

    def test_exact_current_runtime_and_ciphertext_readback_are_required(self):
        result = self.observe(self.observation)
        self.assertEqual(result["application_runtime"], self.runtime)
        self.assertEqual(result["off_instance_readback"], "PASS")
        for key, value in [
            ("container_id", "0" * 64),
            ("runtime_sha256", "0" * 64),
            ("source_commit", "0" * 40),
            ("image", "sha256:" + "0" * 64),
        ]:
            observed = copy.deepcopy(self.observation)
            observed["application_runtime"][key] = value
            with self.subTest(key=key), self.assertRaises(r.Refused):
                self.observe(observed)
        for key, value in [
            ("status", "FAIL"),
            ("coordinated_snapshot", False),
            ("encrypted", False),
            ("off_instance_readback", "SKIP"),
            ("source_commit", "0" * 40),
            ("release_candidate_commit", "0" * 40),
            ("producer_sha256", "0" * 64),
            ("verified_at", (r.now() - dt.timedelta(hours=37)).isoformat()),
        ]:
            observed = {**self.observation, key: value}
            with self.subTest(key=key), self.assertRaises(r.Refused):
                self.observe(observed)

    def test_production_activation_refreshes_backups_for_either_mode_with_twins(self):
        for mode, enabled in [
            ("twins", {"twins"}),
            ("cybersecurity", {"twins", "cybersecurity"}),
            ("cybersecurity", {"cybersecurity"}),
            ("foundation", set()),
        ]:
            binding = {
                **self.binding,
                "component": "api" if mode == "foundation" else mode + "-api",
            }
            values = {
                "ONESA_DIGITAL_TWINS_ENABLED": "true"
                if "twins" in enabled
                else "false",
                "ONESA_CYBERSECURITY_ENABLED": "true"
                if "cybersecurity" in enabled
                else "false",
            }
            with (
                self.subTest(mode=mode),
                patch.object(
                    r, "inventory", return_value={r.TARGET["production"]: self.row}
                ),
                patch.object(r, "running_configuration", return_value=values),
                patch.object(r, "command") as command,
                patch.object(
                    r,
                    "operational_observations",
                    return_value={"actual": "current-runtime-backup"},
                ) as observe,
            ):
                result = r.post_deployment_backup(binding, {"mode": mode})
                if "twins" in enabled:
                    self.assertEqual(result, {"actual": "current-runtime-backup"})
                    command.assert_called_once()
                    self.assertEqual(
                        Path(command.call_args.args[0][-1]).name, "oracle_ai_backup.py"
                    )
                    observe.assert_called_once()
                else:
                    self.assertIsNone(result)
                    command.assert_not_called()
                    observe.assert_not_called()

    def test_backup_failure_cannot_return_an_operational_pass(self):
        with (
            patch.object(
                r, "inventory", return_value={r.TARGET["production"]: self.row}
            ),
            patch.object(
                r,
                "running_configuration",
                return_value={
                    "ONESA_DIGITAL_TWINS_ENABLED": "true",
                    "ONESA_CYBERSECURITY_ENABLED": "true",
                },
            ),
            patch.object(
                r, "command", side_effect=r.Refused("SYNTHETIC_BACKUP_FAILURE")
            ),
            patch.object(r, "operational_observations") as observe,
            self.assertRaises(r.Refused),
        ):
            r.post_deployment_backup(self.binding, self.plan)
        observe.assert_not_called()

    def test_cybersecurity_operations_refuse_stale_twins_backup_before_authorization(
        self,
    ):
        # All other prerequisites are synthetic successful fixtures. Only the
        # coordinated snapshot result varies; no real record or credential exists.
        import oracle_ai_frontend as frontend

        operation = "11111111-1111-4111-8111-111111111111"
        replacement = {"restore_receipt_sha256": "c" * 64}
        restored = {
            "binding": self.binding,
            "operation_id": operation,
            "status": "PASS",
            "profile": "cybersecurity",
            "schema_revision": "20261026_cybersecurity",
            "production_writes": 0,
            "database_manifest_matches": True,
            "encrypted_fixture_recovery": "PASS",
            "fixture_owners": 2,
        }
        hosted = {
            "binding": self.binding,
            "controlled_replacement": replacement,
            "status": "PASS",
            "fixture_identities_disabled": True,
            "existing_records_preserved": True,
        }
        metrics = {
            "simulation": False,
            "alerts": [],
            "checked_at": r.now().isoformat(),
            "metrics": {
                "database_available": True,
                "database_backup_failed": False,
                "memory_available_bytes": 3 * 1024**3,
                "disk_used_percent": 50,
            },
        }
        backup = {"consistent_snapshot": True, "verified_at": r.now().isoformat()}
        plan = {
            **self.plan,
            "artifact_folder": "/synthetic/artifacts",
            "qualification_context_id": operation,
            "rollback": {
                "image": "sha256:" + "d" * 64,
                "retain_additive_schema_and_files": True,
            },
        }

        def read(path):
            name = Path(path).name
            return {
                "metrics.json": metrics,
                "database-backup-ai-success.json": backup,
                "restore-receipt.json": restored,
                "replacement-ok.json": replacement,
                "receipt.json": hosted,
            }[name]

        for twins, failure in [(False, False), (True, False), (True, True)]:
            with (
                self.subTest(twins=twins, failure=failure),
                patch.object(frontend, "observe_provider", return_value={}),
                patch.object(frontend, "verify_retained_frontend"),
                patch.object(r, "read", side_effect=read),
                patch.object(r, "sha", return_value="c" * 64),
                patch.object(r, "command", return_value=b"active"),
                patch.object(
                    r, "inspect_database_backup", return_value={"readback": "synthetic"}
                ),
                patch.object(
                    r, "accepted_rollback_proof", return_value="synthetic-rollback"
                ),
                patch.object(
                    r,
                    "docker",
                    return_value=json.dumps(
                        [{"Id": plan["rollback"]["image"]}]
                    ).encode(),
                ),
                patch.object(
                    r,
                    "runtime_values",
                    return_value={
                        "ONESA_DIGITAL_TWINS_ENABLED": "true" if twins else "false",
                        "ONESA_CYBERSECURITY_ENABLED": "true",
                    },
                ),
                patch.object(
                    r,
                    "coordinated_backup_observation",
                    return_value={"current-runtime": True},
                    side_effect=r.Refused("SYNTHETIC_STALE_TWINS_BACKUP")
                    if failure
                    else None,
                ) as coordinated,
            ):
                if failure:
                    with self.assertRaises(r.Refused):
                        r.operational_observations(self.binding, plan)
                else:
                    result = r.operational_observations(self.binding, plan)
                    self.assertEqual(
                        result["coordinated_backup"],
                        {"current-runtime": True} if twins else None,
                    )
                self.assertEqual(coordinated.call_count, 1 if twins else 0)
