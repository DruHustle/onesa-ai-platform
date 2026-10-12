"""Production startup repair refuses scope drift and keeps data and release gates."""

import copy
import json
import unittest
from unittest.mock import patch

import production_startup as startup
from test_production_defaults import RenderFixture


class Provider(RenderFixture):
    def __init__(self, command="invalid-shell-command"):
        super().__init__()
        self.service["ownerId"] = "tea-d5h2r0p4tr6s739ae000"
        self.service["serviceDetails"].update(
            {
                "plan": "free",
                "region": "frankfurt",
                "envSpecificDetails": {
                    "dockerCommand": command,
                    "dockerfilePath": "./Dockerfile",
                },
            }
        )

    def call(self, path, token, payload=None):
        if payload is not None:
            assert path == "services/" + startup.SERVICE_ID
            assert payload == {
                "serviceDetails": {"envSpecificDetails": {"dockerCommand": ""}}
            }
            self.service["serviceDetails"]["envSpecificDetails"]["dockerCommand"] = ""
            self.writes.append(copy.deepcopy(payload))
            return copy.deepcopy(self.service)
        return super().call(path, token)


class StartupTests(unittest.TestCase):
    def test_repair_preserves_environment_and_deployment_without_disclosure(self):
        provider = Provider()
        original = copy.deepcopy(provider.environment)
        report = startup.repair("fixture", provider.call)
        self.assertTrue(report["startup_override_repaired"])
        self.assertEqual(len(provider.writes), 1)
        self.assertEqual(provider.environment, original)
        self.assertFalse(report["deployment_requested"])
        self.assertFalse(report["production_release_qualified"])
        self.assertNotIn(original["ONESA_DATABASE_URL"], json.dumps(report))

    def test_approved_commands_need_no_write(self):
        for command in (None, "", "sh /app/start.sh"):
            provider = Provider(command)
            self.assertFalse(
                startup.repair("fixture", provider.call)["startup_override_repaired"]
            )
            self.assertEqual(provider.writes, [])

    def test_wrong_target_or_auto_deploy_or_paid_plan_cannot_write(self):
        for field, value in (
            ("id", "srv-another"),
            ("branch", "staging"),
            ("autoDeployTrigger", "commit"),
            ("ownerId", "tea-another"),
        ):
            provider = Provider()
            provider.service[field] = value
            with self.assertRaises(startup.Refused):
                startup.repair("fixture", provider.call)
            self.assertEqual(provider.writes, [])
        for field, value in (
            ("plan", "starter"),
            ("region", "oregon"),
            ("env", "python"),
        ):
            provider = Provider()
            provider.service["serviceDetails"][field] = value
            with self.assertRaises(startup.Refused):
                startup.repair("fixture", provider.call)
            self.assertEqual(provider.writes, [])

    def test_inflight_deployment_cannot_write(self):
        provider = Provider()
        provider.deployment["status"] = "update_in_progress"
        with self.assertRaises(startup.Refused):
            startup.repair("fixture", provider.call)
        self.assertEqual(provider.writes, [])

    def test_concurrent_change_before_write_is_refused(self):
        provider = Provider()
        count = 0

        def call(path, token, payload=None):
            nonlocal count
            if path == "services/" + startup.SERVICE_ID and payload is None:
                count += 1
                if count == 2:
                    provider.service["rootDir"] = "unexpected"
            return provider.call(path, token, payload)

        with self.assertRaises(startup.Refused):
            startup.repair("fixture", call)
        self.assertEqual(provider.writes, [])

    def test_bad_readback_or_changed_environment_or_deployment_cannot_qualify(self):
        for mode in ("readback", "environment", "deployment"):
            provider = Provider()

            def call(path, token, payload=None, provider=provider, mode=mode):
                result = provider.call(path, token, payload)
                if payload:
                    if mode == "readback":
                        provider.service["rootDir"] = "unexpected"
                    elif mode == "environment":
                        provider.environment["UNRELATED_SETTING"] = "changed"
                    else:
                        provider.deployment["id"] = "dep-new"
                return result

            with self.assertRaises(startup.Refused):
                startup.repair("fixture", call)

    def test_unauthorized_entrypoint_never_contacts_provider(self):
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(startup, "repair") as repair,
        ):
            with self.assertRaises(startup.Refused):
                startup.main()
            repair.assert_not_called()


if __name__ == "__main__":
    unittest.main()
