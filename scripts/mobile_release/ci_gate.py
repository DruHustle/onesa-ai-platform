"""Read-only proof of successful product CI on the exact release commit."""
import json
import re
import urllib.error
import urllib.request


def require(condition, message):
    if not condition:
        raise ValueError(message)


def required_checks(config):
    names = config.get("requiredChecks")
    release_jobs = {"Native source and release contract", "Sign and publish Google Play internal bundle",
                    "Sign and publish internal TestFlight build"}
    require(isinstance(names, list) and 0 < len(names) <= 100
            and all(isinstance(name, str) and 0 < len(name) <= 160
                    and not re.search(r"[\x00-\x1f\x7f]", name) for name in names),
            "Configure the product's required CI check names")
    require(len(set(names)) == len(names) and not set(names) & release_jobs,
            "Required product checks must be unique and independent of this release workflow")
    return names


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_checks(repository, sha, page, token):
    url = f"https://api.github.com/repos/{repository}/commits/{sha}/check-runs?filter=latest&per_page=100&page={page}"
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token, "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=60) as response:
            payload = response.read(4 * 1024 * 1024 + 1)
            require(len(payload) <= 4 * 1024 * 1024, "GitHub check response exceeds bounds")
            return json.loads(payload)
    except (urllib.error.URLError, TimeoutError):
        raise ValueError("Exact-source product CI could not be verified; no publication is permitted") from None


def verify(config, sha, env, *, call=read_checks):
    names = required_checks(config)
    require(re.fullmatch(r"DruHustle/[a-z0-9-]+", config["repository"])
            and re.fullmatch(r"[0-9a-f]{40}", sha), "Invalid product CI source")
    require(env.get("GITHUB_TOKEN") and re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "")),
            "Read-only GitHub check access and current run ID are required")
    candidates = {name: [] for name in names}
    count = 0
    for page in range(1, 11):
        result = call(config["repository"], sha, page, env["GITHUB_TOKEN"])
        checks, total = result.get("check_runs"), result.get("total_count")
        require(isinstance(checks, list) and isinstance(total, int) and 0 <= total <= 1000,
                "GitHub check list is incomplete or exceeds bounds")
        for check in checks:
            name = check.get("name")
            if name not in candidates:
                continue
            app = check.get("app", {})
            if app.get("id") != 15368 or app.get("slug") != "github-actions":
                continue
            require(check.get("head_sha") == sha, "Product CI is for another source commit")
            link = re.fullmatch(re.escape("https://github.com/" + config["repository"])
                                + r"/actions/runs/([0-9]+)/job/[0-9]+", check.get("details_url", ""))
            require(link is not None, "Required product check has no trusted Actions run identity")
            if link[1] == env["GITHUB_RUN_ID"]:
                continue
            require(isinstance(check.get("id"), int), "Required product check identity missing")
            candidates[name].append(check)
        count += len(checks)
        if count >= total:
            break
        require(checks, "GitHub check pagination was incomplete")
    else:
        raise ValueError("GitHub check pagination exceeds bounds")
    blocked = []
    for name, checks in candidates.items():
        latest = max(checks, key=lambda value: value["id"]) if checks else {}
        if latest.get("status") != "completed" or latest.get("conclusion") != "success":
            blocked.append(name)
    require(not blocked, "Exact-source product CI has not succeeded: " + ", ".join(blocked))
