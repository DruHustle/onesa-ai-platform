"""Credential-free private-Free release handoff; never a Git push restriction.

Run the external verifier from an owner-reviewed, immutable copy on a trusted machine.
Repository writers can change this file and Actions; withholding production credentials
outside GitHub is the security boundary. No caller-supplied PASS document is accepted.
"""

import argparse
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import PurePosixPath

import evidence as e

WORKFLOW = "free-authorization.yml"
QUALIFICATION = "free-qualification.yml"
DELIVERY_SCOPES = {"full", "docs-public", "docs-internal"}
RETAINED_APPLICATION_COMMIT = "9b986aa4b0fcee0cb3789a2fc91eba260785dffe"
PUBLIC_DOCS_PROJECT = "prj_Dtm2zO8sQQFqmnospPZgxbCi9Bbr"


def docs_acceptance_schema(acceptance):
    """Require per-view evidence, rather than counts of unstructured PASS placeholders."""
    accessibility = acceptance.get("accessibility", [])
    e.require(
        isinstance(accessibility, list) and len(accessibility) >= 124,
        "Complete Docs accessibility views required",
    )
    coordinates = set()
    routes = set()
    for view in accessibility:
        e.require(
            isinstance(view, dict)
            and isinstance(view.get("route"), str)
            and view["route"].startswith("/")
            and "?" not in view["route"]
            and "#" not in view["route"]
            and view.get("mode") in {"light", "dark"}
            and view.get("width") in {320, 1440}
            and isinstance(view.get("violations"), list),
            "Structured Docs accessibility view required",
        )
        coordinate = (view["route"], view["mode"], view["width"])
        e.require(coordinate not in coordinates, "Duplicate Docs accessibility view")
        coordinates.add(coordinate)
        routes.add(view["route"])
        for violation in view["violations"]:
            e.require(
                isinstance(violation, dict)
                and isinstance(violation.get("id"), str)
                and violation.get("impact") in {None, "minor", "moderate"}
                and isinstance(violation.get("nodes"), list),
                "Blocking or malformed Docs accessibility violation",
            )
    e.require(
        coordinates
        == {
            (route, mode, width)
            for route in routes
            for mode in ["light", "dark"]
            for width in [320, 1440]
        },
        "Both system modes and widths required for every public Docs route",
    )
    widths = acceptance.get("widths", [])
    expected = {
        (route, "dark", width)
        for route in ["/", "/architecture", "/downloads", "/api-explorer"]
        for width in [320, 390, 768, 1024, 1440]
    }
    actual = []
    e.require(isinstance(widths, list), "Docs width evidence required")
    for view in widths:
        e.require(
            isinstance(view, dict) and view.get("overflow") is False,
            "Malformed or overflowing Docs width view",
        )
        actual.append((view.get("route"), view.get("mode"), view.get("width")))
    e.require(
        len(actual) == len(set(actual)) and set(actual) == expected,
        "Exact Docs width matrix required",
    )
    navigation = acceptance.get("navigation", [])
    registry = json.loads(
        (
            e.ROOT
            / "onesa-ai-platform-frontend/packages/onesa-design/onesa-applications.json"
        ).read_text()
    )
    expected_links = [
        {"label": app["label"] + " ↗", "href": app["href"].rstrip("/")}
        for app in registry["applications"]
    ]
    e.require(
        isinstance(navigation, list)
        and len(navigation) == 2
        and all(
            isinstance(view, dict) and view.get("links") == expected_links
            for view in navigation
        )
        and {view.get("view") for view in navigation} == {"desktop", "mobile"},
        "Exact four-product Docs navigation in both views required",
    )
    icons = acceptance.get("icons", [])
    manifest = json.loads(
        (
            e.ROOT
            / "onesa-ai-platform-frontend/apps/docs/static/brand/icons/v1/sources.json"
        ).read_text()
    )
    expected_icons = {}
    for file in manifest["products"][0]["files"]:
        if file["name"] in {"onesa-docs.svg", "onesa-docs.ico", "onesa-docs-180.png"}:
            route = (
                "/favicon.ico"
                if file["name"].endswith(".ico")
                else "/brand/icons/v1/" + file["name"]
            )
            expected_icons[route] = file
    e.require(
        isinstance(icons, list) and len(icons) == 3,
        "Docs identity icon evidence required",
    )
    paths = []
    for icon in icons:
        e.require(
            isinstance(icon, dict) and icon.get("path") in expected_icons,
            "Structured Docs identity icon required",
        )
        expected_icon = expected_icons[icon["path"]]
        mimes = (
            {"image/x-icon", "image/vnd.microsoft.icon"}
            if icon["path"] == "/favicon.ico"
            else {expected_icon["mime"]}
        )
        e.require(
            icon.get("status") == 200
            and icon.get("sha256") == expected_icon["sha256"]
            and icon.get("mime") in mimes,
            "Actual Docs icon bytes/status/MIME required",
        )
        paths.append(icon["path"])
    e.require(len(set(paths)) == 3, "Duplicate Docs identity icon")


