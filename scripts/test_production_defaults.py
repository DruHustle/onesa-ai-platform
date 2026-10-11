"""Production setting writes preserve credentials, target identity and release boundaries."""

import copy
import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from urllib.error import HTTPError

import production_defaults as defaults


class RenderFixture:
    def __init__(self):
        self.service = {
            "id": defaults.SERVICE_ID,
            "name": "onesa-ai-platform-backend",
            "repo": "https://github.com/" + defaults.REPOSITORY,
            "branch": "main", "type": "web_service",
            "rootDir": "onesa-ai-platform-backend", "autoDeployTrigger": "off",
            "ownerId": "tea-fixture",
            "serviceDetails": {"env": "docker", "url": "https://onesa-ai-platform-backend.onrender.com"},
        }
        self.environment = {
            "ONESA_ENVIRONMENT": "production",
            "ONESA_PUBLIC_ORIGIN": "https://platform.onesa.eu",
            "ONESA_SECURE_COOKIES": "true",
            "ONESA_DATABASE_URL": "synthetic-private-fixture-must-not-be-emitted",
            "UNRELATED_SETTING": "keep-existing-operator-setting",
        }
        self.groups = []
        self.deployment = {"id": "dep-fixture", "status": "update_failed"}
        self.writes = []

    def call(self, path, token, payload=None):
        base = "services/" + defaults.SERVICE_ID
        if payload is not None:
            self.assert_write(path, base, payload)
            key = path.removeprefix(base + "/env-vars/")
            self.environment[key] = payload["value"]
            self.writes.append(key)
            return {"envVar": {"key": key, "value": payload["value"]}}
        if path == base:
            return copy.deepcopy(self.service)
        if path.startswith("env-groups?"):
            return copy.deepcopy(self.groups)
        if path == base + "/deploys?limit=1":
            return [{"deploy": copy.deepcopy(self.deployment)}]
        if path == base + "/env-vars?limit=100":
            return [{"envVar": {"key": key, "value": value}} for key, value in self.environment.items()]
        raise AssertionError("Unreviewed provider operation")

    @staticmethod
    def assert_write(path, base, payload):
        assert path.startswith(base + "/env-vars/")
        key = path.removeprefix(base + "/env-vars/")
        assert key in defaults.DEFAULTS
        assert payload == {"value": defaults.DEFAULTS[key]}


