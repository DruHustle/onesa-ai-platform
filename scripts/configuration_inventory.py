"""AI-only read-only inventory. Never emit provider secrets or arbitrary env values."""

import json
import os
import re
from urllib.parse import urlencode, urlsplit

from inspect_hosting import application_keys, get_json, safe_commit

REPOSITORY = "https://github.com/DruHustle/onesa-ai-platform"
SAFE_HOSTS = (".onesa.eu", ".onrender.com", ".vercel.app")
ENUMS = {
    "ONESA_ENVIRONMENT": {"development", "test", "staging", "production"},
    "ONESA_MODEL_BACKEND": {"mock", "ollama", "vllm"},
    "ONESA_EMBEDDING_BACKEND": {"lexical", "http"},
    "ONESA_MAIL_PROVIDER": {"disabled", "resend"},
    "ONESA_REGISTRATION_MODE": {"open", "invitation"},
    "ONESA_SECURE_COOKIES": {"true", "false"},
}


def identifier(value):
    return (
        value
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,120}", value)
        else None
    )


def public_origin(value):
    try:
        url = urlsplit(value)
        if (
            url.scheme == "https"
            and url.hostname
            and (url.hostname == "onesa.eu" or url.hostname.endswith(SAFE_HOSTS))
            and not url.username
            and not url.password
            and url.port in {None, 443}
            and url.path in {"", "/"}
            and not url.query
            and not url.fragment
        ):
            return value.rstrip("/")
    except (ValueError, TypeError):
        pass
    return None


def values(entries, wrapper=None):
    result = {}
    for entry in entries if isinstance(entries, list) else []:
        entry = entry.get(wrapper, entry) if wrapper else entry
        key = entry.get("key")
        if isinstance(key, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,100}", key):
            result[key] = entry.get("value", "")
    return result


def settings_report(environment):
    report = {
        key: {"status": "configured" if environment.get(key) else "missing"}
        for key in application_keys()
    }
    for key, allowed in ENUMS.items():
        value = environment.get(key)
        if value:
            report[key] = {"status": "configured" if value in allowed else "invalid"}
            if value in allowed:
                report[key]["value"] = value
    origin = environment.get("ONESA_PUBLIC_ORIGIN")
    if origin:
        safe = public_origin(origin)
        report["ONESA_PUBLIC_ORIGIN"] = {
            "status": "configured" if safe and origin == safe else "invalid"
        }
        if safe and origin == safe:
            report["ONESA_PUBLIC_ORIGIN"]["value"] = safe
    for key, minimum in (("ONESA_METRICS_TOKEN", 32), ("ONESA_AUTH_DELIVERY_KEY", 48)):
        value = environment.get(key)
        if value:
            report[key]["status"] = (
                "configured"
                if isinstance(value, str) and len(value) >= minimum
                else "invalid"
            )
    if environment.get("ONESA_DATABASE_URL"):
        # Driver compatibility only; this is not a connection/TLS/schema acceptance.
        report["ONESA_DATABASE_URL"]["driver_scheme_supported"] = str(
            environment["ONESA_DATABASE_URL"]
        ).startswith("postgresql+psycopg://")
    report["interpretation"] = (
        "configured means present or checked syntax only; hosted functionality remains unverified"
    )
    return report