def public_docs_proof(proof, sha):
    """Check provider identity and both context variants independently of the producer."""
    from urllib.parse import urlsplit

    e.require(isinstance(proof, dict), "Structured public Docs proof required")
    preview = proof.get("preview", {})
    e.require(isinstance(preview, dict), "Structured Docs Preview identity required")
    origin = urlsplit(preview.get("url", ""))
    e.require(
        origin.scheme == "https"
        and origin.hostname
        and origin.hostname.endswith(".vercel.app")
        and not origin.username
        and not origin.password
        and not origin.port
        and not origin.query
        and not origin.fragment
        and origin.path in {"", "/"}
        and preview.get("project") == "onesa-docs"
        and preview.get("projectId") == PUBLIC_DOCS_PROJECT
        and isinstance(preview.get("deploymentId"), str)
        and re.fullmatch(r"dpl_[A-Za-z0-9]+", preview["deploymentId"])
        and preview.get("state") == "READY"
        and preview.get("sourceRevision") == sha
        and "target" in preview
        and preview["target"] in {None, "preview"},
        "Actual classified public Docs Preview identity required",
    )
    for key, environment in [
        ("hosted_acceptance", "staging"),
        ("production_acceptance", "production"),
    ]:
        acceptance = proof.get(key, {})
        e.require(isinstance(acceptance, dict), "Structured Docs acceptance required")
        docs_acceptance_schema(acceptance)
        e.require(
            acceptance.get("result") == "PASS"
            and acceptance.get("environment_context") == environment
            and acceptance.get("provenance")
            == {"revision": sha, "classification": "public"}
            and len(acceptance.get("navigation", [])) == 2
            and len(acceptance.get("icons", [])) == 3
            and len(acceptance.get("accessibility", [])) >= 124
            and len(acceptance.get("widths", [])) >= 20
            and acceptance.get("links", 0) > 0
            and acceptance.get("diagrams", 0) > 0
            and acceptance.get("pdfs", 0) > 0,
            "Complete Docs context and classified acceptance required",
        )
    e.require(
        proof["hosted_acceptance"].get("origin") == origin.geturl().rstrip("/")
        and proof.get("build_environment") == "production",
        "Actual hosted origin and production variant required",
    )


