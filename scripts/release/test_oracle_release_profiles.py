"""Scope/path regressions; no owner record or deployment is produced here."""

import copy
import unittest
from pathlib import Path

import oracle_release_profiles as p


def policy(components=p.SCOPED):
    return {
        "components": {
            p.REPOSITORY + ":" + name: {
                "qualification_attempt_limit": 1,
                **(
                    {"release_mode": p.PROFILES[name][1]}
                    if components == p.SCOPED
                    else {}
                ),
            }
            for name in components
        }
    }


class ReleaseProfileTests(unittest.TestCase):
    def binding(self, name):
        return {"component": name, "candidate_commit": "a" * 40}

    def test_fixed_profiles_have_independent_modes_artifacts_and_configuration(self):
        scoped = policy()
        artifacts, configurations, plans = set(), set(), set()
        for name, (kind, mode) in p.PROFILES.items():
            binding = self.binding(name)
            self.assertEqual(p.kind(binding), kind)
            self.assertEqual(p.validate_mode(binding, mode, scoped), mode)
            artifacts.add(p.artifact_folder(binding, "/private/artifacts/" + kind))
            configurations.add(
                p.configuration_folder(binding, "/private/configuration/" + kind)
            )
            plans.add(
                p.plan_path(
                    binding,
                    "/etc/onesa/oracle-ai-release.json",
                    "/etc/onesa/oracle-ai-frontend-release.json",
                )
            )
            for wrong in {"foundation", "twins", "cybersecurity"} - {mode}:
                with (
                    self.subTest(name=name, wrong=wrong),
                    self.assertRaises(p.ProfileError),
                ):
                    p.validate_mode(binding, wrong, scoped)
        self.assertEqual(len(artifacts), 6)
        self.assertEqual(len(configurations), 6)
        self.assertEqual(len(plans), 6)

    def test_legacy_two_component_policy_preserves_supported_modes_and_paths(self):
        for name in p.LEGACY:
            binding = self.binding(name)
            for mode in ("foundation", "twins", "cybersecurity"):
                self.assertEqual(p.validate_mode(binding, mode, policy(p.LEGACY)), mode)
            self.assertEqual(
                p.artifact_folder(binding, "/old/root"),
                Path("/old/root/artifacts") / ("a" * 40),
            )
            self.assertEqual(
                p.configuration_folder(binding, "/old/candidates"),
                Path("/old/candidates") / ("a" * 40),
            )
        with self.assertRaises(p.ProfileError):
            p.validate_mode(self.binding("twins-api"), "twins", policy(p.LEGACY))

    def test_partial_foreign_and_expanded_allowance_policies_fail_closed(self):
        for value in [
            None,
            {},
            {"components": {}},
            policy({"api"}),
            {
                "components": {
                    p.REPOSITORY + ":worker": {"qualification_attempt_limit": 1}
                }
            },
        ]:
            with self.subTest(value=value), self.assertRaises(p.ProfileError):
                p.policy_components(value)
        for field, value in [
            ("qualification_attempt_limit", 2),
            ("qualification_attempt_limit", True),
            ("release_mode", "foundation"),
        ]:
            changed = copy.deepcopy(policy())
            changed["components"][p.REPOSITORY + ":twins-api"][field] = value
            with self.assertRaises(p.ProfileError):
                p.policy_components(changed)
        changed = policy()
        changed["components"]["foreign/repository:api"] = {
            "qualification_attempt_limit": 1
        }
        with self.assertRaises(p.ProfileError):
            p.policy_components(changed)

    def test_source_aliases_and_caller_selected_profiles_never_select_owner_paths(self):
        for name in [
            "../api",
            "/etc/secret",
            "api-twins",
            "worker",
            "twins-api/../frontend",
            None,
            True,
        ]:
            with self.subTest(name=name), self.assertRaises(p.ProfileError):
                p.artifact_folder(self.binding(name), "/private/root")
        for source in ["main", "../" + "a" * 40, "A" * 40, None]:
            with self.subTest(source=source), self.assertRaises(p.ProfileError):
                p.configuration_folder(
                    {"component": "twins-api", "candidate_commit": source},
                    "/private/configuration",
                )

    def test_companions_keep_api_and_frontend_in_the_same_feature_scope(self):
        for name in p.SCOPED:
            binding = self.binding(name)
            for target in ["api", "frontend"]:
                other = p.companion(binding, target)
                self.assertEqual(p.kind(self.binding(other)), target)
                self.assertEqual(p.PROFILES[other][1], p.PROFILES[name][1])

    def test_actual_runtime_flags_cannot_hide_another_enabled_feature(self):
        both = {
            "ONESA_DIGITAL_TWINS_ENABLED": "true",
            "ONESA_CYBERSECURITY_ENABLED": "true",
        }
        for mode in ["twins", "cybersecurity"]:
            self.assertEqual(p.enabled_features(both, mode), {"twins", "cybersecurity"})
        self.assertEqual(p.enabled_features({}, "foundation"), set())
        for values, mode in [
            (both, "foundation"),
            ({}, "twins"),
            ({"ONESA_DIGITAL_TWINS_ENABLED": True}, "twins"),
            ({"ONESA_CYBERSECURITY_ENABLED": "TRUE"}, "cybersecurity"),
            ({"ONESA_DIGITAL_TWINS_ENABLED": "false "}, "foundation"),
            ({}, "other"),
        ]:
            with (
                self.subTest(values=values, mode=mode),
                self.assertRaises(p.ProfileError),
            ):
                p.enabled_features(values, mode)


if __name__ == "__main__":
    unittest.main()
