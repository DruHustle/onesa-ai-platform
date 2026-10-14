"""Prepare the separately scoped public docs project without exposing credentials."""

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

parser = argparse.ArgumentParser()
parser.add_argument(
    "operation",
    choices=[
        "prepare",
        "domain",
        "inspect",
        "verify-deployment",
        "prepare-preview-access",
    ],
)
parser.add_argument("--create", action="store_true")
args = parser.parse_args()
PUBLIC_PROJECT = "prj_Dtm2zO8sQQFqmnospPZgxbCi9Bbr"
PUBLIC_ORGANIZATION = "team_ZCFijEEeYUAKYka9HEyEeyGm"
token = os.environ.get("VERCEL_TOKEN", "")
organization = os.environ.get("VERCEL_ORG_ID", "")
if not token or not organization:
    raise SystemExit("Missing VERCEL_TOKEN or VERCEL_ORG_ID")
if organization != PUBLIC_ORGANIZATION:
    raise SystemExit("Public Docs organization scope mismatch")
query = (
    "?" + urlencode({"teamId": organization})
    if organization.startswith("team_")
    else ""
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


class ProviderHTTPError(SystemExit):
    def __init__(self, status):
        self.status = status
        super().__init__(
            f"Scoped public Docs provider request failed with HTTP {status}"
        )


def api(path, body=None):
    request = Request(
        "https://api.vercel.com"
        + path
        + (query.replace("?", "&", 1) if "?" in path else query),
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=30) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise SystemExit("Scoped public Docs provider response exceeds bound")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise SystemExit(
                "Scoped public Docs provider response has an invalid shape"
            )
        return value
    except HTTPError as error:
        status = error.code
        error.close()
        raise ProviderHTTPError(status) from None
    except (URLError, TimeoutError, ValueError):
        raise SystemExit("Scoped public Docs provider request unavailable") from None


if args.operation in {
    "prepare",
    "inspect",
    "verify-deployment",
    "prepare-preview-access",
}:
    selected = os.environ.get("VERCEL_DOCS_PROJECT_ID") or "onesa-docs"
    if selected not in {PUBLIC_PROJECT, "onesa-docs"}:
        raise SystemExit("Public Docs project scope mismatch before provider lookup")
    try:
        project = api("/v9/projects/" + selected)
    except ProviderHTTPError as error:
        if error.status == 404 and args.operation == "inspect":
            print(json.dumps({"project": "onesa-docs", "exists": False}))
            raise SystemExit(0)
        if error.status != 404 or not args.create or args.operation != "prepare":
            raise SystemExit(
                f"Docs project lookup failed with HTTP {error.status}"
            ) from None
        project = api(
            "/v11/projects",
            {"name": "onesa-docs", "framework": None, "publicSource": False},
        )
    if project.get("name") != "onesa-docs":
        raise SystemExit(
            "Refusing to publish docs into a differently named application project"
        )
    if project.get("id") != PUBLIC_PROJECT:
        raise SystemExit("Public Docs project scope mismatch")
    if project["id"] == os.environ.get("APPLICATION_VERCEL_PROJECT_ID"):
        raise SystemExit("Docs and application projects must be independent")
    if args.operation == "prepare-preview-access":
        # Read only: the owner creates this project-only credential separately.
        bypasses = project.get("protectionBypass")
        if bypasses is None:
            bypasses = {}
        if not isinstance(bypasses, dict):
            raise SystemExit("Public Docs Preview credential map has an invalid shape")
        candidates = [
            secret
            for secret, metadata in bypasses.items()
            if isinstance(metadata, dict)
            and metadata.get("scope") == "automation-bypass"
            and metadata.get("note") == "onesa-docs-preview-qualification-v1"
        ]
        if len(candidates) != 1:
            raise SystemExit(
                "Owner-managed public Docs Preview test credential required"
            )
        secret = candidates[0]
        if (
            not isinstance(secret, str)
            or not 20 <= len(secret) <= 512
            or any(c in secret for c in "\r\n")
        ):
            raise SystemExit("Public Docs Preview test credential has an invalid shape")
        runner = Path(os.environ["RUNNER_TEMP"])
        if (
            not runner.is_dir()
            or runner.is_symlink()
            or any(parent.is_symlink() for parent in runner.parents)
            or runner.stat().st_mode & 0o022
        ):
            raise SystemExit("Trusted private runner directory required")
        directory = runner.resolve()
        path = Path(os.environ["DOCS_PREVIEW_ACCESS_FILE"])
        if (
            path.parent.resolve() != directory
            or path.exists()
            or path.is_symlink()
            or any(parent.is_symlink() for parent in path.parents)
        ):
            raise SystemExit(
                "New private runner-owned Preview credential file required"
            )
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as output:
            json.dump({"projectId": project["id"], "secret": secret}, output)
            output.write("\n")
        print(
            "Existing owner-managed public Docs Preview test credential prepared privately"
        )
        raise SystemExit(0)
    if args.operation == "verify-deployment":
        from urllib.parse import urlsplit

        origin = os.environ.get("DOCS_DEPLOYMENT_URL", "")
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or not parsed.hostname.endswith(".vercel.app")
        ):
            raise SystemExit("Expected the actual HTTPS Vercel deployment URL")
        deployment = api("/v13/deployments/" + parsed.hostname)
        revision = os.environ.get("GITHUB_SHA", "")
        if (
            not revision
            or deployment.get("projectId") != project["id"]
            or deployment.get("readyState") != "READY"
            or deployment.get("meta", {}).get("onesaSourceRevision") != revision
            or "target" not in deployment
        ):
            raise SystemExit(
                "Deployment project, readiness or exact source revision verification failed"
            )
        print(
            json.dumps(
                {
                    "deploymentId": deployment.get("id"),
                    "project": project["name"],
                    "projectId": project["id"],
                    "state": deployment["readyState"],
                    "url": origin,
                    "sourceRevision": revision,
                    "target": deployment.get("target"),
                },
                indent=2,
            )
        )
        raise SystemExit(0)
    if args.operation == "inspect":
        latest = api("/v6/deployments?projectId=" + project["id"] + "&limit=3")
        print(
            json.dumps(
                {
                    "project": project.get("name"),
                    "framework": project.get("framework"),
                    "rootDirectory": project.get("rootDirectory"),
                    "gitConnected": bool(project.get("link")),
                    "deployments": [
                        {
                            "id": d.get("uid"),
                            "url": d.get("url"),
                            "state": d.get("state"),
                            "target": d.get("target"),
                            "sourceRevision": d.get("meta", {}).get(
                                "onesaSourceRevision"
                            )
                            or d.get("meta", {}).get("githubCommitSha"),
                        }
                        for d in latest.get("deployments", [])
                    ],
                },
                indent=2,
            )
        )
        raise SystemExit(0)
    directory = Path(os.environ["DOCS_DEPLOY_DIRECTORY"])
    (directory / ".vercel").mkdir(parents=True, exist_ok=True)
    (directory / ".vercel/project.json").write_text(
        json.dumps({"orgId": organization, "projectId": project["id"]}) + "\n"
    )
    print("Separate public docs project verified:", project["name"])
else:
    directory = Path(os.environ["DOCS_DEPLOY_DIRECTORY"])
    project = json.loads((directory / ".vercel/project.json").read_text())
    identifier = project["projectId"]
    domain = "docs.onesa.eu"
    try:
        record = api(f"/v9/projects/{identifier}/domains/{domain}")
    except ProviderHTTPError as error:
        if error.status != 404:
            raise SystemExit(f"Domain lookup failed with HTTP {error.status}") from None
        raise SystemExit(
            "Existing docs domain assignment is missing; owner approval is required before changing it"
        )
    # Domain verification records are public; never include provider settings or credentials.
    result = {
        "domain": domain,
        "verified": record.get("verified", False),
        "verification": record.get("verification", []),
    }
    try:
        configuration = api(f"/v6/domains/{domain}/config")
        result["recommendedCNAME"] = configuration.get("recommendedCNAME", [])
        result["misconfigured"] = configuration.get("misconfigured")
    except ProviderHTTPError as error:
        result["dns_readback_http_status"] = error.status
    print(json.dumps(result, indent=2))
    (directory / "domain-readback.json").write_text(json.dumps(result, indent=2) + "\n")