def public_docs_artifact(github, run, proof, name="onesa-public-docs-production"):
    pages = github.api(
        f"repos/{e.REPOSITORY}/actions/runs/{run['id']}/artifacts?per_page=100",
        pages=True,
    )
    matches = [
        item for page in pages for item in page["artifacts"] if item["name"] == name
    ]
    e.require(len(matches) == 1, "One public Docs artifact required")
    metadata = github.api(f"repos/{e.REPOSITORY}/actions/artifacts/{matches[0]['id']}")
    source = metadata.get("workflow_run", {})
    e.require(
        metadata.get("expired") is False
        and metadata.get("size_in_bytes", 10**9) <= 128 * 1024 * 1024
        and source.get("id") == run["id"]
        and source.get("head_sha") == run["head_sha"]
        and source.get("head_repository_id") == run["repository"]["id"]
        and metadata.get("digest") == "sha256:" + proof["artifact_sha256"],
        "Public Docs artifact origin or digest mismatch",
    )
    archive = github.api(
        f"repos/{e.REPOSITORY}/actions/artifacts/{metadata['id']}/zip", binary=True
    )
    e.require(len(archive) <= 128 * 1024 * 1024, "Public Docs archive exceeds bounds")
    e.require(
        hashlib.sha256(archive).hexdigest() == proof["artifact_sha256"],
        "Public Docs archive altered",
    )
    digest = hashlib.sha256()
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        entries = bundle.infolist()
        canonical_names = []
        for item in entries:
            path = PurePosixPath(item.filename)
            mode = stat.S_IFMT(item.external_attr >> 16)
            canonical = str(path) + ("/" if item.is_dir() else "")
            e.require(
                not path.is_absolute()
                and ".." not in path.parts
                and canonical == item.filename
                and str(path) != "."
                and "\\" not in item.filename
                and len(item.filename) <= 1024
                and mode in {0, stat.S_IFREG, stat.S_IFDIR}
                and (mode != stat.S_IFDIR or item.is_dir()),
                "Unsafe public Docs archive entry",
            )
            canonical_names.append(str(path))
        e.require(
            len(canonical_names) == len(set(canonical_names)),
            "Duplicate public Docs archive paths",
        )
        files = [item for item in entries if not item.is_dir()]
        e.require(
            len(files) <= 20000
            and sum(item.file_size for item in files) <= 128 * 1024 * 1024,
            "Public Docs archive exceeds bounds",
        )
        names = [item.filename for item in files]
        e.require(len(names) == len(set(names)), "Duplicate public Docs archive paths")
        for item in sorted(files, key=lambda entry: entry.filename):
            path = PurePosixPath(item.filename)
            e.require(
                not path.is_absolute()
                and ".." not in path.parts
                and str(path) == item.filename
                and str(path) != "."
                and "\\" not in item.filename
                and len(item.filename) <= 1024
                and not stat.S_ISLNK(item.external_attr >> 16),
                "Unsafe public Docs archive entry",
            )
            digest.update(
                item.filename.encode()
                + b"\0"
                + hashlib.sha256(bundle.read(item)).digest()
            )
        e.require(
            digest.hexdigest() == proof["build_sha256"],
            "Public Docs build/artifact mismatch",
        )
    return {
        "id": metadata["id"],
        "digest": metadata["digest"],
        "run_id": run["id"],
        "name": name,
    }


def docs_qualification(github, sha, staging_run, delivery_scope):
    """A static Docs handoff grants no application/API deployment authority."""
    e.require(e.PRODUCT == "onesa-ai-platform", "Docs scope is Platform-only")
    run = github.run(staging_run)
    e.trusted_run(
        run,
        "docs-hosting.yml",
        sha,
        {"staging", "main"},
        event="workflow_dispatch",
    )
    record, origin = github.artifact(run, "documentation-qualification")
    e.require(isinstance(record, dict), "Structured Docs qualification required")
    classification = delivery_scope.removeprefix("docs-")
    e.require(
        record.get("schema_version") == 1
        and record.get("repository") == e.REPOSITORY
        and record.get("candidate_commit") == sha
        and record.get("workflow_run_id") == run["id"]
        and record.get("source_sha256") == e.source_hash()
        and record.get("target") == "preview"
        and record.get("production_deployment_requested") is False
        and record.get("application_deployment_authorized") is False
        and record.get("backend_deployment_authorized") is False
        and e.fresh(record.get("verified_at", ""), datetime.now(timezone.utc)),
        "Docs preview source/origin/freshness mismatch",
    )
    scopes = record.get("scopes", {})
    e.require(isinstance(scopes, dict), "Structured classified Docs scopes required")
    proof = scopes.get(classification, {})
    e.require(isinstance(proof, dict), "Structured classified Docs proof required")
    checks = proof.get("checks", {})
    required = {
        "classified_build",
        "dependency_security",
        "public_private_boundary",
        "system_appearance_and_accessibility",
        "diagrams_pdfs_navigation",
        "hosted_preview_identity",
        "hosted_preview_acceptance",
    }
    e.require(
        proof.get("classification") == classification
        and proof.get("status") == "PASS"
        and isinstance(checks, dict)
        and required <= checks.keys()
        and all(value == "PASS" for value in checks.values())
        and re.fullmatch(r"[a-f0-9]{64}", proof.get("build_sha256", ""))
        and re.fullmatch(r"[a-f0-9]{64}", proof.get("artifact_sha256", "")),
        "Complete classified hosted Docs proof required",
    )
    if classification == "internal":
        e.require(
            proof.get("access", {}).get("all_paths_protected") is True
            and proof["access"].get("approved_engineering_identity") is True
            and proof["access"].get("mfa_required") is True
            and proof["access"].get("source_commit") == sha,
            "Protected Docs needs actual source-bound Access proof",
        )
        published_artifact = None
    else:
        public_docs_proof(proof, sha)
        e.require(
            isinstance(proof.get("preview_artifact"), dict),
            "Preview artifact proof required",
        )
        preview_artifact = public_docs_artifact(
            github, run, proof["preview_artifact"], "onesa-public-docs-staging"
        )
        published_artifact = public_docs_artifact(github, run, proof)
    return {
        "record": record,
        "artifact": origin,
        "public_site_artifact": published_artifact,
        "preview_site_artifact": preview_artifact
        if classification == "public"
        else None,
        "classification": classification,
        "scope": delivery_scope,
        "application_deployment_authorized": False,
        "backend_deployment_authorized": False,
        "retained_application_commit": RETAINED_APPLICATION_COMMIT,
        "retained_backend_commit": RETAINED_APPLICATION_COMMIT,
        "provider_retention_and_no_auto_production": "REQUIRED_EXTERNAL_READBACK",
    }


