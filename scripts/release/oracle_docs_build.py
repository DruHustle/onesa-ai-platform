"""Read genuine credential-free Docs builds for the external owner toolchain.

This produces build evidence only. It cannot publish, issue authorization, or
substitute an Actions artifact for owner provenance or native hosted acceptance.
"""

import hashlib
import io
import json
import os
import re
import stat
import zipfile
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import PurePosixPath

import oracle_owner as owner

REPOSITORY = "DruHustle/onesa-ai-platform"
BUILD_STEPS = {
    "Capture fresh synthetic application screenshots",
    "Verify dependency security and build classified public documentation",
    "Verify public documentation interactions and accessibility",
    "Qualify production-context public bytes before credentials and restore staging Preview",
    "Build and verify classified protected Docs before provider credentials",
    "Verify emitted favicon link and bundled icon",
    "Upload public site only",
    "Upload qualified production-context public site only",
}
PROVIDER_STEPS = {
    "Require exact reviewed CI before Preview provider credentials",
    "Prepare pinned isolated CLI before deployment credentials",
    "Inspect existing public docs project and source revisions",
    "Prepare separate Vercel documentation project",
    "Read owner-managed public Docs Preview test credential without mutation",
    "Publish verified public build as Preview only without dependency installation",
    "Verify actual deployment identity, readiness and source revision",
    "Verify actual public Preview interactions and boundary",
    "Remove private runner-owned Preview test credential",
    "Record source-bound independent Docs Preview qualification",
}
ARTIFACTS = {
    "onesa-public-docs-staging": "STAGING · Public developer documentation",
    "onesa-public-docs-production": "Public developer documentation",
}
FORBIDDEN = {
    "docs/architecture/ONESA_DESIGN_SYSTEM.html",
    "docs/operations/TAILSCALE_ADMINISTRATION.html",
    "onboarding.html",
    "generated/engineering-navigation.json",
    "generated/diagrams/onesa-design-system.svg",
    "generated/diagrams/tailscale-administration.pdf",
}


class Audience(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.labels = []
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if self.depth:
            self.depth += 1
        elif "docs-audience" in dict(attrs).get("class", "").split():
            owner.require(tag == "div", "DOCS_CONTEXT_ELEMENT")
            self.depth = 1
            self.parts = []

    def handle_endtag(self, tag):
        if self.depth:
            self.depth -= 1
            if not self.depth:
                self.labels.append(" ".join("".join(self.parts).split()))

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)


def archive_identity(raw, artifact, sha):
    owner.require(
        isinstance(raw, bytes)
        and 0 < len(raw) <= 128 * 1024**2
        and artifact["digest"] == "sha256:" + hashlib.sha256(raw).hexdigest(),
        "GENUINE_DOCS_ARCHIVE_DIGEST_REQUIRED",
    )
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            owner.require(
                1 <= len(names) <= 20000
                and len(names) == len(set(names))
                and sum(member.file_size for member in members) <= 256 * 1024**2,
                "DOCS_ARCHIVE_BOUNDS_OR_DUPLICATES",
            )
            files = {}
            for member in members:
                path = PurePosixPath(member.filename)
                owner.require(
                    not path.is_absolute()
                    and ".." not in path.parts
                    and str(path) == member.filename.rstrip("/")
                    and member.filename == member.orig_filename
                    and "\x00" not in member.orig_filename
                    and "\\" not in member.filename
                    and len(member.filename) <= 1024
                    and not member.flag_bits & 1
                    and member.compress_type
                    in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                    and stat.S_IFMT(member.external_attr >> 16)
                    in {0, stat.S_IFREG, stat.S_IFDIR}
                    and member.file_size <= 16 * 1024**2,
                    "DOCS_ARCHIVE_MEMBER_REFUSED",
                )
                if not member.is_dir():
                    files[member.filename] = hashlib.sha256(
                        archive.read(member)
                    ).hexdigest()
            owner.require(not FORBIDDEN & files.keys(), "PRIVATE_DOCS_IN_PUBLIC_BUILD")
            owner.require(100 <= len(files), "INCOMPLETE_PUBLIC_DOCS_TREE")
            provenance = json.loads(archive.read("generated/provenance.json"))
            owner.require(
                {
                    "revision",
                    "classification",
                    "policy_schema_version",
                    "code_sha256",
                    "sources",
                    "snapshot_sources",
                    "protected_document_sources",
                }
                <= provenance.keys()
                and provenance.get("revision") == sha
                and provenance.get("classification") == "public"
                and provenance["protected_document_sources"] is None
                and type(provenance["policy_schema_version"]) is int
                and provenance["policy_schema_version"] == 1
                and isinstance(provenance["code_sha256"], str)
                and re.fullmatch("[a-f0-9]{64}", provenance["code_sha256"])
                and isinstance(provenance["sources"], dict)
                and provenance["sources"]
                and isinstance(provenance["snapshot_sources"], dict),
                "PUBLIC_DOCS_SOURCE_OR_CLASSIFICATION_CHANGED",
            )
            page = Audience()
            page.feed(archive.read("index.html").decode("utf-8", errors="strict"))
            owner.require(
                page.depth == 0 and page.labels == [ARTIFACTS[artifact["name"]]],
                "DOCS_BUILD_CONTEXT_MISMATCH_NEVER_RELABEL_ARCHIVES",
            )
    except (KeyError, ValueError, UnicodeError, zipfile.BadZipFile) as error:
        raise owner.Rejected("DOCS_ARCHIVE_INCOMPLETE_OR_INVALID") from error
    return {
        "artifact_id": artifact["id"],
        "name": artifact["name"],
        "archive_sha256": hashlib.sha256(raw).hexdigest(),
        "archive_bytes": len(raw),
        "files": len(files),
        "file_manifest_sha256": owner.digest(files),
    }


