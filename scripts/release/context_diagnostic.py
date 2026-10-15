"""Two-call diagnostic of an already deployed staging application; never qualification.

Uses the existing temporary-fixture lifecycle and isolated hosted runner. It cannot
deploy, rebind an origin, change the model, or emit a staging-verification receipt.
Only bounded structural outcomes are retained; generated text stays in memory.
"""

import argparse
import json
import os
import re
import secrets
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from evidence import PRODUCT, REPOSITORY, ROOT, require
from fixture_lifecycle import file_path, validate_owned
from fixtures import parse_fixtures
from hosted import frontend, preflight, provider
from hosted_suite import Session, generation, safe_suite_failure_reason

SERVICE = "srv-db56mju7bikc73950f60"
PROJECT = "prj_8Si7wnmrTvB9PNh0I8DEnOcMUWKJ"
MODEL = "@cf/qwen/qwen3-30b-a3b-fp8"
MODEL_BASE = "https://api.cloudflare.com/client/v4/accounts/ffe41f6678793e8dcc7f4a1c2f5e60d8/ai/v1"
ACTIVE = {
    "created",
    "queued",
    "build_in_progress",
    "pre_deploy_in_progress",
    "update_in_progress",
}
APP_PATHS = [
    "onesa-ai-platform-backend",
    "onesa-ai-platform-frontend/apps/chat",
    "onesa-ai-platform-frontend/packages/api-client",
    "onesa-ai-platform-frontend/package-lock.json",
]


def execution_context():
    require(
        PRODUCT == "onesa-ai-platform"
        and os.environ.get("GITHUB_REPOSITORY") == REPOSITORY
        and os.environ.get("GITHUB_REF") == "refs/heads/staging"
        and os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
        and os.environ.get("GITHUB_ACTOR") == "DruHustle"
        and os.environ.get("GITHUB_TRIGGERING_ACTOR") == "DruHustle"
        and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"
        and os.environ.get("GITHUB_RUN_ATTEMPT") == "1"
        and os.environ.get("STAGING_FIXTURE_MODE") == "temporary"
        and os.environ.get("AI_CONTEXT_DIAGNOSTIC") == "true",
        "Context diagnostics require an owner-dispatched isolated staging run",
    )
    sha = os.environ.get("AI_DIAGNOSTIC_DEPLOYED_COMMIT", "")
    require(re.fullmatch(r"[a-f0-9]{40}", sha), "Exact deployed source required")
    return sha


def source_identity(sha, path):
    return subprocess.check_output(
        ["git", "rev-parse", sha + ":" + path],
        cwd=ROOT,
        text=True,
        stderr=subprocess.DEVNULL,
        timeout=10,
    ).strip()


def verify_target():
    sha = execution_context()
    verified = preflight()
    settings = verified["settings"]
    require(
        os.environ.get("RENDER_SERVICE_ID") == SERVICE
        and os.environ.get("VERCEL_PROJECT_ID") == PROJECT
        and settings.get("ONESA_ENVIRONMENT") == "staging"
        and settings.get("ONESA_MODEL_BACKEND") == "cloudflare"
        and settings.get("ONESA_MODEL_NAME") == MODEL
        and settings.get("ONESA_MODEL_BASE_URL", "").rstrip("/") == MODEL_BASE
        and 1 <= int(settings.get("ONESA_MODEL_MAX_OUTPUT_TOKENS", "1024")) <= 1024,
        "Existing isolated diagnostic target/model required",
    )
    rows = provider(
        "https://api.render.com/v1/services/" + SERVICE + "/deploys?limit=10",
        os.environ["RENDER_API_KEY"],
    )
    require(isinstance(rows, list) and rows, "Deployment readback required")
    deployments = [item["deploy"] for item in rows]
    require(
        deployments[0].get("status") == "live"
        and deployments[0].get("commit", {}).get("id") == sha
        and not any(item.get("status") in ACTIVE for item in deployments),
        "Diagnostic must reuse the exact still-live deployment",
    )
    current = os.environ["GITHUB_SHA"]
    require(
        all(
            source_identity(sha, path) == source_identity(current, path)
            for path in APP_PATHS
        ),
        "Workflow diagnostic source differs from the running application",
    )
    origin = settings.get("ONESA_PUBLIC_ORIGIN", "")
    # Reuse the running origin, never the newly built workflow revision's Preview.
    require(preview_origin_value(origin) == origin, "Exact protected Preview required")
    frontend(origin, sha, "Staging")
    return sha, origin, deployments[0]["id"]


