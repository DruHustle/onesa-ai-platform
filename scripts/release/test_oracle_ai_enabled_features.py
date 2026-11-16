"""Combined-feature evidence boundaries; all inputs and reports are disposable."""

import hashlib
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import oracle_ai_probe as p
import oracle_ai_runner as r


class EnabledFeatureEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.binding = {
            "repository": "DruHustle/onesa-ai-platform",
            "component": "cybersecurity-api",
            "candidate_commit": "a" * 40,
        }
        self.operation = str(uuid4())

    def report(self, **changes):
        return {
            "binding": self.binding,
            "operation_id": self.operation,
            "environment": "production",
            "workflow_run_id": 0,
            "source_commit": self.binding["candidate_commit"],
            "status": "PASS",
            "checks": {"twins_saved_state": "PASS"},
            **changes,
        }

    def test_other_feature_requires_its_exact_source_operation_and_success(self):
        invalid = [
            {"binding": {**self.binding, "candidate_commit": "b" * 40}},
            {"binding": {**self.binding, "component": "twins-api"}},
            {"operation_id": str(uuid4())},
            {"environment": "staging"},
            {"workflow_run_id": 123},
            {"workflow_run_id": False},
            {"source_commit": "b" * 40},
            {"status": "FAIL"},
            {"checks": {"twins_saved_state": "SKIP"}},
            {"checks": {}},
        ]
        for changes in [{}, *invalid]:
            with (
                self.subTest(changes=changes),
                tempfile.TemporaryDirectory() as directory,
                patch.object(p, "OUTPUT", Path(directory)),
                patch.object(p, "run_node") as run,
                patch.object(p, "private_json", return_value=self.report(**changes)),
            ):

                def invoke():
                    return p.feature_probe(
                        "twins",
                        "prepare",
                        "production",
                        self.binding,
                        self.operation,
                        "https://platform.onesa.eu",
                        [],
                        None,
                        {"PATH": "/synthetic"},
                    )

                if changes:
                    with self.assertRaises(p.Refused):
                        invoke()
                else:
                    self.assertEqual(invoke(), self.report())
                    self.assertEqual(run.call_args.kwargs["args"], [])
                    self.assertNotIn(
                        "ONESA_ORACLE_CYBERSECURITY_CONTEXT", run.call_args.args[1]
                    )

    def test_secondary_failure_after_primary_pass_keeps_failed_receipt_and_cleanup(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            plan = {
                "binding": self.binding,
                "mode": "cybersecurity",
                "expected_schema_revision": "20261026_cybersecurity",
            }
            plan_file = output / "plan.json"
            plan_file.write_text(json.dumps(plan))
            request = {
                "binding": self.binding,
                "operation_id": self.operation,
                "plan_sha256": hashlib.sha256(plan_file.read_bytes()).hexdigest(),
                "ci_run_id": 123,
            }
            engine = MagicMock()
            users = [{"id": str(uuid4())}, {"id": str(uuid4())}]
            settings = {
                "ONESA_PUBLIC_ORIGIN": "https://platform.onesa.eu",
                "ONESA_DIGITAL_TWINS_ENABLED": "true",
                "ONESA_CYBERSECURITY_ENABLED": "true",
            }
            phases = []

            def supplemental(feature, phase, *_args):
                phases.append((feature, phase))
                if phase == "verify":
                    raise p.Refused("SYNTHETIC_SECONDARY_FAILURE")
                return self.report()

            def read_private(path):
                if str(path) == "/private/plan.json":
                    return plan
                if str(path) == "/private/vercel.json":
                    return {
                        "backend_identity": {},
                        "project_id": "synthetic",
                        "retained_frontend": {
                            "served_static_artifact_verified": True,
                            "authority_transferred": False,
                            "new_frontend_deployment_requests": 0,
                            "deployment_id": "dpl_synthetic",
                            "binding": {"candidate_commit": "b" * 40},
                        },
                    }
                return {
                    "status": "PASS",
                    "checks": {"cybersecurity_ingestion": "PASS"},
                    "scope": "synthetic-only",
                }

            with (
                patch.object(p, "OUTPUT", output),
                patch.object(
                    p,
                    "Path",
                    side_effect=lambda value: (
                        plan_file if value == "/private/plan.json" else Path(value)
                    ),
                ),
                patch.object(p, "private_json", side_effect=read_private),
                patch.object(p, "runtime", return_value=settings),
                patch.object(
                    p,
                    "provider",
                    return_value=(
                        settings["ONESA_PUBLIC_ORIGIN"],
                        None,
                        {"deployment_id": "dpl_synthetic", "source": "b" * 40},
                    ),
                ),
                patch.object(p, "served_backend_identity", return_value={}),
                patch.object(p, "fixture_engine", return_value=engine),
                patch.object(
                    p, "fingerprints", return_value={"synthetic-existing": "unchanged"}
                ),
                patch.object(p, "create_fixtures", return_value=users),
                patch.object(p, "disable_fixtures") as cleanup,
                patch.object(
                    p, "ordinary_production", return_value={"existing": "PASS"}
                ),
                patch.object(p, "run_node") as primary,
                patch.object(p, "feature_probe", side_effect=supplemental),
                patch.dict(
                    "sys.modules",
                    {
                        "hosted": types.SimpleNamespace(),
                        "hosted_suite": types.SimpleNamespace(
                            Session=type("Session", (), {})
                        ),
                    },
                ),
                patch.dict("os.environ", {}, clear=True),
                self.assertRaisesRegex(p.Refused, "SYNTHETIC_SECONDARY_FAILURE"),
            ):
                p.execute("production", request)
            receipt = json.loads((output / "receipt.json").read_text())
            self.assertEqual(receipt["status"], "FAIL")
            self.assertEqual(receipt["checks"]["cybersecurity_ingestion"], "PASS")
            self.assertEqual(receipt["enabled_features"], ["cybersecurity", "twins"])
            self.assertTrue(receipt["fixture_identities_disabled"])
            self.assertTrue(receipt["existing_records_preserved"])
            self.assertEqual(phases, [("twins", "prepare"), ("twins", "verify")])
            self.assertEqual(primary.call_count, 2)
            self.assertFalse((output / "prepared-for-replacement.json").exists())
            cleanup.assert_called_once()
            engine.dispose.assert_called_once()

    def test_legacy_observations_cannot_cover_new_or_combined_feature_scopes(self):
        r.verify_observed_features({"component": "api"}, {}, "foundation", set())
        r.verify_observed_features({"component": "api"}, {}, "twins", {"twins"})
        for binding, observed, mode, enabled in [
            ({"component": "api"}, {}, "twins", {"twins", "cybersecurity"}),
            (self.binding, {}, "cybersecurity", {"cybersecurity"}),
            (
                self.binding,
                {"enabled_features": ["cybersecurity"]},
                "cybersecurity",
                {"twins", "cybersecurity"},
            ),
        ]:
            with (
                self.subTest(binding=binding, observed=observed),
                self.assertRaises(r.Refused),
            ):
                r.verify_observed_features(binding, observed, mode, enabled)
        r.verify_observed_features(
            self.binding,
            {"enabled_features": ["cybersecurity", "twins"]},
            "cybersecurity",
            {"twins", "cybersecurity"},
        )

    def test_runtime_flags_must_match_both_signed_configuration_and_running_container(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            configured = Path(directory) / "runtime.env"
            raw = (
                b"ONESA_DIGITAL_TWINS_ENABLED=true\nONESA_CYBERSECURITY_ENABLED=true\n"
            )
            configured.write_bytes(raw)
            configured.chmod(0o600)
            binding = {
                **self.binding,
                "configuration_sha256": {"production": hashlib.sha256(raw).hexdigest()},
            }
            live = {"Config": {"Env": [*raw.decode().splitlines(), "PATH=/synthetic"]}}
            with (
                patch.object(r, "ENV", {"production": configured}),
                patch.object(r, "private", side_effect=lambda path, **_kwargs: path),
            ):
                self.assertEqual(
                    r.running_configuration(binding, "production", live)[
                        "ONESA_DIGITAL_TWINS_ENABLED"
                    ],
                    "true",
                )
                for rows in [
                    [
                        "ONESA_DIGITAL_TWINS_ENABLED=false",
                        "ONESA_CYBERSECURITY_ENABLED=true",
                    ],
                    ["ONESA_DIGITAL_TWINS_ENABLED=true"],
                    [*live["Config"]["Env"], "ONESA_DIGITAL_TWINS_ENABLED=true"],
                    ["ONESA_DIGITAL_TWINS_ENABLED"],
                ]:
                    with self.subTest(rows=rows), self.assertRaises(r.Refused):
                        r.running_configuration(
                            binding, "production", {"Config": {"Env": rows}}
                        )
                configured.write_bytes(raw.replace(b"=true", b"=false"))
                with self.assertRaises(r.Refused):
                    r.running_configuration(binding, "production", live)


if __name__ == "__main__":
    unittest.main()