def current_main(github, sha):
    e.require(re.fullmatch(r"[a-f0-9]{40}", sha) is not None, "Exact commit required")
    branch = github.api(f"repos/{e.REPOSITORY}/branches/main")
    e.require(branch["commit"]["sha"] == sha, "Candidate is not current main")
    pages = github.api(
        f"repos/{e.REPOSITORY}/commits/{sha}/pulls?per_page=100", pages=True
    )
    details = [
        github.api(f"repos/{e.REPOSITORY}/pulls/{pr['number']}")
        for page in pages
        for pr in page
    ]
    matches = [
        pr
        for pr in details
        if pr.get("merged_at")
        and pr.get("merge_commit_sha") == sha
        and pr["base"]["ref"] == "main"
        and pr["base"]["repo"]["full_name"] == e.REPOSITORY
        and pr.get("merged_by", {}).get("login") == e.OWNER
        and pr["head"]["ref"] != "main"
    ]
    e.require(
        matches,
        "Main candidate needs an owner-merged feature PR; a direct push is deploy-ineligible",
    )
    return matches[0]["html_url"]


def qualification(github, sha, run, staging_run, delivery_scope="full"):
    e.require(delivery_scope in DELIVERY_SCOPES, "Unsupported delivery scope")
    e.require(
        run["event"] in {"workflow_dispatch", "workflow_run"},
        "Untrusted qualification event",
    )
    e.trusted_run(
        run, QUALIFICATION, sha, {"main"}, event=run["event"], completed=False
    )
    e.require(
        run["actor"]["login"] == e.OWNER
        and run["triggering_actor"]["login"] == e.OWNER,
        "Qualification requires owner provenance",
    )
    pr = current_main(github, sha)
    code, references = e.checked_ci(github, sha)
    e.require(
        code == "PASS",
        "Essential exact-commit CI failed or is incomplete: authorized deployment blocked",
    )
    # Do not permit staging-branch CI to substitute for main CI.
    for reference in references:
        e.require(
            github.run(reference["run_id"])["head_branch"] == "main",
            "Main CI is required",
        )
    builds = e.artifacts_for_ci(github, references)
    if delivery_scope != "full":
        docs = docs_qualification(github, sha, staging_run, delivery_scope)
        return {
            "schema_version": 1,
            "repository": e.REPOSITORY,
            "candidate_commit": sha,
            "source_sha256": e.source_hash(),
            "target_environment": "Production",
            "pull_request": pr,
            "ci": references,
            "builds": builds,
            "staging": docs,
            "delivery_scope": delivery_scope,
            "verified_at": run["created_at"],
            "workflow_run_id": run["id"],
            "status": "AWAITING_OWNER_AUTHORIZATION",
            "CODE_VERIFIED": "PASS",
            "STAGING_VERIFIED": "PASS",
            "OPERATIONS_VERIFIED": "BLOCKED",
            "CONTENT_LEGAL_APPROVED": "BLOCKED",
            "security_status": "PASS",
            "approval_provenance": None,
            "scope": delivery_scope,
            "physical_hardware_authorized": False,
            "application_deployment_authorized": False,
            "backend_deployment_authorized": False,
        }
    stage_run = github.run(staging_run)
    e.trusted_staging_run(github, stage_run, sha)
    stage, origin = github.artifact(stage_run, "staging-verification")
    fingerprint = e.source_hash()
    e.require(
        e.verify_stage(stage, sha, fingerprint, builds) == "PASS",
        "Staging qualification missing",
    )
    return {
        "schema_version": 1,
        "repository": e.REPOSITORY,
        "candidate_commit": sha,
        "source_sha256": fingerprint,
        "target_environment": "Production",
        "pull_request": pr,
        "ci": references,
        "builds": builds,
        "staging": {"record": stage, "artifact": origin},
        "verified_at": run["created_at"],
        "workflow_run_id": run["id"],
        "status": "AWAITING_OWNER_AUTHORIZATION",
        "CODE_VERIFIED": "PASS",
        "STAGING_VERIFIED": "PASS",
        "OPERATIONS_VERIFIED": "BLOCKED",
        "CONTENT_LEGAL_APPROVED": "BLOCKED",
        "operations_evidence": {
            "scope": "technical staging readiness only",
            "checks": stage["checks"],
            "missing": [
                "verified alert delivery",
                "off-host restore and rollback approval",
                "operating limits review",
            ],
        },
        "security_status": "PASS",
        "approval_provenance": None,
        "scope": "cloud-software-only",
        "physical_hardware_authorized": False,
    }