def read_build(github, source, run_id, archives, *, now=None):
    """A pinned external consumer supplies downloaded bytes, never a supplied PASS."""
    owner.require(not os.getenv("GITHUB_ACTIONS"), "EXTERNAL_DOCS_READER_REQUIRED")
    owner.require(
        set(source) == {"repository", "candidate_commit", "source_tree"}
        and source["repository"] == REPOSITORY
        and all(
            re.fullmatch("[a-f0-9]{40}", source[key])
            for key in ["candidate_commit", "source_tree"]
        )
        and type(run_id) is int
        and run_id > 0,
        "REAL_ACTIONS_BUILD_ID_AND_EXACT_SOURCE_REQUIRED",
    )
    github.owner()
    ci = github.qualify(source)
    owner.require(ci, "MANDATORY_NATIVE_CI_REQUIRED")
    prefix = "repos/" + REPOSITORY + "/actions/runs/" + str(run_id)
    run = github.api(prefix)
    sha = source["candidate_commit"]
    owner.require(
        run["id"] == run_id
        and run["repository"]["full_name"] == REPOSITORY
        and run["head_repository"]["full_name"] == REPOSITORY
        and run["head_sha"] == sha
        and run["head_branch"] == "main"
        and run["path"] == ".github/workflows/docs-hosting.yml"
        and run["event"] == "workflow_dispatch"
        and type(run["run_attempt"]) is int
        and run["run_attempt"] == 1
        and run["status"] == "completed"
        and run["conclusion"] == "success"
        and run["actor"]["login"] == run["triggering_actor"]["login"] == owner.OWNER,
        "DOCS_BUILD_RUN_PROVENANCE_REQUIRED",
    )
    clock = now or datetime.now(timezone.utc)
    stamp = datetime.fromisoformat(run["updated_at"].replace("Z", "+00:00"))
    owner.require(
        stamp.utcoffset() == timedelta()
        and clock.utcoffset() == timedelta()
        and timedelta() <= clock - stamp < timedelta(hours=6),
        "DOCS_BUILD_EXPIRED_OR_FUTURE",
    )
    jobs = github.api(prefix + "/jobs?filter=latest&per_page=100")
    owner.require(
        jobs["total_count"] == len(jobs["jobs"]) == 1,
        "COMPLETE_SINGLE_DOCS_BUILD_JOB_REQUIRED",
    )
    job = jobs["jobs"][0]
    steps = {step["name"]: step for step in job["steps"]}
    owner.require(
        job["name"] == "docs-hosting"
        and job["run_id"] == run_id
        and job["status"] == "completed"
        and job["conclusion"] == "success"
        and all(
            sum(step["name"] == name for step in job["steps"]) == 1
            for name in BUILD_STEPS | PROVIDER_STEPS
        )
        and all(
            step["status"] == "completed"
            and step["conclusion"] in {"success", "skipped"}
            for step in job["steps"]
        )
        and all(
            steps.get(name, {}).get("status") == "completed"
            and steps[name].get("conclusion") == "success"
            for name in BUILD_STEPS
        )
        and all(
            steps.get(name, {}).get("status") == "completed"
            and steps[name].get("conclusion") == "skipped"
            for name in PROVIDER_STEPS
        ),
        "MANDATORY_DOCS_BUILD_FAILED_SKIPPED_OR_PROVIDER_PATH_EXECUTED",
    )
    listing = github.api(prefix + "/artifacts?per_page=100")
    items = listing["artifacts"]
    owner.require(
        listing["total_count"] == len(items) == 2
        and {item["name"] for item in items} == ARTIFACTS.keys()
        and {item["id"] for item in items} == archives.keys(),
        "EXACT_TWO_PUBLIC_DOCS_ARTIFACTS_REQUIRED",
    )
    result = []
    for item in sorted(items, key=lambda item: item["name"]):
        owner.require(
            type(item["id"]) is int
            and item["id"] > 0
            and item["expired"] is False
            and item["workflow_run"]["id"] == run_id
            and item["workflow_run"]["head_sha"] == sha,
            "DOCS_ARTIFACT_ORIGIN_EXPIRED_OR_CHANGED",
        )
        result.append(archive_identity(archives[item["id"]], item, sha))
    owner.require(
        github.qualify(source) == ci
        and github.api(prefix) == run
        and github.api(prefix + "/artifacts?per_page=100") == listing,
        "DOCS_SOURCE_CI_OR_ARTIFACT_CUSTODY_CHANGED_DURING_READ",
    )
    return {
        "state": "CREDENTIAL_FREE_DOCS_BUILD_VERIFIED_NOT_HOSTED_QUALIFICATION",
        "source": source,
        "actions_build_run_id": run_id,
        "actions_job_id": job["id"],
        "native_ci": ci,
        "artifacts": result,
        "STAGING_VERIFIED": "BLOCKED",
        "required_external_checks": [
            "owner_controlled_preview_publication_and_provider_identity",
            "actual_native_source_bound_hosted_acceptance",
            "current_scoped_owner_authorization",
            "canonical_production_identity_and_affected_workflows",
        ],
        "production_deployment_authorized": False,
        "application_deployment_authorized": False,
        "backend_deployment_authorized": False,
    }
