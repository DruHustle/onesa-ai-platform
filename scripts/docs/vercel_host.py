"""Prepare the separately scoped public docs project without exposing credentials."""

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser()
parser.add_argument(
    "operation", choices=["prepare", "domain", "inspect", "verify-deployment"]
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
    with urlopen(request, timeout=30) as response:
        return json.load(response)


if args.operation in {"prepare", "inspect", "verify-deployment"}:
    selected = os.environ.get("VERCEL_DOCS_PROJECT_ID") or "onesa-docs"
    try:
        project = api("/v9/projects/" + selected)
    except HTTPError as error:
        if error.code == 404 and args.operation == "inspect":
            print(json.dumps({"project": "onesa-docs", "exists": False}))
            raise SystemExit(0)
        if error.code != 404 or not args.create or args.operation != "prepare":
            raise SystemExit(
                f"Docs project lookup failed with HTTP {error.code}"
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
    except HTTPError as error:
        if error.code != 404:
            raise SystemExit(f"Domain lookup failed with HTTP {error.code}") from None
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
    except HTTPError as error:
        result["dns_readback_http_status"] = error.code
    print(json.dumps(result, indent=2))
    (directory / "domain-readback.json").write_text(json.dumps(result, indent=2) + "\n")