def live_qualification(github, sha, identifier, delivery_scope="full"):
    run = github.run(identifier)
    e.trusted_run(run, QUALIFICATION, sha, {"main"}, event=run["event"])
    record, origin = github.artifact(run, "free-release-qualification")
    e.require(
        record.get("workflow_run_id") == run["id"], "Qualification origin mismatch"
    )
    e.require(
        e.fresh(record["verified_at"], datetime.now(timezone.utc)),
        "Qualification expired",
    )
    e.require(
        record.get("delivery_scope", "full") == delivery_scope,
        "Qualification delivery scope mismatch",
    )
    refreshed = qualification(
        github, sha, run, record["staging"]["artifact"]["run_id"], delivery_scope
    )
    e.require(
        refreshed == record, "Qualification changed: fresh CI/staging review required"
    )
    return record, origin


def owner_issue(github, number, sha, fingerprint):
    e.require(str(number).isdigit(), "Owner review issue number required")
    issue = github.api(f"repos/{e.REPOSITORY}/issues/{number}")
    e.require(
        issue["state"] == "open" and issue["user"]["login"] == e.OWNER,
        "An open owner-authored review record is required",
    )
    body = issue.get("body") or ""
    required = (
        sha,
        fingerprint,
        "OPERATIONS_APPROVED",
        "CONTENT_LEGAL_APPROVED",
        "EXTERNAL_PRODUCTION_CONTROLS_VERIFIED",
    )
    e.require(
        all(text in body for text in required),
        "Owner record must bind SHA, evidence digest and explicit reviews",
    )
    return {
        "url": issue["html_url"],
        "number": int(number),
        "body_sha256": e.digest(body),
    }


def authorize(
    github,
    sha,
    run,
    qualification_run,
    fingerprint,
    review_issue,
    decision,
    delivery_scope="full",
):
    e.require(delivery_scope in DELIVERY_SCOPES, "Unsupported delivery scope")
    e.trusted_run(run, WORKFLOW, sha, {"main"}, completed=False)
    current_main(github, sha)
    e.require(decision in {"approve", "revoke"}, "Explicit decision required")
    record = {
        "repository": e.REPOSITORY,
        "candidate_commit": sha,
        "workflow_run_id": run["id"],
        "approved_at": run["created_at"],
        "approver": e.OWNER,
        "decision": decision,
        "target_environment": "Production",
        "physical_hardware_authorized": False,
    }
    if delivery_scope != "full":
        record.update(
            delivery_scope=delivery_scope,
            application_deployment_authorized=False,
            backend_deployment_authorized=False,
        )
    if decision == "approve":
        qualified, origin = live_qualification(
            github, sha, qualification_run, delivery_scope
        )
        e.require(
            e.digest(qualified) == fingerprint,
            "Owner must review the exact derived evidence digest",
        )
        record.update(
            qualification=origin,
            evidence_sha256=fingerprint,
            source_sha256=qualified["source_sha256"],
            owner_review=(
                owner_issue(github, review_issue, sha, fingerprint)
                if review_issue
                else {
                    "source": "owner-workflow-dispatch",
                    "workflow_run_id": run["id"],
                    "candidate_commit": sha,
                    "evidence_sha256": fingerprint,
                    "approver": e.OWNER,
                }
            ),
        )
    return record


