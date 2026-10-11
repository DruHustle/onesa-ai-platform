"""Save missing reviewed AI production defaults only; never deploy or copy secrets."""

import json
import os
import urllib.error
import urllib.request

SERVICE_ID = "srv-db4j0aom7kps73c0uu3g"
REPOSITORY = "DruHustle/onesa-ai-platform"
DEFAULTS = {
    "ONESA_ENVIRONMENT": "production",
    "ONESA_PUBLIC_ORIGIN": "https://platform.onesa.eu",
    "ONESA_SECURE_COOKIES": "true",
    "ONESA_REGISTRATION_MODE": "invitation",
    "ONESA_ACCESS_OPERATOR_USER_IDS": "[]",
    "ONESA_AUTH_HASH_CONCURRENCY": "1",
    "ONESA_KNOWLEDGE_UPLOAD_CONCURRENCY": "1",
    "ONESA_MODEL_USER_CONCURRENCY": "1",
    "ONESA_MODEL_GLOBAL_CONCURRENCY": "1",
    "ONESA_MODEL_CONTEXT_LENGTH": "8192",
    "ONESA_MODEL_MAX_OUTPUT_TOKENS": "1024",
    "ONESA_GENERATION_TIMEOUT": "60",
    # Preserve the reviewed local model choice, pending a hosted-model decision.
    "ONESA_MODEL_BACKEND": "ollama",
    "ONESA_MODEL_NAME": "qwen3:4b-instruct-2507-q4_K_M",
    "ONESA_EMBEDDING_BACKEND": "http",
    "ONESA_EMBEDDING_NAME": "Qwen/Qwen3-Embedding-0.6B",
    "ONESA_EMBEDDING_REVISION": "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3:qwen-retrieval-v1",
    "ONESA_EMBEDDING_QUERY_INSTRUCTION": (
        "Given a user question, retrieve relevant document passages that answer the question"
    ),
    "ONESA_MAIL_PROVIDER": "disabled",
    "ONESA_MAIL_FROM": "Onesa AI <noreply@mail.onesa.eu>",
    "ONESA_MAIL_REPLY_TO": "info@onesa.eu",
}
PROFILES = (
    ("ONESA_MODEL_BACKEND", "ONESA_MODEL_NAME"),
    ("ONESA_EMBEDDING_BACKEND", "ONESA_EMBEDDING_NAME", "ONESA_EMBEDDING_REVISION",
     "ONESA_EMBEDDING_QUERY_INSTRUCTION"),
)


def compatible_profile(key, environment):
    return all(
        not any(environment.get(name) and environment[name] != DEFAULTS[name] for name in profile)
        for profile in PROFILES if key in profile
    )


