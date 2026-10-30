"""Named GET-only Cloudflare reader in existing external owner custody.

Provider credentials cannot authorize a release. The separately commissioned
issuer, source/build pins, current native evidence and one-use ledger remain
mandatory. No arbitrary URL, redirect, provider mutation or response logging.
"""

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import oracle_owner as owner

PUBLISHER = Path("/etc/onesa/oracle-cloudflare-docs/publisher.json")
ACCESS = Path("/etc/onesa/oracle-cloudflare-docs/access-readonly.json")
MAX_RESPONSE = 2 * 1024**2


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def custody(path, account, *, uid=0, now=None):
    owner.private(path, uid=uid)
    owner.require(path.stat().st_size <= 32768, "PRIVATE_PROVIDER_CUSTODY_BOUND")
    value = json.loads(path.read_bytes())
    now = now or datetime.now(timezone.utc)
    expiry = datetime.fromisoformat(value["expires_at"])
    owner.require(
        set(value)
        == {
            "schema_version",
            "purpose",
            "account_id",
            "token",
            "expires_at",
            "release_authority",
        }
        and type(value["schema_version"]) is int
        and value["schema_version"] == 1
        and value["purpose"]
        == (
            "existing-cloudflare-pages-publisher"
            if path == PUBLISHER
            else "existing-cloudflare-access-readonly"
        )
        and value["account_id"] == account
        and value["release_authority"] is False
        and isinstance(value["token"], str)
        and re.fullmatch(r"[!-~]{20,16384}", value["token"]) is not None
        and expiry.utcoffset() == timedelta()
        and timedelta(minutes=5) <= expiry - now <= timedelta(days=2),
        "CURRENT_PURPOSE_SCOPED_PROVIDER_CUSTODY_REQUIRED",
    )
    return value["token"]


def path_allowed(path, configuration):
    project = "/pages/projects/onesa-engineering-docs"
    apps = configuration["applications"]
    owner.require(
        set(apps) == {"canonical", "wildcard"}
        and all(re.fullmatch(r"[a-f0-9-]{36}", value) for value in apps.values()),
        "EXACT_COMMISSIONED_ACCESS_APPS_REQUIRED",
    )
    return (
        path == project
        or re.fullmatch(
            re.escape(project)
            + r"/deployments\?per_page=25&page=(?:[1-9]|[1-3][0-9]|4[01])",
            path,
        )
        is not None
        or re.fullmatch(re.escape(project) + r"/deployments/[a-f0-9-]{36}", path)
        is not None
        or path in {"/access/organizations", "/access/identity_providers?per_page=100"}
        or path
        in {
            "/access/apps/" + identity + suffix
            for identity in apps.values()
            for suffix in ["", "/policies?per_page=100"]
        }
    )


def get(path, configuration, *, uid=0):
    account = configuration["account_id"]
    owner.require(
        re.fullmatch("[a-f0-9]{32}", account)
        and isinstance(path, str)
        and path_allowed(path, configuration),
        "ONLY_NAMED_EXISTING_PROVIDER_GETS_ALLOWED",
    )
    credential = ACCESS if path.startswith("/access/") else PUBLISHER
    token = custody(credential, account, uid=uid)
    request = urllib.request.Request(
        "https://api.cloudflare.com/client/v4/accounts/" + account + path,
        method="GET",
        headers={
            "Authorization": "Bearer " + token,
            "User-Agent": "OnesaOwnerProtectedDocsReadOnly/1.0",
        },
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(
            request, timeout=30
        ) as response:
            owner.require(response.status == 200, "PROVIDER_GET_NOT_SUCCESSFUL")
            raw = response.read(MAX_RESPONSE + 1)
            owner.require(0 < len(raw) <= MAX_RESPONSE, "PROVIDER_GET_RESPONSE_BOUND")
            value = json.loads(raw)
            owner.require(
                isinstance(value, dict)
                and value.get("success") is True
                and "result" in value,
                "PROVIDER_GET_INCOMPLETE_RESPONSE",
            )
            return value
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        raise owner.Rejected("PROVIDER_READ_FAILED_NO_REDIRECT_OR_MUTATION") from None
    finally:
        del token


def snapshot(configuration, *, uid=0):
    project = get("/pages/projects/onesa-engineering-docs", configuration, uid=uid)[
        "result"
    ]
    apps = {}
    for role, identity in configuration["applications"].items():
        app = get("/access/apps/" + identity, configuration, uid=uid)["result"]
        policies = get(
            "/access/apps/" + identity + "/policies?per_page=100",
            configuration,
            uid=uid,
        )
        count = policies.get("result_info", {}).get(
            "total_count", len(policies["result"])
        )
        owner.require(
            isinstance(policies["result"], list)
            and count == len(policies["result"]) < 100,
            "COMPLETE_ACCESS_POLICIES_REQUIRED",
        )
        apps[role] = {"app": app, "policies": policies["result"]}
    providers = get("/access/identity_providers?per_page=100", configuration, uid=uid)
    count = providers.get("result_info", {}).get(
        "total_count", len(providers["result"])
    )
    owner.require(
        isinstance(providers["result"], list)
        and count == len(providers["result"]) < 100,
        "COMPLETE_IDENTITY_PROVIDER_LIST_REQUIRED",
    )
    matching = [
        row
        for row in providers["result"]
        if row["id"] == configuration["portal_provider_id"]
    ]
    owner.require(len(matching) == 1, "EXISTING_DEDICATED_PORTAL_PROVIDER_REQUIRED")
    organization = get("/access/organizations", configuration, uid=uid)["result"]
    return project, apps, matching[0], organization


def deployments(configuration, *, uid=0):
    """Read the complete bounded project history, never a truncated first page."""
    result, seen = [], set()
    total = None
    for page in range(1, 42):
        value = get(
            "/pages/projects/onesa-engineering-docs/deployments?per_page=25&page="
            + str(page),
            configuration,
            uid=uid,
        )
        rows = value["result"]
        info = value.get("result_info", {})
        owner.require(
            isinstance(rows, list)
            and len(rows) <= 25
            and info.get("page", page) == page
            and info.get("per_page", 25) == 25,
            "BOUNDED_COMPLETE_PRIVATE_DEPLOYMENT_PAGE_REQUIRED",
        )
        if "total_count" in info:
            owner.require(
                type(info["total_count"]) is int
                and 0 <= info["total_count"] <= 1000
                and total in {None, info["total_count"]},
                "PRIVATE_DEPLOYMENT_HISTORY_CHANGED_OR_TOO_LARGE",
            )
            total = info["total_count"]
        for row in rows:
            identity = row["id"]
            owner.require(
                re.fullmatch(r"[a-f0-9-]{36}", identity) and identity not in seen,
                "UNIQUE_PRIVATE_PROVIDER_DEPLOYMENTS_REQUIRED",
            )
            seen.add(identity)
            result.append(row)
        owner.require(
            len(result) <= 1000, "PRIVATE_PROVIDER_HISTORY_EXCEEDS_INSPECTION_BOUND"
        )
        owner.require(
            total is None or len(result) <= total,
            "PRIVATE_PROVIDER_HISTORY_TOTAL_INCONSISTENT",
        )
        if total is not None and len(result) == total:
            return result
        if len(rows) < 25:
            owner.require(
                total is None or total == len(result),
                "PRIVATE_PROVIDER_HISTORY_INCOMPLETE",
            )
            return result
    raise owner.Rejected("PRIVATE_PROVIDER_HISTORY_EXCEEDS_INSPECTION_BOUND")
