"""Prepare the separately scoped public docs project without exposing credentials."""

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser()
parser.add_argument("operation", choices=["prepare", "domain"])
parser.add_argument("--create", action="store_true")
args = parser.parse_args()
token = os.environ.get("VERCEL_TOKEN", "")
organization = os.environ.get("VERCEL_ORG_ID", "")
if not token or not organization:
    raise SystemExit("Missing VERCEL_TOKEN or VERCEL_ORG_ID")
query = (
    "?" + urlencode({"teamId": organization})
    if organization.startswith("team_")
    else ""
)


def api(path, body=None):
    request = Request(
        "https://api.vercel.com" + path + query,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


if args.operation == "prepare":
    selected = os.environ.get("VERCEL_DOCS_PROJECT_ID") or "onesa-docs"
    try:
        project = api("/v9/projects/" + selected)
    except HTTPError as error:
        if error.code != 404 or not args.create:
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
    if project["id"] == os.environ.get("APPLICATION_VERCEL_PROJECT_ID"):
        raise SystemExit("Docs and application projects must be independent")
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
        record = api(f"/v10/projects/{identifier}/domains", {"name": domain})
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