class Refused(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(path, token, payload=None):
    req = urllib.request.Request(
        "https://api.render.com/v1/" + path,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        data=json.dumps(payload).encode() if payload is not None else None,
        method="PUT" if payload is not None else "GET",
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=30) as response:
            return json.loads(response.read(1024 * 1024))
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise Refused("Render operation unavailable; inspect saved settings before retrying") from None


def inventory(entries):
    if not isinstance(entries, list) or len(entries) >= 100:
        raise Refused("Complete production environment inventory required")
    result = {}
    for entry in entries:
        item = entry.get("envVar", {}) if isinstance(entry, dict) else {}
        key, value = item.get("key"), item.get("value")
        if not isinstance(key, str) or not isinstance(value, str) or key in result:
            raise Refused("Unexpected environment inventory")
        result[key] = value
    return result


def apply_defaults(token, call=request):
    base = "services/" + SERVICE_ID
    service = call(base, token)
    details = service.get("serviceDetails", {})
    if not (
        service.get("id") == SERVICE_ID
        and service.get("repo", "").removesuffix(".git") == "https://github.com/" + REPOSITORY
        and service.get("name") == "onesa-ai-platform-backend"
        and service.get("branch") == "main"
        and service.get("type") == "web_service"
        and service.get("rootDir") == "onesa-ai-platform-backend"
        and details.get("env") == "docker"
        and details.get("url") == "https://onesa-ai-platform-backend.onrender.com"
        and (service.get("autoDeployTrigger") == "off" or service.get("autoDeploy") == "no")
    ):
        raise Refused("Expected production service with native auto-deploy disabled required")
    owner = service.get("ownerId", "")
    if not isinstance(owner, str) or not owner.startswith("tea-") or not owner[4:].isalnum():
        raise Refused("Verified production owner required")
    groups = call("env-groups?ownerId=" + owner + "&limit=100", token)
    if not isinstance(groups, list) or len(groups) >= 100:
        raise Refused("Complete environment group inventory required")
    for entry in groups:
        group = entry.get("envGroup", entry)
        if any(link.get("id") == SERVICE_ID for link in group.get("serviceLinks", [])):
            raise Refused("Linked environment groups require a separate effective-setting review")
    deployments = call(base + "/deploys?limit=1", token)
    if not isinstance(deployments, list) or len(deployments) != 1:
        raise Refused("Existing deployment identity required")
    before = deployments[0].get("deploy", {})
    if before.get("status") not in {
        "live", "update_failed", "build_failed", "pre_deploy_failed", "canceled", "deactivated"
    } or not before.get("id"):
        raise Refused("Wait for the existing deployment to finish before saving configuration")
    current = inventory(call(base + "/env-vars?limit=100", token))
    added = []
    for key, value in DEFAULTS.items():
        if not current.get(key) and compatible_profile(key, current):
            # Re-read immediately before each write; preserve concurrent operator additions.
            fresh = inventory(call(base + "/env-vars?limit=100", token))
            if fresh.get(key) or not compatible_profile(key, fresh):
                continue
            call(base + "/env-vars/" + key, token, {"value": value})
            added.append(key)
    after = inventory(call(base + "/env-vars?limit=100", token))
    if any(after.get(key) != DEFAULTS[key] for key in added):
        raise Refused("Saved defaults did not match readback; deployment remains blocked")
    if any(after.get(key) != value for key, value in current.items() if value):
        raise Refused("An existing setting changed during this operation; review privately")
    latest = call(base + "/deploys?limit=1", token)
    if not isinstance(latest, list) or not latest or latest[0].get("deploy", {}).get("id") != before["id"]:
        raise Refused("Deployment changed during save; inspect provider status before continuing")
    return {
        "added": added,
        "preserved_existing": sorted(key for key in DEFAULTS if current.get(key)),
        "configured_default_names": sorted(key for key in DEFAULTS if after.get(key)),
        "deferred_profile_keys": sorted(key for profile in PROFILES for key in profile if not after.get(key)),
        "required_external_settings_missing": [key for key in (
            "ONESA_DATABASE_URL", "ONESA_METRICS_TOKEN", "ONESA_MODEL_BASE_URL",
            "ONESA_MODEL_API_KEY", "ONESA_EMBEDDING_BASE_URL", "ONESA_EMBEDDING_API_KEY",
        ) if not after.get(key)],
        "deployment_requested": False,
        "deployment_identity_unchanged": True,
        "production_release_qualified": False,
    }


def main():
    if not (
        os.environ.get("GITHUB_REPOSITORY") == REPOSITORY
        and os.environ.get("GITHUB_REF") == "refs/heads/dev"
        and os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
        and os.environ.get("GITHUB_ACTOR") == "DruHustle"
        and os.environ.get("GITHUB_TRIGGERING_ACTOR") == "DruHustle"
        and os.environ.get("GITHUB_RUN_ATTEMPT") == "1"
        and os.environ.get("RENDER_API_KEY")
    ):
        raise Refused("Explicit first-attempt owner dispatch on reviewed dev required")
    print(json.dumps(apply_defaults(os.environ["RENDER_API_KEY"]), indent=2))


if __name__ == "__main__":
    try:
        main()
    except Refused as error:
        raise SystemExit(str(error)) from None