def preview_origin_value(origin):
    # The existing parser reads a file; no shared /tmp/vercel-url binding is changed.
    from urllib.parse import urlsplit

    parsed = urlsplit(origin)
    require(
        parsed.scheme == "https"
        and not parsed.username
        and not parsed.password
        and not parsed.port
        and not parsed.path
        and not parsed.query
        and not parsed.fragment
        and re.fullmatch(
            r"onesa-ai-platform-[a-z0-9]+-druhustles-projects\.vercel\.app",
            parsed.hostname or "",
        ),
        "Exact protected application Preview required",
    )
    return origin


def save(record):
    directory = Path(os.environ["RUNNER_TEMP"], "context-diagnostic")
    directory.mkdir(mode=0o700, exist_ok=True)
    path = directory / "record.json"
    path.write_text(json.dumps(record, indent=2) + "\n")
    path.chmod(0o600)


def probe():
    sha, origin, deployment = verify_target()
    path = file_path()
    require(
        path.is_file() and path.stat().st_mode & 0o077 == 0,
        "Private run-owned fixture file required",
    )
    config = json.loads(path.read_text())
    validate_owned(config)
    config = parse_fixtures(json.dumps(config), PROJECT, PRODUCT)
    clients = [Session(origin), Session(origin)]
    logged = []
    conversation = None
    record = {
        "kind": "staging-context-diagnostic-only",
        "repository": REPOSITORY,
        "workflow_commit": os.environ["GITHUB_SHA"],
        "deployed_commit": sha,
        "render_deployment": deployment,
        "workflow_run_id": int(os.environ["GITHUB_RUN_ID"]),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "maximum_inference_requests": 2,
        "inference_requests_submitted": 0,
        "observations": [],
        "qualification_established": False,
        "deployment_requests": 0,
        "configuration_changes": 0,
        "generated_or_reasoning_text_retained": False,
        "result": "INCOMPLETE",
    }
    save(record)
    try:
        for client, user in zip(clients, config["users"], strict=True):
            client.login(user)
            logged.append(client)
        conversation = clients[0].call(
            "POST",
            "/api/v1/conversations",
            {"title": "Synthetic context diagnostic " + secrets.token_hex(8)},
            expected=201,
        )["id"]
        clients[1].call("GET", "/api/v1/conversations/" + conversation, expected=404)
        code = "RELEASE-" + secrets.token_hex(8)
        for phase, content in [
            (
                "acknowledgement",
                "Remember this synthetic test code: " + code + ". Acknowledge briefly.",
            ),
            (
                "recall",
                "What synthetic test code did I give you? Return only that exact code.",
            ),
        ]:
            record["inference_requests_submitted"] += 1
            save(record)
            text, start = generation(
                clients[0],
                {
                    "conversation_id": conversation,
                    "content": content,
                    "stream": True,
                },
            )
            record["observations"].append(
                {
                    "phase": phase,
                    "visible_characters": len(text),
                    "nonempty": bool(text.strip()),
                    "synthetic_code_present": code.lower() in text.lower(),
                    "real_inference": start["model"]["real_inference"],
                    "backend": start["model"]["backend"],
                }
            )
            if phase == "recall":
                require(
                    code.lower() in text.lower(),
                    "Hosted conversation context was not retained",
                )
            del text
        record["result"] = "DIAGNOSTIC_COMPLETED"
    except Exception as error:
        record["result"] = "DIAGNOSTIC_FAILED"
        record["failure_reason"] = safe_suite_failure_reason(error)
        raise
    finally:
        if conversation and logged:
            try:
                messages = clients[0].call(
                    "GET", "/api/v1/conversations/" + conversation
                )["messages"]
                record["persisted_message_outcomes"] = [
                    {"role": message.get("role"), "status": message.get("status")}
                    for message in messages
                ]
            except Exception:  # noqa: BLE001 -- Fixed structural diagnostic only.
                record["history_read_failed"] = True
        for client in logged:
            try:
                client.call("POST", "/api/v1/auth/logout", {})
            except Exception:  # noqa: BLE001 -- Existing always-cleanup revokes run-owned sessions.
                record["logout_failed"] = True
        save(record)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["verify", "probe"])
    args = parser.parse_args()
    if args.mode == "verify":
        verify_target()
        print("Existing staging application verified; no deployment or origin change")
    else:
        probe()
        print("Two-call context diagnostic complete; no qualification established")


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 -- CLI boundary cannot expose private values.
        raise SystemExit(
            "Context diagnostic blocked; inspect sanitized diagnostic artifact"
        ) from None
