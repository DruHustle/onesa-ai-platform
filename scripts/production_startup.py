"""Repair the identified AI startup override only; never release or copy credentials."""

import json
import os
import urllib.error
import urllib.request

from production_defaults import REPOSITORY, SERVICE_ID, NoRedirect, Refused, inventory


def request(path, token, payload=None):
    req = urllib.request.Request(
        "https://api.render.com/v1/" + path,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
        data=json.dumps(payload).encode() if payload is not None else None,
        method="PATCH" if payload is not None else "GET",
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(
            req, timeout=30
        ) as response:
            raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise Refused("Provider response exceeds bound")
            return json.loads(raw)
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise Refused(
            "Startup operation unavailable; inspect saved settings before retrying"
        ) from None


def verified(service):
    details = service.get("serviceDetails", {})
    return (
        service.get("id") == SERVICE_ID
        and service.get("name") == "onesa-ai-platform-backend"
        and service.get("repo", "").removesuffix(".git")
        == "https://github.com/" + REPOSITORY
        and service.get("branch") == "main"
        and service.get("rootDir") == "onesa-ai-platform-backend"
        and service.get("type") == "web_service"
        and service.get("ownerId") == "tea-d5h2r0p4tr6s739ae000"
        and details.get("env") == "docker"
        and details.get("plan") == "free"
        and details.get("region") == "frankfurt"
        and details.get("url") == "https://onesa-ai-platform-backend.onrender.com"
        and (
            service.get("autoDeployTrigger") == "off"
            or service.get("autoDeploy") == "no"
        )
    )


def deployment(entries):
    if not isinstance(entries, list) or len(entries) != 1:
        raise Refused("Existing deployment identity required")
    value = entries[0].get("deploy", {})
    if not value.get("id") or value.get("status") not in {
        "live",
        "update_failed",
        "build_failed",
        "pre_deploy_failed",
        "canceled",
        "deactivated",
    }:
        raise Refused("A stable existing deployment is required")
    return value["id"]


def repair(token, call=request):
    base = "services/" + SERVICE_ID
    before = call(base, token)
    if not verified(before):
        raise Refused(
            "Identified free production service with native auto-deploy off required"
        )
    original_env = inventory(call(base + "/env-vars?limit=100", token))
    original_deploy = deployment(call(base + "/deploys?limit=1", token))
    runtime = before.get("serviceDetails", {}).get("envSpecificDetails", {})
    command = runtime.get("dockerCommand")
    # The existing shell script and Dockerfile CMD are already reviewed startup paths.
    changed = command not in {None, "", "sh /app/start.sh"}
    if changed:
        fresh = call(base, token)
        if fresh != before:
            raise Refused(
                "Service changed concurrently; inspect privately before repair"
            )
        call(
            base,
            token,
            {"serviceDetails": {"envSpecificDetails": {"dockerCommand": ""}}},
        )
    after = call(base, token)
    expected = json.loads(json.dumps(before))
    if changed:
        expected["serviceDetails"]["envSpecificDetails"]["dockerCommand"] = ""
    # Render may update timestamps when saving a setting; all functional fields must match.
    for value in (after, expected):
        value.pop("updatedAt", None)
    if after != expected or not verified(after):
        raise Refused("Startup readback differs; deployment remains blocked")
    if inventory(call(base + "/env-vars?limit=100", token)) != original_env:
        raise Refused("Environment changed; review privately before deployment")
    if deployment(call(base + "/deploys?limit=1", token)) != original_deploy:
        raise Refused("Deployment changed; inspect before continuing")
    return {
        "startup_override_repaired": changed,
        "reviewed_startup_configuration": True,
        "environment_unchanged": True,
        "deployment_identity_unchanged": True,
        "deployment_requested": False,
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
        and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"
        and os.environ.get("RENDER_API_KEY")
    ):
        raise Refused("First-attempt owner dispatch on current reviewed dev required")
    print(json.dumps(repair(os.environ["RENDER_API_KEY"]), indent=2))


if __name__ == "__main__":
    try:
        main()
    except Refused as error:
        raise SystemExit(str(error)) from None