class ProductionDefaultsTests(unittest.TestCase):
    def test_adds_only_missing_defaults_preserves_credentials_and_does_not_deploy(self):
        provider = RenderFixture()
        original = dict(provider.environment)
        report = defaults.apply_defaults("placeholder", provider.call)
        self.assertEqual(set(report["added"]), set(defaults.DEFAULTS) - original.keys())
        self.assertTrue(all(provider.environment[key] == value for key, value in original.items()))
        self.assertFalse(report["deployment_requested"])
        self.assertFalse(report["production_release_qualified"])
        self.assertIn("ONESA_METRICS_TOKEN", report["required_external_settings_missing"])
        self.assertNotIn(original["ONESA_DATABASE_URL"], json.dumps(report))
        self.assertNotIn("ONESA_DATABASE_URL", provider.writes)
        self.assertNotIn("ONESA_MODEL_BASE_URL", provider.writes)

    def test_existing_custom_model_profile_and_mail_provider_are_preserved(self):
        provider = RenderFixture()
        provider.environment.update({"ONESA_MODEL_BACKEND": "vllm", "ONESA_MODEL_NAME": "reviewed-hosted-model", "ONESA_MAIL_PROVIDER": "resend"})
        defaults.apply_defaults("placeholder", provider.call)
        self.assertEqual(provider.environment["ONESA_MODEL_NAME"], "reviewed-hosted-model")
        self.assertNotIn("ONESA_MODEL_BACKEND", provider.writes)
        self.assertNotIn("ONESA_MAIL_PROVIDER", provider.writes)

    def test_wrong_target_or_enabled_native_deployment_prevents_every_write(self):
        for key, value in (("id", "srv-staging"), ("name", "onesa-ai-platform-backend_staging"), ("branch", "staging"), ("repo", "https://github.com/other/repo"), ("rootDir", "wrong-root"), ("autoDeployTrigger", "commit")):
            with self.subTest(key=key):
                provider = RenderFixture()
                provider.service[key] = value
                with self.assertRaises(defaults.Refused):
                    defaults.apply_defaults("placeholder", provider.call)
                self.assertEqual(provider.writes, [])

    def test_partial_custom_profiles_are_not_completed_with_incompatible_identifiers(self):
        provider = RenderFixture()
        provider.environment.update({"ONESA_MODEL_BACKEND": "vllm", "ONESA_EMBEDDING_BACKEND": "lexical"})
        report = defaults.apply_defaults("placeholder", provider.call)
        self.assertNotIn("ONESA_MODEL_NAME", provider.writes)
        self.assertNotIn("ONESA_EMBEDDING_NAME", provider.writes)
        self.assertIn("ONESA_MODEL_NAME", report["deferred_profile_keys"])

    def test_linked_group_or_active_deployment_requires_independent_review(self):
        for linked in (True, False):
            provider = RenderFixture()
            if linked:
                provider.groups = [{"envGroup": {"serviceLinks": [{"id": defaults.SERVICE_ID}]}}]
            else:
                provider.deployment["status"] = "update_in_progress"
            with self.assertRaises(defaults.Refused):
                defaults.apply_defaults("placeholder", provider.call)
            self.assertEqual(provider.writes, [])

    def test_concurrent_operator_addition_is_not_overwritten(self):
        provider = RenderFixture()
        reads = 0

        def call(path, token, payload=None):
            nonlocal reads
            if "env-vars?" in path:
                reads += 1
                if reads == 2:
                    provider.environment["ONESA_REGISTRATION_MODE"] = "invitation"
            return provider.call(path, token, payload)

        defaults.apply_defaults("placeholder", call)
        self.assertNotIn("ONESA_REGISTRATION_MODE", provider.writes)

    def test_unexpected_readback_or_deployment_change_cannot_report_success(self):
        for mode in ("setting", "deployment"):
            provider = RenderFixture()

            def call(path, token, payload=None):
                result = provider.call(path, token, payload)
                if payload:
                    if mode == "setting":
                        provider.environment["UNRELATED_SETTING"] = "concurrent-change"
                    else:
                        provider.deployment["id"] = "dep-new"
                return result

            with self.subTest(mode=mode), self.assertRaises(defaults.Refused):
                defaults.apply_defaults("placeholder", call)

    def test_http_error_and_redirect_never_expose_response_or_send_credentials_elsewhere(self):
        marker = "synthetic-private-fixture-must-not-be-emitted"
        error = HTTPError("https://api.render.com", 403, marker, {}, io.BytesIO(marker.encode()))
        with patch("production_defaults.urllib.request.build_opener") as opener:
            opener.return_value.open.side_effect = error
            with self.assertRaises(defaults.Refused) as failure:
                defaults.request("services/fixture", "placeholder")
            self.assertNotIn(marker, str(failure.exception))
        self.assertIsNone(defaults.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.invalid"))

    def test_incomplete_inventory_is_rejected_and_owner_dispatch_is_required(self):
        for inventory in ({}, [{"envVar": {"key": "X"}}], [{"envVar": {"key": "X", "value": ""}}] * 100):
            with self.assertRaises(defaults.Refused):
                defaults.inventory(inventory)
        with patch.dict(os.environ, {"GITHUB_REF": "refs/heads/staging"}), patch.object(defaults, "apply_defaults") as operation, redirect_stdout(io.StringIO()):
            with self.assertRaises(defaults.Refused):
                defaults.main()
            operation.assert_not_called()


if __name__ == "__main__":
    unittest.main()
