"""Staging scope, credential-disclosure and production-write regression tests."""

import json
import os
import unittest
from unittest.mock import patch

import staging


class StagingTests(unittest.TestCase):
    def test_current_standard_protection_is_accepted_but_missing_or_unknown_modes_are_not(self):
        project = {
            "link": {"org": "DruHustle", "repo": "onesa-ai-platform", "productionBranch": "main"},
            "rootDirectory": "onesa-ai-platform-frontend/apps/chat",
        }
        service = {"serviceDetails": {"url": "https://onesa-ai-platform-backend-staging.onrender.com"}}
        environment = {"envs": [
            {"key": "ONESA_API_URL", "gitBranch": "staging", "target": ["preview"], "value": service["serviceDetails"]["url"]},
            {"key": "NEXT_PUBLIC_ONESA_DOCUMENTATION_URL", "gitBranch": "staging", "target": ["preview"], "value": "https://docs.onesa.eu"},
        ]}
        with patch.dict(os.environ, {"VERCEL_PROJECT_ID": "prj_synthetic", "VERCEL_TOKEN": "synthetic"}):
            for mode in ["prod_deployment_urls_and_all_previews", "all", "all_except_custom_domains", "preview"]:
                with (
                    self.subTest(mode=mode),
                    patch.object(staging, "get_json", side_effect=[({**project, "ssoProtection": {"deploymentType": mode}}, 200), (environment, 200), (environment, 200)]),
                    patch.object(staging, "write_json") as write,
                ):
                    self.assertTrue(staging.configure_preview(service)["readback_verified"])
                    write.assert_not_called()
            for mode in [None, "unknown"]:
                with (
                    self.subTest(mode=mode),
                    patch.object(staging, "get_json", return_value=({**project, "ssoProtection": {"deploymentType": mode}}, 200)) as read,
                    patch.object(staging, "write_json") as write,
                ):
                    with self.assertRaises(SystemExit):
                        staging.configure_preview(service)
                    read.assert_called_once()
                    write.assert_not_called()

    def test_main_cannot_read_or_mutate_provider(self):
        with (
            patch.dict(
                os.environ,
                {
                    "GITHUB_REPOSITORY": "DruHustle/onesa-ai-platform",
                    "GITHUB_REF": "refs/heads/main",
                },
            ),
            patch.object(staging, "get_json") as read,
        ):
            with self.assertRaises(SystemExit):
                staging.target()
            read.assert_not_called()

    def test_foreign_database_is_rejected_without_connecting_or_disclosure(self):
        private_marker = "synthetic-private-password"
        with patch.object(staging, "create_engine") as connect:
            report = staging.database_probe(
                {
                    "ONESA_DATABASE_URL": "postgresql://user:"
                    + private_marker
                    + "@foreign.invalid/neondb?sslmode=require&channel_binding=require"
                }
            )
            connect.assert_not_called()
        self.assertEqual(report["connection"], "FAILED")
        self.assertNotIn(private_marker, json.dumps(report))

    def test_preview_conflict_preserves_existing_variables(self):
        project = {
            "link": {
                "org": "DruHustle",
                "repo": "onesa-ai-platform",
                "productionBranch": "main",
            },
            "rootDirectory": "onesa-ai-platform-frontend/apps/chat",
            "ssoProtection": {"deploymentType": "all_except_custom_domains"},
        }
        env = {
            "envs": [
                {
                    "key": "ONESA_API_URL",
                    "gitBranch": "staging",
                    "target": ["preview"],
                    "value": "https://foreign.invalid",
                }
            ]
        }
        with (
            patch.dict(
                os.environ,
                {"VERCEL_PROJECT_ID": "prj_synthetic", "VERCEL_TOKEN": "synthetic"},
            ),
            patch.object(staging, "get_json", side_effect=[(project, 200), (env, 200)]),
            patch.object(staging, "write_json") as write,
        ):
            with self.assertRaises(SystemExit):
                staging.configure_preview(
                    {
                        "serviceDetails": {
                            "url": "https://onesa-ai-platform-backend-staging.onrender.com"
                        }
                    }
                )
            write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
