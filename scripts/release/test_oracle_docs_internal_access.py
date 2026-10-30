"""Disposable provider responses; never account access or authorization."""

import copy
import unittest

import oracle_docs_internal_access as access
import oracle_owner as owner


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.members = ["owner@example.invalid", "engineer@example.invalid"]
        variables = {
            "CF_ACCESS_TEAM_DOMAIN": {
                "type": "plain_text",
                "value": "synthetic.cloudflareaccess.com",
            },
            "CF_ACCESS_AUDIENCES": {
                "type": "plain_text",
                "value": '["' + "a" * 64 + '","' + "b" * 64 + '"]',
            },
            "CF_ACCESS_ENGINEERING_EMAILS": {
                "type": "plain_text",
                "value": owner.canonical(self.members).decode(),
            },
            "CF_ACCESS_ALLOWED_HOSTS": {
                "type": "plain_text",
                "value": owner.canonical(
                    [
                        "onesa-engineering-docs.pages.dev",
                        "*.onesa-engineering-docs.pages.dev",
                        "docs.engineering.onesa.eu",
                    ]
                ).decode(),
            },
        }
        self.project = {
            "id": "synthetic-existing-project",
            "name": "onesa-engineering-docs",
            "production_branch": "main",
            "deployment_configs": {
                environment: {"env_vars": copy.deepcopy(variables)}
                for environment in ["preview", "production"]
            },
        }
        self.organization = {"auth_domain": "synthetic.cloudflareaccess.com"}
        self.provider = {
            "id": "synthetic-dedicated-portal",
            "type": "oidc",
            "name": "Onesa Portal",
            "config": {
                "pkce_enabled": True,
                "email_claim_name": "email",
                "auth_url": "https://portal.onesa.eu/api/v1/engineering-identity/auth",
                "token_url": "https://portal.onesa.eu/api/v1/engineering-identity/token",
                "certs_url": "https://portal.onesa.eu/api/v1/engineering-identity/jwks",
            },
        }
        self.apps = {}
        for role, audience in [("canonical", "a" * 64), ("wildcard", "b" * 64)]:
            self.apps[role] = {
                "app": {
                    "id": "synthetic-" + role,
                    "type": "self_hosted",
                    "aud": audience,
                    "allowed_idps": [self.provider["id"]],
                    "session_duration": "8h",
                    "domain": "onesa-engineering-docs.pages.dev"
                    if role == "canonical"
                    else "*.onesa-engineering-docs.pages.dev",
                    "self_hosted_domains": [
                        "onesa-engineering-docs.pages.dev",
                        "docs.engineering.onesa.eu",
                    ]
                    if role == "canonical"
                    else ["*.onesa-engineering-docs.pages.dev"],
                    "destinations": [
                        {"type": "public", "uri": domain}
                        for domain in (
                            [
                                "onesa-engineering-docs.pages.dev",
                                "docs.engineering.onesa.eu",
                            ]
                            if role == "canonical"
                            else ["*.onesa-engineering-docs.pages.dev"]
                        )
                    ],
                },
                "policies": [
                    {
                        "decision": "allow",
                        "include": [
                            {"email": {"email": email}} for email in self.members
                        ],
                        "require": [],
                        "exclude": [],
                    }
                ],
            }
        self.expected = {
            "organization_sha256": owner.digest(self.organization),
            "project_id": self.project["id"],
            "production_branch": "main",
            "applications": {role: row["app"]["id"] for role, row in self.apps.items()},
            "portal_provider_id": self.provider["id"],
            "binding_sha256": {
                environment: owner.digest(variables)
                for environment in ["preview", "production"]
            },
            "membership_sha256": owner.digest(sorted(self.members)),
            "application_policy_sha256": {
                role: owner.digest(row) for role, row in self.apps.items()
            },
            "portal_provider_sha256": owner.digest(self.provider),
        }

    def inspect(self):
        return access.inspect(
            self.project, self.apps, self.provider, self.organization, self.expected
        )

    def test_current_two_member_configuration_is_inspected_without_export_or_write(
        self,
    ):
        result = self.inspect()
        self.assertEqual(result["configuration_writes"], 0)
        self.assertFalse(result["credential_or_member_values_exported"])
        self.assertNotIn("example.invalid", str(result))

    def test_wrong_project_branch_or_new_source_integration_refused(self):
        for key, value in [
            ("id", "new-project"),
            ("name", "different-project"),
            ("production_branch", "other"),
            ("source", {"type": "github"}),
        ]:
            saved = copy.deepcopy(self.project)
            self.project[key] = value
            with self.subTest(key=key), self.assertRaises(owner.Rejected):
                self.inspect()
            self.project = saved

    def test_missing_changed_and_cross_environment_bindings_refused(self):
        for environment in ["preview", "production"]:
            for key in access.BINDINGS:
                saved = copy.deepcopy(self.project)
                del self.project["deployment_configs"][environment]["env_vars"][key]
                with (
                    self.subTest(environment=environment, key=key),
                    self.assertRaises(owner.Rejected),
                ):
                    self.inspect()
                self.project = saved
        self.project["deployment_configs"]["preview"]["env_vars"][
            "CF_ACCESS_TEAM_DOMAIN"
        ]["value"] = "different.cloudflareaccess.com"
        with self.assertRaises(owner.Rejected):
            self.inspect()

    def test_bypass_service_auth_domain_membership_and_extra_member_refused(self):
        for policy in [
            {"decision": "bypass", "include": [{"everyone": {}}]},
            {
                "decision": "non_identity",
                "include": [{"service_token": {"token_id": "synthetic"}}],
            },
            {
                "decision": "allow",
                "include": [{"email_domain": {"domain": "example.invalid"}}],
            },
            {
                "decision": "allow",
                "include": [
                    {"email": {"email": email}}
                    for email in self.members + ["unapproved@example.invalid"]
                ],
            },
        ]:
            saved = copy.deepcopy(self.apps)
            self.apps["wildcard"]["policies"] = [policy]
            with self.assertRaises(owner.Rejected):
                self.inspect()
            self.apps = saved

    def test_changed_mfa_exclusion_or_destination_never_inherits_old_configuration_pin(
        self,
    ):
        for target, key, value in [
            ("policy", "require", [{"auth_method": {"auth_method": "pwd"}}]),
            ("policy", "exclude", [{"email": {"email": self.members[0]}}]),
            ("app", "mfa_config", {"mfa_disabled": True}),
            ("app", "self_hosted_domains", ["different.example.invalid"]),
        ]:
            saved = copy.deepcopy(self.apps)
            row = (
                self.apps["canonical"]["policies"][0]
                if target == "policy"
                else self.apps["canonical"]["app"]
            )
            row[key] = value
            with self.subTest(key=key), self.assertRaises(owner.Rejected):
                self.inspect()
            self.apps = saved

    def test_missing_or_additional_identity_provider_and_longer_session_refused(self):
        for key, value in [
            ("allowed_idps", []),
            ("allowed_idps", [self.provider["id"], "another-provider"]),
            ("session_duration", "24h"),
            ("aud", "0" * 64),
        ]:
            saved = copy.deepcopy(self.apps)
            self.apps["canonical"]["app"][key] = value
            with self.subTest(key=key), self.assertRaises(owner.Rejected):
                self.inspect()
            self.apps = saved

    def test_dedicated_portal_pkce_claim_endpoints_and_scim_preserved(self):
        for key, value in [
            ("pkce_enabled", False),
            ("email_claim_name", "nickname"),
            ("auth_url", "https://foreign.example.invalid/auth"),
            ("token_url", "https://foreign.example.invalid/token"),
            ("certs_url", "https://foreign.example.invalid/keys"),
        ]:
            saved = copy.deepcopy(self.provider)
            self.provider["config"][key] = value
            with self.subTest(key=key), self.assertRaises(owner.Rejected):
                self.inspect()
            self.provider = saved
        self.provider["scim_config"] = {"enabled": True}
        with self.assertRaises(owner.Rejected):
            self.inspect()

    def test_uncovered_preview_custom_host_or_wrong_organization_refused(self):
        for role, key, value in [
            ("canonical", "self_hosted_domains", ["onesa-engineering-docs.pages.dev"]),
            ("wildcard", "domain", "onesa-engineering-docs.pages.dev"),
            ("wildcard", "aud", "a" * 64),
        ]:
            saved = copy.deepcopy(self.apps)
            self.apps[role]["app"][key] = value
            with self.subTest(role=role, key=key), self.assertRaises(owner.Rejected):
                self.inspect()
            self.apps = saved
        self.organization["auth_domain"] = "different.cloudflareaccess.com"
        with self.assertRaises(owner.Rejected):
            self.inspect()


if __name__ == "__main__":
    unittest.main()