def main():
    if os.environ.get("GITHUB_REPOSITORY") != "DruHustle/onesa-ai-platform":
        raise SystemExit("AI repository scope required")
    render_token = os.environ.get("RENDER_API_KEY", "")
    service_id = identifier(os.environ.get("RENDER_BACKEND_SERVICE_ID", ""))
    if not render_token or not service_id or not service_id.startswith("srv-"):
        raise SystemExit("AI Render access not configured")
    service, status = get_json(
        "https://api.render.com/v1/", "services/" + service_id, render_token
    )
    if (
        status != 200
        or service.get("repo", "").removesuffix(".git").rstrip("/") != REPOSITORY
    ):
        raise SystemExit("AI Render target could not be verified")
    owner = identifier(service.get("ownerId"))
    if not owner:
        raise SystemExit("Render owner could not be verified")
    env, env_status = get_json(
        "https://api.render.com/v1/",
        "services/" + service_id + "/env-vars?limit=100",
        render_token,
    )
    direct = values(env, "envVar")
    groups, group_status = get_json(
        "https://api.render.com/v1/",
        "env-groups?" + urlencode({"ownerId": owner, "limit": 100}),
        render_token,
    )
    linked = []
    group_values = {}
    for entry in groups if isinstance(groups, list) else []:
        group = entry.get("envGroup", entry)
        if not any(
            link.get("id") == service_id for link in group.get("serviceLinks", [])
        ):
            continue
        group_id = identifier(group.get("id"))
        if not group_id:
            continue
        detail, detail_status = get_json(
            "https://api.render.com/v1/", "env-groups/" + group_id, render_token
        )
        group_env = values(detail.get("envVars", []), "envVar")
        linked.append(
            {
                "id": group_id,
                "name": identifier(group.get("name")),
                "details_http": detail_status,
                "environment_id": identifier(group.get("environmentId")),
                "keys": sorted(group_env),
                "portal_named": "portal" in str(group.get("name", "")).lower(),
                "conflicting_service_keys": sorted(
                    key
                    for key, value in group_env.items()
                    if key in direct and direct[key] != value
                ),
            }
        )
        for key, value in group_env.items():
            group_values.setdefault(key, []).append(value)
    effective = {
        key: entries[0]
        for key, entries in group_values.items()
        if len(set(entries)) == 1
    }
    effective.update(direct)
    details = service.get("serviceDetails", {})
    service_origin = public_origin(details.get("url"))
    workers, workers_status = get_json(
        "https://api.render.com/v1/",
        "services?" + urlencode({"ownerId": owner, "limit": 100}),
        render_token,
    )
    ai_workers = []
    for entry in workers if isinstance(workers, list) else []:
        item = entry.get("service", entry)
        if (
            item.get("type") == "background_worker"
            and item.get("repo", "").removesuffix(".git").rstrip("/") == REPOSITORY
        ):
            ai_workers.append(
                {
                    "id": identifier(item.get("id")),
                    "name": identifier(item.get("name")),
                    "environment_id": identifier(item.get("environmentId")),
                }
            )
    result = {
        "read_only": True,
        "source_commit": safe_commit(os.environ.get("GITHUB_SHA")),
        "render": {
            "id": service_id,
            "name": identifier(service.get("name")),
            "owner_id": owner,
            "repository": REPOSITORY,
            "branch": service.get("branch")
            if service.get("branch") in {"main", "staging"}
            else "unrecognized",
            "root_matches": service.get("rootDir") == "onesa-ai-platform-backend",
            "public_backend_origin": service_origin,
            "environment_id": identifier(service.get("environmentId")),
            "service_environment_http": env_status,
            "service_environment_keys": sorted(direct),
            "service_environment_may_be_truncated": isinstance(env, list)
            and len(env) == 100,
            "environment_groups_http": group_status,
            "environment_groups_may_be_truncated": isinstance(groups, list)
            and len(groups) == 100,
            "linked_environment_groups": linked,
            "conflicting_group_keys": sorted(
                key for key, entries in group_values.items() if len(set(entries)) > 1
            ),
            "effective_settings": settings_report(effective),
            "workers_inventory_http": workers_status,
            "workers_inventory_may_be_truncated": isinstance(workers, list)
            and len(workers) == 100,
            "matching_identity_workers": ai_workers,
        },
    }
    token = os.environ.get("VERCEL_TOKEN", "")
    project = identifier(os.environ.get("VERCEL_PROJECT_ID", ""))
    team = identifier(os.environ.get("VERCEL_ORG_ID", ""))
    if token and project and project.startswith("prj_"):
        query = (
            "?" + urlencode({"teamId": team})
            if team and team.startswith("team_")
            else ""
        )
        data, project_status = get_json(
            "https://api.vercel.com/v9/", "projects/" + project + query, token
        )
        domains, domains_status = get_json(
            "https://api.vercel.com/v9/",
            "projects/" + project + "/domains" + query,
            token,
        )
        frontend_env, frontend_env_status = get_json(
            "https://api.vercel.com/v9/", "projects/" + project + "/env" + query, token
        )
        link = data.get("link") or {}
        repository_matches = (
            link.get("org") == "DruHustle" and link.get("repo") == "onesa-ai-platform"
        )
        safe_domains = [
            {
                "origin": public_origin("https://" + domain.get("name", "")),
                "verified": domain.get("verified") is True,
            }
            for domain in domains.get("domains", [])
            if public_origin("https://" + domain.get("name", ""))
        ]
        frontend_keys = [
            {
                "key": item.get("key"),
                "targets": [
                    target
                    for target in item.get("target", [])
                    if target in {"production", "preview", "development"}
                ],
            }
            for item in frontend_env.get("envs", [])
            if isinstance(item.get("key"), str)
            and re.fullmatch(r"[A-Z][A-Z0-9_]{0,100}", item["key"])
        ]
        result["vercel"] = {
            "http": project_status,
            "project_id": project,
            "name": identifier(data.get("name")),
            "team_id": team,
            "repository_matches": repository_matches,
            "git_link_present": bool(link),
            "root_matches": data.get("rootDirectory")
            == "onesa-ai-platform-frontend/apps/chat",
            "domains_http": domains_status,
            "domains": safe_domains,
            "environment_http": frontend_env_status,
            "environment_keys_and_targets": frontend_keys,
            "prepared_production_ONESA_API_URL": service_origin,
            "configuration_applied": False,
        }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