def verify(github, sha, identifier, delivery_scope="full"):
    e.require(delivery_scope in DELIVERY_SCOPES, "Unsupported delivery scope")
    # Latest revocation/failure/pending dispatch invalidates any older approval.
    runs = github.runs(WORKFLOW, sha)
    e.require(
        runs and str(runs[0]["id"]) == str(identifier),
        "Only the latest owner authorization is usable",
    )
    run = github.run(identifier)
    e.trusted_run(run, WORKFLOW, sha, {"main"})
    approval, origin = github.artifact(run, "free-production-authorization")
    e.require(
        approval.get("delivery_scope", "full") == delivery_scope,
        "Authorization delivery scope mismatch",
    )
    e.require(approval.get("decision") == "approve", "Production authorization revoked")
    e.require(
        e.fresh(approval["approved_at"], datetime.now(timezone.utc)),
        "Authorization expired",
    )
    refreshed = authorize(
        github,
        sha,
        run,
        approval["qualification"]["run_id"],
        approval["evidence_sha256"],
        approval["owner_review"].get("number"),
        "approve",
        delivery_scope,
    )
    e.require(approval == refreshed, "Approval or owner review changed")
    return {
        "status": "AUTHORIZED_EXTERNAL_HANDOFF",
        "approval": approval,
        "artifact": origin,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "deployment_triggered": False,
        "git_push_prevented": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["qualify", "authorize", "verify"])
    parser.add_argument("--sha", default=os.getenv("GITHUB_SHA"))
    parser.add_argument("--staging-run", default=os.getenv("STAGING_RUN"))
    parser.add_argument("--qualification-run", default=os.getenv("QUALIFICATION_RUN"))
    parser.add_argument("--evidence-digest", default=os.getenv("EVIDENCE_DIGEST"))
    parser.add_argument("--review-issue", default=os.getenv("REVIEW_ISSUE"))
    parser.add_argument("--decision", default=os.getenv("REVIEW_DECISION", "revoke"))
    parser.add_argument("--authorization-run")
    parser.add_argument(
        "--delivery-scope", choices=sorted(DELIVERY_SCOPES), default="full"
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    github = e.GitHub()
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=e.ROOT, text=True
    ).strip()
    e.require(sha == args.sha, "Checkout differs from candidate")
    e.require(
        not subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=e.ROOT
        ),
        "Clean reviewed checkout required",
    )
    if args.mode == "verify":
        e.require(
            not os.getenv("GITHUB_ACTIONS"),
            "Private production handoff must run outside repository Actions",
        )
        actor = json.loads(subprocess.check_output(["gh", "api", "user"], text=True))[
            "login"
        ]
        e.require(
            actor == e.OWNER, "External production verifier requires owner identity"
        )
        record = verify(github, sha, args.authorization_run, args.delivery_scope)
    else:
        e.require(
            os.getenv("GITHUB_REF") == "refs/heads/main",
            "Owner dispatch on main required",
        )
        run = github.run(os.environ["GITHUB_RUN_ID"])
        record = (
            qualification(github, sha, run, args.staging_run, args.delivery_scope)
            if args.mode == "qualify"
            else authorize(
                github,
                sha,
                run,
                args.qualification_run,
                args.evidence_digest,
                args.review_issue,
                args.decision,
                args.delivery_scope,
            )
        )
    e.save(record, args.output)
    print("Evidence SHA256:", e.digest(record))


if __name__ == "__main__":
    try:
        main()
    except (e.Rejected, KeyError, TypeError, ValueError) as error:
        raise SystemExit("BLOCKED: " + str(error)) from None
