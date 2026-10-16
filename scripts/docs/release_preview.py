"""Emit source-bound Docs preview data; never grant application release authority."""

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_PROJECT = "prj_Dtm2zO8sQQFqmnospPZgxbCi9Bbr"
sys.path.insert(0, str(ROOT / "scripts/release"))
import evidence as e
import free_gate as f


def build_digest(directory):
    e.require(directory.is_dir() and not directory.is_symlink(), "Docs build required")
    e.require(
        not any(parent.is_symlink() for parent in directory.parents),
        "Docs build parent alias",
    )
    value = hashlib.sha256()
    for file in sorted(directory.rglob("*")):
        e.require(not file.is_symlink(), "Docs build alias")
        if file.is_file():
            value.update(
                str(file.relative_to(directory)).encode()
                + b"\0"
                + hashlib.sha256(file.read_bytes()).digest()
            )
    return value.hexdigest()


def preview_record(
    sha,
    run_id,
    public,
    internal,
    hosted,
    deployment,
    artifact_digest,
    production_public,
    production_acceptance,
    production_artifact_digest,
    *,
    validation_channel="ci",
    staging_acceptance=None,
):
    e.require(
        re.fullmatch(r"[a-f0-9]{40}", sha) and str(run_id).isdigit(),
        "Exact Docs source/run required",
    )
    e.require(
        re.fullmatch(r"[a-f0-9]{64}", artifact_digest),
        "Uploaded public archive digest required",
    )
    e.require(
        re.fullmatch(r"[a-f0-9]{64}", production_artifact_digest),
        "Uploaded production archive digest required",
    )
    for directory, classification in [
        (public, "public"),
        (production_public, "public"),
        (internal, "internal"),
    ]:
        provenance = json.loads((directory / "generated/provenance.json").read_text())
        e.require(
            provenance.get("revision") == sha
            and provenance.get("classification") == classification,
            "Classified Docs build source mismatch",
        )
        build_digest(directory)
    origin = urlsplit(deployment.get("url", ""))
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
        and deployment.get("project") == "onesa-docs"
        and deployment.get("projectId") == PUBLIC_PROJECT
        and isinstance(deployment.get("deploymentId"), str)
        and deployment["deploymentId"].startswith("dpl_")
        and deployment.get("state") == "READY"
        and deployment.get("sourceRevision") == sha
        and "target" in deployment
        and deployment["target"] in {None, "preview"},
        "Actual public Preview identity required",
    )
    e.require(
        validation_channel in {"ci", "native-owner"},
        "Explicit Docs validation channel required",
    )
    pending_native = validation_channel == "native-owner"
    if pending_native:
        e.require(hosted is None, "Pending native mode cannot claim hosted evidence")
        hosted = staging_acceptance
        e.require(isinstance(hosted, dict), "Typed local staging acceptance required")
    e.require(
        hosted.get("result") == "PASS"
        and (pending_native or hosted.get("origin") == origin.geturl().rstrip("/"))
        and len(hosted.get("navigation", [])) == 2
        and len(hosted.get("icons", [])) == 3
        and len(hosted.get("accessibility", [])) >= 124
        and len(hosted.get("widths", [])) >= 20
        and hosted.get("links", 0) > 0
        and hosted.get("diagrams", 0) > 0
        and hosted.get("pdfs", 0) > 0
        and hosted.get("environment_context") == "staging"
        and hosted.get("provenance") == {"revision": sha, "classification": "public"},
        "Complete actual public Docs Preview acceptance required",
    )
    e.require(
        production_acceptance.get("result") == "PASS"
        and production_acceptance.get("environment_context") == "production"
        and production_acceptance.get("provenance")
        == {"revision": sha, "classification": "public"}
        and len(production_acceptance.get("accessibility", [])) >= 124
        and len(production_acceptance.get("widths", [])) >= 20,
        "Qualified production-context Docs variant required",
    )
    f.docs_acceptance_schema(hosted)
    f.docs_acceptance_schema(production_acceptance)
    checks = {
        name: "PASS"
        for name in [
            "classified_build",
            "dependency_security",
            "public_private_boundary",
            "system_appearance_and_accessibility",
            "diagrams_pdfs_navigation",
            "hosted_preview_identity",
            "hosted_preview_acceptance",
        ]
    }
    if pending_native:
        checks["hosted_preview_acceptance"] = "PENDING_NATIVE_OWNER"
    record = {
        "schema_version": 1,
        "repository": e.REPOSITORY,
        "candidate_commit": sha,
        "workflow_run_id": int(run_id),
        "source_sha256": e.source_hash(),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "target": "preview",
        "production_deployment_requested": False,
        "application_deployment_authorized": False,
        "backend_deployment_authorized": False,
        "scopes": {
            "public": {
                "classification": "public",
                "status": "BLOCKED" if pending_native else "PASS",
                "checks": checks,
                "build_environment": "production",
                "build_sha256": build_digest(production_public),
                "artifact_sha256": production_artifact_digest,
                "preview_artifact": {
                    "build_sha256": build_digest(public),
                    "artifact_sha256": artifact_digest,
                },
                "production_acceptance": production_acceptance,
                "preview": deployment,
                "hosted_acceptance": hosted,
            },
            "internal": {
                "classification": "internal",
                "status": "BLOCKED",
                "build_sha256": build_digest(internal),
                "checks": {
                    **checks,
                    "hosted_preview_identity": "BLOCKED",
                    "hosted_preview_acceptance": "BLOCKED",
                },
                "reason": "Actual protected Preview, approved engineering identity and current sign-in-policy evidence required; local fixture is insufficient.",
            },
        },
    }
    if pending_native:
        proof = record["scopes"]["public"]
        del proof["hosted_acceptance"]
        proof["validation_channel"] = "native-owner"
        proof["staging_acceptance"] = hosted
        record["native_validation_required"] = True
    else:
        f.public_docs_proof(record["scopes"]["public"], sha)
    return record


