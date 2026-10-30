"""Fail-closed inspection of existing Engineering Docs Access controls.

Only the external owner provider reader supplies these responses. No policy,
identity, credential, account or deployment is created or changed here.
"""

import json
import re

import oracle_owner as owner

BINDINGS = {
    "CF_ACCESS_TEAM_DOMAIN",
    "CF_ACCESS_AUDIENCES",
    "CF_ACCESS_ENGINEERING_EMAILS",
    "CF_ACCESS_ALLOWED_HOSTS",
}


def inspect(project, apps, provider, organization, expected):
    owner.require(
        project["id"] == expected["project_id"]
        and project["name"] == "onesa-engineering-docs"
        and project["production_branch"] == expected["production_branch"] == "main"
        and not project.get("source")
        and set(apps) == {"canonical", "wildcard"},
        "EXISTING_INDEPENDENT_PROTECTED_DOCS_TARGET_REQUIRED",
    )
    environment_hashes = {}
    configurations = []
    for environment in ["preview", "production"]:
        variables = project["deployment_configs"][environment]["env_vars"]
        owner.require(BINDINGS <= variables.keys(), "ALL_PATH_ACCESS_BINDINGS_REQUIRED")
        raw = {key: variables[key] for key in sorted(BINDINGS)}
        owner.require(
            all(
                set(row) == {"type", "value"} and row["type"] == "plain_text"
                for row in raw.values()
            ),
            "EXISTING_PLAINTEXT_ACCESS_CONFIGURATION_REQUIRED",
        )
        values = {key: row["value"] for key, row in raw.items()}
        owner.require(
            re.fullmatch(
                r"[a-z0-9][a-z0-9-]*\.cloudflareaccess\.com",
                values["CF_ACCESS_TEAM_DOMAIN"],
            ),
            "EXACT_ACCESS_ORGANIZATION_REQUIRED",
        )
        audiences = json.loads(values["CF_ACCESS_AUDIENCES"])
        members = json.loads(values["CF_ACCESS_ENGINEERING_EMAILS"])
        hosts = json.loads(values["CF_ACCESS_ALLOWED_HOSTS"])
        owner.require(
            isinstance(audiences, list)
            and len(audiences) == len(set(audiences)) == 2
            and all(owner.HEX.fullmatch(value) for value in audiences)
            and isinstance(members, list)
            and len(members) == len(set(members)) == 2
            and all(
                isinstance(value, str)
                and re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value)
                for value in members
            )
            and isinstance(hosts, list)
            and set(hosts)
            == {
                "onesa-engineering-docs.pages.dev",
                "*.onesa-engineering-docs.pages.dev",
                "docs.engineering.onesa.eu",
            },
            "EXACT_CURRENT_AUDIENCES_MEMBERS_AND_HOSTS_REQUIRED",
        )
        members = sorted(value.lower() for value in members)
        owner.require(
            len(set(members)) == 2, "TWO_DISTINCT_ENGINEERING_MEMBERS_REQUIRED"
        )
        environment_hashes[environment] = owner.digest(raw)
        configurations.append((audiences, members, hosts))
    owner.require(
        environment_hashes == expected["binding_sha256"]
        and configurations[0] == configurations[1]
        and owner.digest(configurations[0][1]) == expected["membership_sha256"],
        "EXISTING_ACCESS_CONFIGURATION_CHANGED",
    )
    audiences, members, _hosts = configurations[0]
    observed_policies = {}
    seen_audiences = set()
    for role, response in apps.items():
        owner.require(
            set(response) == {"app", "policies"},
            "COMPLETE_ACCESS_APP_RESPONSE_REQUIRED",
        )
        app, policies = response["app"], response["policies"]
        owner.require(
            app["id"] == expected["applications"][role]
            and app["type"] == "self_hosted"
            and app["aud"] in audiences
            and app["allowed_idps"] == [expected["portal_provider_id"]]
            and app["session_duration"] == "8h"
            and isinstance(policies, list)
            and len(policies) == 1,
            "EXISTING_ACCESS_APP_AND_PORTAL_IDENTITY_REQUIRED",
        )
        domains = (
            ["onesa-engineering-docs.pages.dev", "docs.engineering.onesa.eu"]
            if role == "canonical"
            else ["*.onesa-engineering-docs.pages.dev"]
        )
        owner.require(
            app["domain"] == domains[0]
            and app["self_hosted_domains"] == domains
            and app["destinations"]
            == [{"type": "public", "uri": domain} for domain in domains]
            and app["aud"] not in seen_audiences,
            "ORIGIN_CUSTOM_AND_WILDCARD_PREVIEW_COVERAGE_REQUIRED",
        )
        seen_audiences.add(app["aud"])
        policy = policies[0]
        owner.require(
            policy["decision"] == "allow"
            and isinstance(policy["include"], list)
            and len(policy["include"]) == 2
            and all(
                set(rule) == {"email"} and set(rule["email"]) == {"email"}
                for rule in policy["include"]
            )
            and sorted(rule["email"]["email"].lower() for rule in policy["include"])
            == members,
            "EXACT_DIRECT_EXISTING_MEMBERSHIP_REQUIRED_NO_BYPASS",
        )
        # Retain every require/exclude/MFA/destination setting, including absence.
        # A null provider field must never be interpreted as disabling MFA.
        observed_policies[role] = owner.digest(response)
    owner.require(
        seen_audiences == set(audiences)
        and organization["auth_domain"] == values["CF_ACCESS_TEAM_DOMAIN"]
        and owner.digest(organization) == expected["organization_sha256"],
        "EXISTING_ACCESS_ORGANIZATION_AND_TWO_AUDIENCES_REQUIRED",
    )
    config = provider["config"]
    owner.require(
        observed_policies == expected["application_policy_sha256"]
        and provider["id"] == expected["portal_provider_id"]
        and provider["type"] == "oidc"
        and provider["name"] == "Onesa Portal"
        and config["pkce_enabled"] is True
        and config["email_claim_name"] == "email"
        and config["auth_url"]
        == "https://portal.onesa.eu/api/v1/engineering-identity/auth"
        and config["token_url"]
        == "https://portal.onesa.eu/api/v1/engineering-identity/token"
        and config["certs_url"]
        == "https://portal.onesa.eu/api/v1/engineering-identity/jwks"
        and not provider.get("scim_config", {}).get("enabled")
        and owner.digest(provider) == expected["portal_provider_sha256"],
        "DEDICATED_EXISTING_PORTAL_POLICY_OR_IDENTITY_CHANGED",
    )
    return {
        "project_id": project["id"],
        "binding_sha256": environment_hashes,
        "application_policy_sha256": observed_policies,
        "membership_sha256": expected["membership_sha256"],
        "portal_provider_sha256": expected["portal_provider_sha256"],
        "organization_sha256": expected["organization_sha256"],
        "configuration_writes": 0,
        "credential_or_member_values_exported": False,
    }