def main():
    e.require(
        os.environ.get("GITHUB_REPOSITORY") == e.REPOSITORY
        and os.environ.get("GITHUB_ACTOR") == e.OWNER
        and os.environ.get("GITHUB_REF") in {"refs/heads/staging", "refs/heads/main"},
        "Reviewed owner Docs Preview source required",
    )
    sha = os.environ["GITHUB_SHA"]
    e.require(
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        == sha,
        "Docs checkout/source mismatch",
    )
    folder = ROOT / "onesa-ai-platform-frontend/apps/docs"
    record = preview_record(
        sha,
        os.environ["GITHUB_RUN_ID"],
        folder / "build-public",
        folder / "build-internal",
        None
        if os.environ.get("DOCS_VALIDATION_CHANNEL", "ci") == "native-owner"
        else json.loads(Path(os.environ["DOCS_HOSTED_ACCEPTANCE"]).read_text()),
        json.loads(Path(os.environ["DOCS_PREVIEW_IDENTITY"]).read_text()),
        os.environ["DOCS_PUBLIC_ARTIFACT_DIGEST"],
        Path(os.environ["DOCS_PRODUCTION_PUBLIC_DIRECTORY"]),
        json.loads(Path(os.environ["DOCS_PRODUCTION_ACCEPTANCE"]).read_text()),
        os.environ["DOCS_PRODUCTION_ARTIFACT_DIGEST"],
        validation_channel=os.environ.get("DOCS_VALIDATION_CHANNEL", "ci"),
        staging_acceptance=json.loads(
            Path(os.environ["DOCS_STAGING_ACCEPTANCE"]).read_text()
        )
        if os.environ.get("DOCS_VALIDATION_CHANNEL", "ci") == "native-owner"
        else None,
    )
    e.save(record, os.environ["DOCS_QUALIFICATION_OUTPUT"])
    print(
        "Docs record emitted; pending native evidence never grants release authority."
    )


if __name__ == "__main__":
    main()
