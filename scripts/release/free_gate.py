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
import selectors
import stat
import subprocess
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import evidence as e

WORKFLOW = "free-authorization.yml"
QUALIFICATION = "free-qualification.yml"
DELIVERY_SCOPES = {"full", "docs-public", "docs-internal"}
RETAINED_APPLICATION_COMMIT = "9b986aa4b0fcee0cb3789a2fc91eba260785dffe"
PUBLIC_DOCS_PROJECT = "prj_Dtm2zO8sQQFqmnospPZgxbCi9Bbr"
INTERNAL_DOCS_METADATA_ASSET = "protected-docs-preview-qualification.json"
INTERNAL_DOCS_METADATA_BYTES = 64 * 1024
INTERNAL_DOCS_CONDITIONAL_AUTHORITY = "REQUIRES_EXTERNAL_LIVE_VALIDATION"
PUBLIC_DOCS_METADATA_ASSET = "public-docs-native-preview-qualification.json"
PUBLIC_DOCS_METADATA_KIND = "onesa-docs-public-native-preview-metadata"


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
        {"label": app["label"], "href": app["href"].rstrip("/")}
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
        for item in sorted(
            files, key=lambda entry: PurePosixPath(entry.filename).parts
        ):
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


def _internal_docs_asset_bytes(asset_id):
    """Download only sanitized metadata through the fixed repository asset API."""
    e.require(
        type(asset_id) is int and asset_id > 0, "Positive immutable asset ID required"
    )
    command = [
        "gh",
        "api",
        f"repos/{e.REPOSITORY}/releases/assets/{asset_id}",
        "--hostname",
        "github.com",
        "--method",
        "GET",
        "--header",
        "Accept: application/octet-stream",
    ]
    process = None
    try:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        deadline = time.monotonic() + 30
        content = bytearray()
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                e.require(
                    remaining > 0 and selector.select(remaining),
                    "Metadata download timed out",
                )
                chunk = os.read(
                    process.stdout.fileno(),
                    min(4096, INTERNAL_DOCS_METADATA_BYTES + 1 - len(content)),
                )
                if not chunk:
                    break
                content.extend(chunk)
                e.require(
                    len(content) <= INTERNAL_DOCS_METADATA_BYTES,
                    "Metadata download exceeds bound",
                )
        e.require(
            process.wait(timeout=max(0.001, deadline - time.monotonic())) == 0,
            "Metadata download unavailable",
        )
        return bytes(content)
    except (OSError, subprocess.TimeoutExpired):
        raise e.Rejected("Metadata download unavailable") from None
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait()
            process.stdout.close()


def _internal_docs_local_source(sha):
    """Metadata from a dirty or different verifier checkout is never qualifying."""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=e.ROOT,
            capture_output=True,
            timeout=10,
            check=False,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=e.ROOT,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise e.Rejected("Exact clean verifier checkout required") from None
    e.require(
        head.returncode == 0
        and head.stdout.strip() == sha.encode()
        and status.returncode == 0
        and not status.stdout,
        "Exact clean verifier checkout required",
    )
    return e.source_hash()


def _internal_docs_json(content):
    def unique(pairs):
        record = {}
        for key, value in pairs:
            e.require(key not in record, "Duplicate metadata key")
            record[key] = value
        return record

    def nonfinite(_value):
        raise e.Rejected("Nonfinite metadata value")

    try:
        return json.loads(content, object_pairs_hook=unique, parse_constant=nonfinite)
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        if isinstance(error, e.Rejected):
            raise
        raise e.Rejected("Sanitized metadata JSON required") from None


def _internal_docs_fresh(timestamp, now):
    try:
        e.require(
            isinstance(timestamp, str) and e.fresh(timestamp, now),
            "Fresh metadata timestamps required",
        )
    except (ValueError, TypeError):
        raise e.Rejected("Fresh metadata timestamps required") from None


def internal_docs_preview_metadata(
    github,
    sha,
    release_id,
    asset_id,
    asset_digest,
    producer_sha256,
    delivery_scope="docs-internal",
):
    """Read owner draft custody; never establish hosted PASS or authorize deployment.

    The producer hash and immutable asset ID/digest come from the independently
    reviewed owner-held executor, not from a caller's PASS record. This reader is
    used by conditional qualification, authorization and CLI only for metadata
    custody. It establishes neither hosted PASS nor production authority. Actual
    provider, all-path access, approved engineering session/MFA, private artifact
    bytes and source binding still require external live validation.
    """
    e.require(
        e.PRODUCT == "onesa-ai-platform" and delivery_scope == "docs-internal",
        "Protected Docs metadata scope required",
    )
    e.require(
        isinstance(sha, str) and re.fullmatch(r"[a-f0-9]{40}", sha),
        "Exact candidate commit required",
    )
    e.require(
        type(release_id) is int
        and release_id > 0
        and type(asset_id) is int
        and asset_id > 0,
        "Positive immutable release and asset IDs required",
    )
    e.require(
        isinstance(asset_digest, str)
        and re.fullmatch(r"sha256:[a-f0-9]{64}", asset_digest)
        and isinstance(producer_sha256, str)
        and re.fullmatch(r"[a-f0-9]{64}", producer_sha256),
        "Reviewed asset and producer digests required",
    )
    fingerprint = _internal_docs_local_source(sha)
    current_main(github, sha)
    code, ci = e.checked_ci(github, sha)
    e.require(code == "PASS", "Exact main CI required for protected Docs metadata")
    now = datetime.now(timezone.utc)
    for reference in ci:
        run = github.run(reference["run_id"])
        e.trusted_run(run, reference["workflow"], sha, {"main"}, event="push")
        _internal_docs_fresh(run.get("updated_at"), now)
    expected_ci = [item for item in ci if item["workflow"] == e.POLICY["ci"]]
    e.require(len(expected_ci) == 1, "One exact main CI producer required")

    def custody():
        release = github.api(f"repos/{e.REPOSITORY}/releases/{release_id}")
        e.require(
            isinstance(release, dict)
            and type(release.get("id")) is int
            and release.get("id") == release_id
            and release.get("draft") is True
            and release.get("published_at") is None
            and isinstance(release.get("author"), dict)
            and release["author"].get("login") == e.OWNER
            and release.get("target_commitish") == sha
            and release.get("tag_name") == "docs-internal-qualification-" + sha
            and (release.get("body") is None or release.get("body") == ""),
            "Owner-only exact-source draft release required",
        )
        _internal_docs_fresh(release.get("created_at"), now)
        _internal_docs_fresh(release.get("updated_at"), now)
        entries = release.get("assets")
        e.require(
            isinstance(entries, list)
            and len(entries) == 1
            and isinstance(entries[0], dict)
            and entries[0].get("id") == asset_id,
            "Draft must contain only the pinned metadata asset",
        )
        asset = github.api(f"repos/{e.REPOSITORY}/releases/assets/{asset_id}")
        e.require(
            isinstance(asset, dict)
            and type(asset.get("id")) is int
            and asset.get("id") == asset_id
            and asset.get("name") == INTERNAL_DOCS_METADATA_ASSET
            and asset.get("state") == "uploaded"
            and isinstance(asset.get("uploader"), dict)
            and asset["uploader"].get("login") == e.OWNER
            and asset.get("digest") == asset_digest
            and asset.get("content_type") == "application/json"
            and type(asset.get("size")) is int
            and 0 < asset["size"] <= INTERNAL_DOCS_METADATA_BYTES
            and asset.get("url")
            == f"https://api.github.com/repos/{e.REPOSITORY}/releases/assets/{asset_id}",
            "Owner-uploaded immutable sanitized metadata asset required",
        )
        _internal_docs_fresh(asset.get("created_at"), now)
        _internal_docs_fresh(asset.get("updated_at"), now)
        release_proof = {
            key: release.get(key)
            for key in [
                "id",
                "draft",
                "published_at",
                "target_commitish",
                "tag_name",
                "body",
                "created_at",
                "updated_at",
            ]
        }
        release_proof.update(author=e.OWNER, asset_id=asset_id)
        asset_proof = {
            key: asset.get(key)
            for key in [
                "id",
                "name",
                "state",
                "digest",
                "content_type",
                "size",
                "url",
                "created_at",
                "updated_at",
            ]
        }
        asset_proof["uploader"] = e.OWNER
        return release_proof, asset_proof

    before = custody()
    content = _internal_docs_asset_bytes(asset_id)
    e.require(
        isinstance(content, bytes)
        and len(content) == before[1]["size"]
        and len(content) <= INTERNAL_DOCS_METADATA_BYTES
        and "sha256:" + hashlib.sha256(content).hexdigest() == asset_digest,
        "Downloaded metadata size or digest mismatch",
    )
    record = _internal_docs_json(content)
    keys = {
        "schema_version",
        "kind",
        "repository",
        "candidate_commit",
        "source_sha256",
        "producer_sha256",
        "ci_run_id",
        "verified_at",
        "delivery_scope",
        "staging",
        "private_artifacts",
        "access_configuration_sha256",
        "counts",
        "application_deployment_authorized",
        "backend_deployment_authorized",
        "production_deployment_authorized",
    }
    e.require(
        isinstance(record, dict) and record.keys() == keys,
        "Exact sanitized metadata schema required",
    )
    e.require(
        type(record["schema_version"]) is int
        and record["schema_version"] == 1
        and record["kind"] == "protected-docs-preview-qualification"
        and record["repository"] == e.REPOSITORY
        and record["candidate_commit"] == sha
        and record["source_sha256"] == fingerprint
        and record["producer_sha256"] == producer_sha256
        and type(record["ci_run_id"]) is int
        and record["ci_run_id"] == expected_ci[0]["run_id"]
        and record["delivery_scope"] == "docs-internal"
        and all(
            record[key] is False
            for key in [
                "application_deployment_authorized",
                "backend_deployment_authorized",
                "production_deployment_authorized",
            ]
        ),
        "Metadata candidate, producer, CI, scope or no-grant mismatch",
    )
    _internal_docs_fresh(record["verified_at"], now)
    stage = record["staging"]
    e.require(
        isinstance(stage, dict)
        and stage.keys()
        == {"project", "environment", "deployment_id", "source_commit", "origin"}
        and stage["project"] == "onesa-engineering-docs"
        and stage["environment"] == "preview"
        and isinstance(stage["deployment_id"], str)
        and re.fullmatch(
            r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}",
            stage["deployment_id"],
        )
        and stage["source_commit"] == sha
        and isinstance(stage["origin"], str)
        and re.fullmatch(
            r"https://[a-f0-9]{8}\.onesa-engineering-docs\.pages\.dev", stage["origin"]
        )
        and stage["origin"].split("//", 1)[1].split(".", 1)[0]
        == stage["deployment_id"][:8],
        "Exact protected Pages deployment Preview required",
    )
    artifacts = record["private_artifacts"]
    e.require(
        isinstance(artifacts, dict)
        and artifacts.keys()
        == {
            "staging_tree_sha256",
            "staging_archive_sha256",
            "production_tree_sha256",
            "production_archive_sha256",
        }
        and all(
            isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value)
            for value in artifacts.values()
        )
        and isinstance(record["access_configuration_sha256"], str)
        and re.fullmatch(r"[a-f0-9]{64}", record["access_configuration_sha256"]),
        "Private artifact and Access hashes only required",
    )
    counts = record["counts"]
    exact_counts = {
        "source_provenance_checks": 1,
        "accessibility_views": 18,
        "layout_views": 18,
        "architecture_topics": 18,
        "engineering_chapters": 17,
        "onboarding_days": 4,
        "application_navigation_views": 2,
        "identity_icons": 3,
        "pdfs": 22,
        "diagrams": 83,
        "mfa_checks": 1,
        "blocking_accessibility": 0,
        "unexpected_browser_errors": 0,
    }
    e.require(
        isinstance(counts, dict)
        and counts.keys()
        == exact_counts.keys() | {"unauthenticated_denials", "verified_asset_responses"}
        and all(type(value) is int for value in counts.values())
        and all(counts[key] == value for key, value in exact_counts.items())
        and all(
            1 <= counts[key] <= 20000
            for key in ["unauthenticated_denials", "verified_asset_responses"]
        ),
        "Exact bounded sanitized count schema required",
    )
    e.require(custody() == before, "Draft metadata custody changed during read")
    current_main(github, sha)
    refreshed_code, refreshed_ci = e.checked_ci(github, sha)
    e.require(
        refreshed_code == "PASS"
        and e.digest(refreshed_ci) == e.digest(ci)
        and _internal_docs_local_source(sha) == fingerprint,
        "Source or CI changed during metadata read",
    )
    return {
        "status": "REQUIRES_EXTERNAL_LIVE_VALIDATION",
        "STAGING_VERIFIED": "BLOCKED",
        "PRODUCTION_AUTHORIZED": False,
        "delivery_scope": "docs-internal",
        "application_deployment_authorized": False,
        "backend_deployment_authorized": False,
        "production_deployment_authorized": False,
        "metadata": record,
        "custody": {
            "release_id": release_id,
            "asset_id": asset_id,
            "asset_digest": asset_digest,
        },
        "required_external_checks": [
            "actual_provider_preview_and_source",
            "all_paths_protected",
            "approved_engineering_session_and_mfa",
            "exact_private_artifact_bytes",
            "retained_application_and_api_and_no_auto_production",
        ],
    }


def public_docs_native_preview(github, sha, staging_run):
    """Verify pending Preview custody and bytes; never establish hosted PASS."""
    from urllib.parse import urlsplit

    e.require(e.PRODUCT == "onesa-ai-platform", "Public Docs is Platform-only")
    e.require(
        (type(staging_run) is int and staging_run > 0)
        or (
            isinstance(staging_run, str)
            and re.fullmatch(r"[0-9]{1,20}", staging_run)
            and int(staging_run) > 0
        ),
        "Explicit positive registered Preview run required",
    )
    fingerprint = _internal_docs_local_source(sha)
    code, references = e.checked_ci(github, sha)
    e.require(code == "PASS", "Exact source CI required for native Preview")
    now = datetime.now(timezone.utc)
    for reference in references:
        ci_run = github.run(reference["run_id"])
        e.trusted_run(
            ci_run, reference["workflow"], sha, {"staging", "main"}, event="push"
        )
        _internal_docs_fresh(ci_run.get("updated_at"), now)
    run = github.run(staging_run)
    e.trusted_run(run, "docs-hosting.yml", sha, {"staging", "main"})
    _internal_docs_fresh(run.get("updated_at"), now)
    record, origin = github.artifact(run, "documentation-qualification")
    e.require(
        isinstance(record, dict)
        and type(record.get("schema_version")) is int
        and record["schema_version"] == 1
        and record.get("repository") == e.REPOSITORY
        and record.get("candidate_commit") == sha
        and record.get("workflow_run_id") == run["id"]
        and record.get("source_sha256") == fingerprint
        and record.get("target") == "preview"
        and record.get("native_validation_required") is True
        and record.get("production_deployment_requested") is False
        and record.get("application_deployment_authorized") is False
        and record.get("backend_deployment_authorized") is False,
        "Source-bound pending native Preview required",
    )
    _internal_docs_fresh(record.get("verified_at"), now)
    scopes = record.get("scopes")
    e.require(isinstance(scopes, dict), "Classified Preview scopes required")
    proof = scopes.get("public")
    e.require(isinstance(proof, dict), "Public Preview proof required")
    checks = proof.get("checks")
    local = {
        "classified_build",
        "dependency_security",
        "public_private_boundary",
        "system_appearance_and_accessibility",
        "diagrams_pdfs_navigation",
        "hosted_preview_identity",
    }
    e.require(
        proof.get("classification") == "public"
        and proof.get("status") == "BLOCKED"
        and proof.get("validation_channel") == "native-owner"
        and proof.get("build_environment") == "production"
        and "hosted_acceptance" not in proof
        and isinstance(checks, dict)
        and checks.keys() == local | {"hosted_preview_acceptance"}
        and all(checks[key] == "PASS" for key in local)
        and checks["hosted_preview_acceptance"] == "PENDING_NATIVE_OWNER",
        "Hosted native validation must remain explicitly pending",
    )
    preview = proof.get("preview")
    e.require(isinstance(preview, dict), "Actual Preview identity required")
    try:
        e.require(isinstance(preview.get("url"), str), "Preview origin string required")
        parsed = urlsplit(preview["url"])
        valid_origin = (
            parsed.scheme == "https"
            and parsed.hostname
            and re.fullmatch(
                r"onesa-docs-[a-z0-9]+-druhustles-projects\.vercel\.app",
                parsed.hostname,
            )
            and not parsed.username
            and not parsed.password
            and not parsed.port
            and not parsed.query
            and not parsed.fragment
            and preview["url"] == "https://" + parsed.hostname
        )
    except ValueError:
        valid_origin = False
    e.require(
        valid_origin
        and preview.get("project") == "onesa-docs"
        and preview.get("projectId") == PUBLIC_DOCS_PROJECT
        and isinstance(preview.get("deploymentId"), str)
        and re.fullmatch(r"dpl_[A-Za-z0-9]+", preview["deploymentId"])
        and preview.get("state") == "READY"
        and preview.get("sourceRevision") == sha
        and "target" in preview
        and preview["target"] in {None, "preview"},
        "Exact READY public Docs Preview identity required",
    )
    for key, context in [
        ("staging_acceptance", "staging"),
        ("production_acceptance", "production"),
    ]:
        accepted = proof.get(key)
        e.require(isinstance(accepted, dict), "Actual typed local acceptance required")
        docs_acceptance_schema(accepted)
        e.require(
            accepted.get("result") == "PASS"
            and accepted.get("environment_context") == context
            and accepted.get("provenance")
            == {"revision": sha, "classification": "public"}
            and type(accepted.get("links")) is int
            and accepted["links"] > 0
            and accepted.get("diagrams") == 21
            and accepted.get("pdfs") == 11,
            "Classified local context acceptance mismatch",
        )
    preview_proof = proof.get("preview_artifact")
    e.require(isinstance(preview_proof, dict), "Staging archive proof required")
    for variant in [proof, preview_proof]:
        e.require(
            all(
                isinstance(variant.get(key), str)
                and re.fullmatch(r"[a-f0-9]{64}", variant[key])
                for key in ["artifact_sha256", "build_sha256"]
            ),
            "Exact public archive and tree hashes required",
        )
    stage_archive = public_docs_artifact(
        github, run, preview_proof, "onesa-public-docs-staging"
    )
    production_archive = public_docs_artifact(github, run, proof)
    e.require(
        all(
            type(item["id"]) is int and item["id"] > 0
            for item in [stage_archive, production_archive]
        )
        and stage_archive["id"] != production_archive["id"],
        "Distinct classified context archives required",
    )
    refreshed_run = github.run(staging_run)
    e.trusted_run(refreshed_run, "docs-hosting.yml", sha, {"staging", "main"})
    _internal_docs_fresh(refreshed_run.get("updated_at"), now)
    e.require(refreshed_run == run, "Registered Preview run changed during review")
    repeated, repeated_origin = github.artifact(
        refreshed_run, "documentation-qualification"
    )
    refreshed_code, refreshed_ci = e.checked_ci(github, sha)
    e.require(
        record == repeated
        and origin == repeated_origin
        and refreshed_code == "PASS"
        and references == refreshed_ci
        and fingerprint == _internal_docs_local_source(sha),
        "Preview custody, source or CI changed during review",
    )
    return {
        "status": "REQUIRES_EXTERNAL_LIVE_VALIDATION",
        "STAGING_VERIFIED": "BLOCKED",
        "delivery_scope": "docs-public",
        "classification": "public",
        "application_deployment_authorized": False,
        "backend_deployment_authorized": False,
        "production_deployment_authorized": False,
        "record": record,
        "artifact": origin,
        "public_site_artifact": production_archive,
        "preview_site_artifact": stage_archive,
        "ci": references,
    }


def public_docs_preview_metadata(github, sha, staging_run, custody):
    """Validate owner metadata custody; external native acceptance remains mandatory."""
    e.require(
        isinstance(custody, dict)
        and custody.keys()
        == {"release_id", "asset_id", "asset_digest", "producer_sha256"},
        "Exact owner metadata custody required",
    )
    release_id, asset_id = custody["release_id"], custody["asset_id"]
    producer, asset_digest = custody["producer_sha256"], custody["asset_digest"]
    e.require(
        type(release_id) is int
        and release_id > 0
        and type(asset_id) is int
        and asset_id > 0,
        "Positive immutable metadata IDs required",
    )
    e.require(
        isinstance(producer, str)
        and re.fullmatch(r"[a-f0-9]{64}", producer)
        and isinstance(asset_digest, str)
        and re.fullmatch(r"sha256:[a-f0-9]{64}", asset_digest),
        "Reviewed producer and metadata digests required",
    )
    current_main(github, sha)
    stage = public_docs_native_preview(github, sha, staging_run)
    for reference in stage["ci"]:
        e.trusted_run(
            github.run(reference["run_id"]),
            reference["workflow"],
            sha,
            {"main"},
            event="push",
        )
    now = datetime.now(timezone.utc)

    def read_custody():
        release = github.api(f"repos/{e.REPOSITORY}/releases/{release_id}")
        e.require(
            isinstance(release, dict)
            and type(release.get("id")) is int
            and release["id"] == release_id
            and release.get("draft") is True
            and release.get("published_at") is None
            and isinstance(release.get("author"), dict)
            and release["author"].get("login") == e.OWNER
            and release.get("target_commitish") == sha
            and release.get("tag_name") == "docs-public-native-qualification-" + sha
            and (release.get("body") is None or release.get("body") == "")
            and isinstance(release.get("assets"), list)
            and len(release["assets"]) == 1
            and isinstance(release["assets"][0], dict)
            and release["assets"][0].get("id") == asset_id,
            "Single owner-uploaded exact-source draft metadata required",
        )
        # Real asset entries contain additional provider metadata; only IDs/cardinality bind here.
        asset = github.api(f"repos/{e.REPOSITORY}/releases/assets/{asset_id}")
        e.require(
            isinstance(asset, dict)
            and type(asset.get("id")) is int
            and asset["id"] == asset_id
            and asset.get("name") == PUBLIC_DOCS_METADATA_ASSET
            and asset.get("state") == "uploaded"
            and isinstance(asset.get("uploader"), dict)
            and asset["uploader"].get("login") == e.OWNER
            and asset.get("digest") == asset_digest
            and asset.get("content_type") == "application/json"
            and type(asset.get("size")) is int
            and 0 < asset["size"] <= INTERNAL_DOCS_METADATA_BYTES
            and asset.get("url")
            == f"https://api.github.com/repos/{e.REPOSITORY}/releases/assets/{asset_id}",
            "Immutable owner-uploaded public metadata asset required",
        )
        for value in [release, asset]:
            for key in ["created_at", "updated_at"]:
                _internal_docs_fresh(value.get(key), now)
        return {
            key: release.get(key)
            for key in [
                "id",
                "draft",
                "published_at",
                "target_commitish",
                "tag_name",
                "body",
                "created_at",
                "updated_at",
            ]
        }, {
            key: asset.get(key)
            for key in [
                "id",
                "name",
                "state",
                "digest",
                "content_type",
                "size",
                "url",
                "created_at",
                "updated_at",
            ]
        }

    before = read_custody()
    raw = _internal_docs_asset_bytes(asset_id)
    e.require(
        isinstance(raw, bytes)
        and len(raw) == before[1]["size"]
        and "sha256:" + hashlib.sha256(raw).hexdigest() == asset_digest,
        "Downloaded public metadata size or digest mismatch",
    )
    record = _internal_docs_json(raw)
    _public_docs_native_metadata(record, sha, producer, stage, now)
    e.require(read_custody() == before, "Public draft custody changed during read")
    current_main(github, sha)
    again = public_docs_native_preview(github, sha, staging_run)
    e.require(
        again == stage, "Public Preview, CI or archive custody changed during read"
    )
    return {
        **stage,
        "metadata": record,
        "custody": {
            "release_id": release_id,
            "asset_id": asset_id,
            "asset_digest": asset_digest,
        },
        "required_external_checks": [
            "actual_native_full_public_acceptance",
            "exact_preview_and_both_archive_bytes",
            "retained_application_api_and_no_auto_production",
            "fresh_latest_owner_decision",
        ],
    }


def _public_docs_native_metadata(record, sha, producer, stage, now):
    """Counts and hashes are metadata only; this validator never grants hosted PASS."""
    keys = {
        "schema_version",
        "evidence_kind",
        "repository",
        "candidate_commit",
        "source_sha256",
        "verified_at",
        "delivery_scope",
        "classification",
        "build_environment",
        "producer_sha256",
        "ci_sha256",
        "staging_run_id",
        "preview_record_sha256",
        "preview_artifact_id",
        "production_artifact_id",
        "preview_artifact_sha256",
        "production_artifact_sha256",
        "preview_build_sha256",
        "production_build_sha256",
        "hosted_acceptance_sha256",
        "preview",
        "counts",
        "application_deployment_authorized",
        "backend_deployment_authorized",
        "production_deployment_authorized",
    }
    e.require(
        isinstance(record, dict) and record.keys() == keys,
        "Exact sanitized public metadata schema required",
    )
    proof = stage["record"]["scopes"]["public"]
    e.require(
        type(record["schema_version"]) is int
        and record["schema_version"] == 1
        and record["evidence_kind"] == PUBLIC_DOCS_METADATA_KIND
        and record["repository"] == e.REPOSITORY
        and record["candidate_commit"] == sha
        and record["source_sha256"] == e.source_hash()
        and record["delivery_scope"] == "docs-public"
        and record["classification"] == "public"
        and record["build_environment"] == "staging"
        and record["producer_sha256"] == producer
        and record["ci_sha256"] == e.digest(stage["ci"])
        and type(record["staging_run_id"]) is int
        and record["staging_run_id"] == stage["artifact"]["run_id"]
        and record["preview_record_sha256"] == e.digest(stage["record"])
        and type(record["preview_artifact_id"]) is int
        and record["preview_artifact_id"] == stage["preview_site_artifact"]["id"]
        and type(record["production_artifact_id"]) is int
        and record["production_artifact_id"] == stage["public_site_artifact"]["id"]
        and record["preview_artifact_sha256"]
        == proof["preview_artifact"]["artifact_sha256"]
        and record["production_artifact_sha256"] == proof["artifact_sha256"]
        and record["preview_build_sha256"] == proof["preview_artifact"]["build_sha256"]
        and record["production_build_sha256"] == proof["build_sha256"]
        and isinstance(record["hosted_acceptance_sha256"], str)
        and re.fullmatch(r"[a-f0-9]{64}", record["hosted_acceptance_sha256"])
        and all(
            record[key] is False
            for key in [
                "application_deployment_authorized",
                "backend_deployment_authorized",
                "production_deployment_authorized",
            ]
        ),
        "Public metadata source, producer, CI, archives or no-grant mismatch",
    )
    _internal_docs_fresh(record["verified_at"], now)
    preview = proof["preview"]
    e.require(
        record["preview"]
        == {
            "provider": "vercel",
            "project": "onesa-docs",
            "project_id": PUBLIC_DOCS_PROJECT,
            "deployment_id": preview["deploymentId"],
            "origin": preview["url"].rstrip("/"),
            "source_commit": sha,
            "environment": "preview",
        },
        "Metadata Preview differs from registered producer",
    )
    counts = record["counts"]
    expected = {
        "accessibility_views": 124,
        "layout_views": 20,
        "navigation_views": 2,
        "identity_icons": 3,
        "diagrams": 21,
        "manual_pdfs": 11,
    }
    e.require(
        isinstance(counts, dict)
        and counts.keys() == expected.keys() | {"links"}
        and all(type(value) is int for value in counts.values())
        and all(counts[key] == value for key, value in expected.items())
        and 0 < counts["links"] <= 500000,
        "Bounded public metadata counts required",
    )
    return record


def public_docs_native_event(path, delivery_scope, producer, staging_run):
    """Read bounded dispatch inputs as data, never shell code or a live proof."""
    file = Path(path)
    e.require(
        str(file) == os.getenv("GITHUB_EVENT_PATH")
        and file.is_file()
        and not file.is_symlink()
        and 0 < file.stat().st_size <= 1024 * 1024,
        "Bounded native dispatch event required",
    )
    with file.open("rb") as stream:
        raw = stream.read(1024 * 1024 + 1)
    e.require(len(raw) <= 1024 * 1024, "Bounded native dispatch event required")
    event = _internal_docs_json(raw)
    e.require(isinstance(event, dict), "Structured dispatch event required")
    inputs = event.get("inputs")
    if inputs is None:
        inputs = {}
    e.require(
        isinstance(inputs, dict)
        and inputs.keys()
        <= {
            "staging_run",
            "delivery_scope",
            "metadata_release_id",
            "metadata_asset_id",
            "metadata_asset_digest",
            "metadata_producer_sha256",
            "native_custody_mode",
            "native_metadata",
        },
        "Structured known dispatch inputs required",
    )
    mode = inputs.get("native_custody_mode", "none")
    content = inputs.get("native_metadata", "")
    e.require(
        isinstance(mode, str) and mode in {"none", "actions-native"},
        "Explicit native custody mode required",
    )
    e.require(isinstance(content, str), "Native metadata input must be JSON text")
    if mode == "none":
        e.require(
            not content, "Native metadata requires explicit artifact custody mode"
        )
        return None
    e.require(
        os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch"
        and delivery_scope == "docs-public"
        and inputs.get("delivery_scope") == "docs-public"
        and inputs.get("staging_run") == str(staging_run)
        and inputs.get("metadata_producer_sha256") == producer
        and isinstance(producer, str)
        and re.fullmatch(r"[a-f0-9]{64}", producer)
        and not any(
            inputs.get(key)
            for key in [
                "metadata_release_id",
                "metadata_asset_id",
                "metadata_asset_digest",
            ]
        )
        and 0 < len(content.encode("utf8")) <= 32768,
        "Exact public native artifact inputs required; mixed custody is forbidden",
    )
    return {
        "channel": "actions-native",
        "metadata": _internal_docs_json(content),
        "producer_sha256": producer,
    }


def public_docs_actions_preview_metadata(github, sha, staging_run, custody, run):
    """The existing owner qualification artifact is custody, not a deployment grant."""
    e.require(
        isinstance(custody, dict)
        and custody.keys() == {"channel", "metadata", "producer_sha256"}
        and custody["channel"] == "actions-native"
        and isinstance(custody["producer_sha256"], str)
        and re.fullmatch(r"[a-f0-9]{64}", custody["producer_sha256"]),
        "Exact native Actions metadata and producer pin required",
    )
    e.trusted_run(run, QUALIFICATION, sha, {"main"}, completed=False)
    current_main(github, sha)
    stage = public_docs_native_preview(github, sha, staging_run)
    for reference in stage["ci"]:
        e.trusted_run(
            github.run(reference["run_id"]),
            reference["workflow"],
            sha,
            {"main"},
            event="push",
        )
    metadata = _public_docs_native_metadata(
        custody["metadata"],
        sha,
        custody["producer_sha256"],
        stage,
        datetime.now(timezone.utc),
    )
    current_main(github, sha)
    again = public_docs_native_preview(github, sha, staging_run)
    e.require(
        again == stage, "Public native source, Preview, CI or archive custody changed"
    )
    return {
        **stage,
        "metadata": metadata,
        "custody": {
            "channel": "actions-native",
            "workflow_run_id": run["id"],
            "metadata_sha256": e.digest(metadata),
        },
        "required_external_checks": [
            "actual_native_full_public_acceptance",
            "exact_preview_and_both_archive_bytes",
            "retained_application_api_and_no_auto_production",
            "fresh_latest_owner_decision",
        ],
    }


def docs_qualification(github, sha, staging_run, delivery_scope):
    """A static Docs handoff grants no application/API deployment authority."""
    e.require(
        delivery_scope == "docs-public",
        "Protected Docs requires conditional owner draft custody",
    )
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


def internal_docs_conditional_qualification(github, sha, run, custody):
    """Owner metadata permits only an external live review, never hosted PASS."""
    e.require(e.PRODUCT == "onesa-ai-platform", "Protected Docs is Platform-only")
    e.require(
        isinstance(custody, dict)
        and custody.keys()
        == {"release_id", "asset_id", "asset_digest", "producer_sha256"},
        "Exact owner draft metadata references required",
    )
    e.trusted_run(run, QUALIFICATION, sha, {"main"}, completed=False)
    pr = current_main(github, sha)
    code, references = e.checked_ci(github, sha)
    e.require(code == "PASS", "Essential exact-main CI required")
    for reference in references:
        e.trusted_run(
            github.run(reference["run_id"]),
            reference["workflow"],
            sha,
            {"main"},
            event="push",
        )
    builds = e.artifacts_for_ci(github, references)
    metadata = internal_docs_preview_metadata(
        github,
        sha,
        custody["release_id"],
        custody["asset_id"],
        custody["asset_digest"],
        custody["producer_sha256"],
    )
    return {
        "schema_version": 1,
        "repository": e.REPOSITORY,
        "candidate_commit": sha,
        "source_sha256": e.source_hash(),
        "target_environment": "Production",
        "pull_request": pr,
        "ci": references,
        "builds": builds,
        "staging": metadata,
        "delivery_scope": "docs-internal",
        "verified_at": run["created_at"],
        "workflow_run_id": run["id"],
        "status": "AWAITING_OWNER_CONDITIONAL_AUTHORIZATION",
        "conditional_authority": INTERNAL_DOCS_CONDITIONAL_AUTHORITY,
        "CODE_VERIFIED": "PASS",
        "STAGING_VERIFIED": "BLOCKED",
        "OPERATIONS_VERIFIED": "BLOCKED",
        "CONTENT_LEGAL_APPROVED": "BLOCKED",
        "security_status": "PASS",
        "approval_provenance": None,
        "scope": "docs-internal",
        "physical_hardware_authorized": False,
        "application_deployment_authorized": False,
        "backend_deployment_authorized": False,
        "production_deployment_authorized": False,
        "retained_application_commit": RETAINED_APPLICATION_COMMIT,
        "retained_backend_commit": RETAINED_APPLICATION_COMMIT,
    }


def internal_docs_live_qualification(github, sha, identifier):
    run = github.run(identifier)
    e.trusted_run(run, QUALIFICATION, sha, {"main"})
    record, origin = github.artifact(run, "free-release-qualification")
    e.require(
        isinstance(record, dict)
        and record.get("workflow_run_id") == run["id"]
        and record.get("delivery_scope") == "docs-internal"
        and e.fresh(record.get("verified_at", ""), datetime.now(timezone.utc)),
        "Fresh exact internal qualification required",
    )
    stage = record.get("staging", {})
    e.require(
        isinstance(stage, dict)
        and isinstance(stage.get("custody"), dict)
        and isinstance(stage.get("metadata"), dict),
        "Pinned owner draft custody required",
    )
    custody = {
        **stage["custody"],
        "producer_sha256": stage["metadata"].get("producer_sha256"),
    }
    refreshed = internal_docs_conditional_qualification(github, sha, run, custody)
    e.require(refreshed == record, "Internal custody, CI or qualification changed")
    return record, origin


def internal_docs_conditional_authorization(
    github, sha, run, qualification_run, fingerprint, review_issue, decision
):
    e.trusted_run(run, WORKFLOW, sha, {"main"}, completed=False)
    current_main(github, sha)
    e.require(decision in {"approve", "revoke"}, "Explicit decision required")
    # This channel reviews metadata custody only. Existing optional owner issues
    # with production-control claims cannot substitute for external live checks.
    e.require(not review_issue, "Conditional Docs uses explicit owner dispatch")
    record = {
        "repository": e.REPOSITORY,
        "candidate_commit": sha,
        "workflow_run_id": run["id"],
        "approved_at": run["created_at"],
        "approver": e.OWNER,
        "decision": decision,
        "target_environment": "Production",
        "delivery_scope": "docs-internal",
        "conditional_authority": INTERNAL_DOCS_CONDITIONAL_AUTHORITY,
        "STAGING_VERIFIED": "BLOCKED",
        "physical_hardware_authorized": False,
        "application_deployment_authorized": False,
        "backend_deployment_authorized": False,
        "production_deployment_authorized": False,
    }
    if decision == "approve":
        qualified, origin = internal_docs_live_qualification(
            github, sha, qualification_run
        )
        e.require(
            e.digest(qualified) == fingerprint,
            "Owner must review exact conditional evidence digest",
        )
        record.update(
            qualification=origin,
            evidence_sha256=fingerprint,
            source_sha256=qualified["source_sha256"],
            owner_review={
                "source": "owner-workflow-dispatch",
                "workflow_run_id": run["id"],
                "candidate_commit": sha,
                "evidence_sha256": fingerprint,
                "approver": e.OWNER,
                "review_scope": "metadata-custody-only; external-live-validation-required",
            },
        )
    return record


def internal_docs_conditional_verify(github, sha, identifier, expected_producer_sha256):
    e.require(
        isinstance(expected_producer_sha256, str)
        and re.fullmatch(r"[a-f0-9]{64}", expected_producer_sha256),
        "Independently held expected protected producer hash required",
    )
    runs = github.runs(WORKFLOW, sha)
    e.require(
        runs and str(runs[0]["id"]) == str(identifier),
        "Only latest owner conditional authorization is usable",
    )
    run = github.run(identifier)
    e.trusted_run(run, WORKFLOW, sha, {"main"})
    approval, origin = github.artifact(run, "free-production-authorization")
    e.require(
        isinstance(approval, dict)
        and approval.get("delivery_scope") == "docs-internal"
        and approval.get("decision") == "approve"
        and e.fresh(approval.get("approved_at", ""), datetime.now(timezone.utc)),
        "Conditional authorization unavailable, revoked or expired",
    )
    refreshed = internal_docs_conditional_authorization(
        github,
        sha,
        run,
        approval["qualification"]["run_id"],
        approval["evidence_sha256"],
        None,
        "approve",
    )
    e.require(refreshed == approval, "Owner conditional approval changed")
    qualified, qualified_origin = internal_docs_live_qualification(
        github, sha, approval["qualification"]["run_id"]
    )
    e.require(
        qualified["staging"]["metadata"]["producer_sha256"] == expected_producer_sha256,
        "Protected producer differs from independently held pin",
    )
    final_runs = github.runs(WORKFLOW, sha)
    e.require(
        final_runs and str(final_runs[0]["id"]) == str(identifier),
        "Owner conditional authorization changed during verification",
    )
    final_run = github.run(identifier)
    e.trusted_run(final_run, WORKFLOW, sha, {"main"})
    final_approval, final_origin = github.artifact(
        final_run, "free-production-authorization"
    )
    e.require(
        final_approval == approval and final_origin == origin,
        "Owner conditional artifact changed during verification",
    )
    current_main(github, sha)
    return {
        "status": "CONDITIONAL_EXTERNAL_HANDOFF",
        "conditional_authority": INTERNAL_DOCS_CONDITIONAL_AUTHORITY,
        "delivery_scope": "docs-internal",
        "STAGING_VERIFIED": "BLOCKED",
        "application_deployment_authorized": False,
        "backend_deployment_authorized": False,
        "production_deployment_authorized": False,
        "approval": approval,
        "artifact": origin,
        "qualification": qualified,
        "qualification_artifact": qualified_origin,
        "staging": qualified["staging"],
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "deployment_triggered": False,
        "git_push_prevented": False,
    }


def public_docs_conditional_qualification(github, sha, run, staging_run, custody):
    """Owner metadata permits only an external live review, never hosted PASS."""
    e.require(e.PRODUCT == "onesa-ai-platform", "Native public Docs is Platform-only")
    e.require(
        isinstance(custody, dict)
        and custody.keys()
        in (
            {"release_id", "asset_id", "asset_digest", "producer_sha256"},
            {"channel", "metadata", "producer_sha256"},
        ),
        "Exact owner native metadata references required",
    )
    e.trusted_run(run, QUALIFICATION, sha, {"main"}, completed=False)
    pr = current_main(github, sha)
    code, references = e.checked_ci(github, sha)
    e.require(code == "PASS", "Essential exact-main CI required")
    for reference in references:
        e.trusted_run(
            github.run(reference["run_id"]),
            reference["workflow"],
            sha,
            {"main"},
            event="push",
        )
    builds = e.artifacts_for_ci(github, references)
    metadata = (
        public_docs_actions_preview_metadata(github, sha, staging_run, custody, run)
        if custody.get("channel") == "actions-native"
        else public_docs_preview_metadata(github, sha, staging_run, custody)
    )
    return {
        "schema_version": 1,
        "repository": e.REPOSITORY,
        "candidate_commit": sha,
        "source_sha256": e.source_hash(),
        "target_environment": "Production",
        "pull_request": pr,
        "ci": references,
        "builds": builds,
        "staging": metadata,
        "delivery_scope": "docs-public",
        "verified_at": run["created_at"],
        "workflow_run_id": run["id"],
        "status": "AWAITING_OWNER_CONDITIONAL_AUTHORIZATION",
        "conditional_authority": INTERNAL_DOCS_CONDITIONAL_AUTHORITY,
        "CODE_VERIFIED": "PASS",
        "STAGING_VERIFIED": "BLOCKED",
        "OPERATIONS_VERIFIED": "BLOCKED",
        "CONTENT_LEGAL_APPROVED": "BLOCKED",
        "security_status": "PASS",
        "approval_provenance": None,
        "scope": "docs-public",
        "physical_hardware_authorized": False,
        "application_deployment_authorized": False,
        "backend_deployment_authorized": False,
        "production_deployment_authorized": False,
        "retained_application_commit": RETAINED_APPLICATION_COMMIT,
        "retained_backend_commit": RETAINED_APPLICATION_COMMIT,
    }


def public_docs_live_qualification(
    github, sha, identifier, *, expected_producer_sha256=None
):
    run = github.run(identifier)
    e.trusted_run(run, QUALIFICATION, sha, {"main"})
    record, origin = github.artifact(run, "free-release-qualification")
    e.require(
        isinstance(record, dict)
        and record.get("workflow_run_id") == run["id"]
        and record.get("delivery_scope") == "docs-public"
        and e.fresh(record.get("verified_at", ""), datetime.now(timezone.utc)),
        "Fresh exact native public qualification required",
    )
    stage = record.get("staging", {})
    e.require(
        isinstance(stage, dict)
        and isinstance(stage.get("custody"), dict)
        and isinstance(stage.get("metadata"), dict),
        "Pinned owner draft custody required",
    )
    if stage["custody"].get("channel") == "actions-native":
        e.require(
            isinstance(expected_producer_sha256, str)
            and re.fullmatch(r"[a-f0-9]{64}", expected_producer_sha256)
            and stage["metadata"].get("producer_sha256") == expected_producer_sha256,
            "Independently held native Actions producer pin required",
        )
        e.require(
            stage["custody"]
            == {
                "channel": "actions-native",
                "workflow_run_id": run["id"],
                "metadata_sha256": e.digest(stage["metadata"]),
            },
            "Exact native Actions artifact custody required",
        )
        custody = {
            "channel": "actions-native",
            "metadata": stage["metadata"],
            "producer_sha256": expected_producer_sha256,
        }
    else:
        custody = {
            **stage["custody"],
            "producer_sha256": stage["metadata"].get("producer_sha256"),
        }
    refreshed = public_docs_conditional_qualification(
        github, sha, run, stage["metadata"]["staging_run_id"], custody
    )
    e.require(refreshed == record, "Public custody, CI or qualification changed")
    return record, origin


def public_docs_conditional_authorization(
    github,
    sha,
    run,
    qualification_run,
    fingerprint,
    review_issue,
    decision,
    *,
    expected_producer_sha256=None,
):
    e.trusted_run(run, WORKFLOW, sha, {"main"}, completed=False)
    current_main(github, sha)
    e.require(decision in {"approve", "revoke"}, "Explicit decision required")
    # This channel reviews metadata custody only. Existing optional owner issues
    # with production-control claims cannot substitute for external live checks.
    e.require(not review_issue, "Conditional Docs uses explicit owner dispatch")
    record = {
        "repository": e.REPOSITORY,
        "candidate_commit": sha,
        "workflow_run_id": run["id"],
        "approved_at": run["created_at"],
        "approver": e.OWNER,
        "decision": decision,
        "target_environment": "Production",
        "delivery_scope": "docs-public",
        "conditional_authority": INTERNAL_DOCS_CONDITIONAL_AUTHORITY,
        "STAGING_VERIFIED": "BLOCKED",
        "physical_hardware_authorized": False,
        "application_deployment_authorized": False,
        "backend_deployment_authorized": False,
        "production_deployment_authorized": False,
    }
    if decision == "approve":
        qualified, origin = public_docs_live_qualification(
            github,
            sha,
            qualification_run,
            expected_producer_sha256=expected_producer_sha256,
        )
        e.require(
            e.digest(qualified) == fingerprint,
            "Owner must review exact conditional evidence digest",
        )
        record.update(
            qualification=origin,
            evidence_sha256=fingerprint,
            source_sha256=qualified["source_sha256"],
            owner_review={
                "source": "owner-workflow-dispatch",
                "workflow_run_id": run["id"],
                "candidate_commit": sha,
                "evidence_sha256": fingerprint,
                "approver": e.OWNER,
                "review_scope": "metadata-custody-only; external-live-validation-required",
            },
        )
    return record


def public_docs_conditional_verify(github, sha, identifier, expected_producer_sha256):
    e.require(
        isinstance(expected_producer_sha256, str)
        and re.fullmatch(r"[a-f0-9]{64}", expected_producer_sha256),
        "Independently held expected native public producer hash required",
    )
    runs = github.runs(WORKFLOW, sha)
    e.require(
        runs and str(runs[0]["id"]) == str(identifier),
        "Only latest owner conditional authorization is usable",
    )
    run = github.run(identifier)
    e.trusted_run(run, WORKFLOW, sha, {"main"})
    approval, origin = github.artifact(run, "free-production-authorization")
    e.require(
        isinstance(approval, dict)
        and approval.get("delivery_scope") == "docs-public"
        and approval.get("decision") == "approve"
        and e.fresh(approval.get("approved_at", ""), datetime.now(timezone.utc)),
        "Conditional authorization unavailable, revoked or expired",
    )
    refreshed = public_docs_conditional_authorization(
        github,
        sha,
        run,
        approval["qualification"]["run_id"],
        approval["evidence_sha256"],
        None,
        "approve",
        expected_producer_sha256=expected_producer_sha256,
    )
    e.require(refreshed == approval, "Owner conditional approval changed")
    qualified, qualified_origin = public_docs_live_qualification(
        github,
        sha,
        approval["qualification"]["run_id"],
        expected_producer_sha256=expected_producer_sha256,
    )
    e.require(
        qualified["staging"]["metadata"]["producer_sha256"] == expected_producer_sha256,
        "Public producer differs from independently held pin",
    )
    final_runs = github.runs(WORKFLOW, sha)
    e.require(
        final_runs and str(final_runs[0]["id"]) == str(identifier),
        "Owner conditional authorization changed during verification",
    )
    final_run = github.run(identifier)
    e.trusted_run(final_run, WORKFLOW, sha, {"main"})
    final_approval, final_origin = github.artifact(
        final_run, "free-production-authorization"
    )
    e.require(
        final_approval == approval and final_origin == origin,
        "Owner conditional artifact changed during verification",
    )
    current_main(github, sha)
    return {
        "status": "CONDITIONAL_EXTERNAL_HANDOFF",
        "conditional_authority": INTERNAL_DOCS_CONDITIONAL_AUTHORITY,
        "delivery_scope": "docs-public",
        "STAGING_VERIFIED": "BLOCKED",
        "application_deployment_authorized": False,
        "backend_deployment_authorized": False,
        "production_deployment_authorized": False,
        "approval": approval,
        "artifact": origin,
        "qualification": qualified,
        "qualification_artifact": qualified_origin,
        "staging": qualified["staging"],
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "deployment_triggered": False,
        "git_push_prevented": False,
    }


def qualification(
    github, sha, run, staging_run, delivery_scope="full", *, metadata_custody=None
):
    if delivery_scope == "docs-public" and metadata_custody is not None:
        return public_docs_conditional_qualification(
            github, sha, run, staging_run, metadata_custody
        )
    if delivery_scope == "docs-internal":
        return internal_docs_conditional_qualification(
            github, sha, run, metadata_custody
        )
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
    if delivery_scope == "docs-internal":
        return internal_docs_live_qualification(github, sha, identifier)
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
    *,
    expected_producer_sha256=None,
):
    if delivery_scope == "docs-public" and expected_producer_sha256 is not None:
        e.require(
            isinstance(expected_producer_sha256, str)
            and re.fullmatch(r"[a-f0-9]{64}", expected_producer_sha256),
            "Explicit independently held native public producer pin required",
        )
        if decision == "approve":
            proposed, _ = public_docs_live_qualification(
                github,
                sha,
                qualification_run,
                expected_producer_sha256=expected_producer_sha256,
            )
            e.require(
                proposed["staging"]["metadata"]["producer_sha256"]
                == expected_producer_sha256,
                "Conditional public producer differs from supplied pin",
            )
        return public_docs_conditional_authorization(
            github,
            sha,
            run,
            qualification_run,
            fingerprint,
            review_issue,
            decision,
            expected_producer_sha256=expected_producer_sha256,
        )
    if delivery_scope == "docs-internal":
        return internal_docs_conditional_authorization(
            github, sha, run, qualification_run, fingerprint, review_issue, decision
        )
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


def verify(
    github, sha, identifier, delivery_scope="full", *, expected_producer_sha256=None
):
    if delivery_scope == "docs-public" and expected_producer_sha256 is not None:
        return public_docs_conditional_verify(
            github, sha, identifier, expected_producer_sha256
        )
    if delivery_scope == "docs-internal":
        return internal_docs_conditional_verify(
            github, sha, identifier, expected_producer_sha256
        )
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
    parser.add_argument("--native-metadata-event")
    parser.add_argument("--metadata-release-id")
    parser.add_argument("--metadata-asset-id")
    parser.add_argument("--metadata-asset-digest")
    parser.add_argument("--metadata-producer-sha256")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    metadata_custody = None
    if args.native_metadata_event:
        e.require(args.mode == "qualify", "Native metadata is qualification-only")
        metadata_custody = public_docs_native_event(
            args.native_metadata_event,
            args.delivery_scope,
            args.metadata_producer_sha256,
            args.staging_run,
        )
    if metadata_custody is not None:
        e.require(
            not any(
                [
                    args.metadata_release_id,
                    args.metadata_asset_id,
                    args.metadata_asset_digest,
                ]
            ),
            "Mixed native and draft custody forbidden",
        )
    elif args.mode == "qualify" and (
        args.delivery_scope == "docs-internal"
        or (
            args.delivery_scope == "docs-public"
            and any(
                [
                    args.metadata_release_id,
                    args.metadata_asset_id,
                    args.metadata_asset_digest,
                    args.metadata_producer_sha256,
                ]
            )
        )
    ):
        e.require(
            all(
                isinstance(value, str) and re.fullmatch(r"[0-9]{1,20}", value)
                for value in [args.metadata_release_id, args.metadata_asset_id]
            ),
            "Explicit positive immutable metadata IDs required",
        )
        metadata_custody = {
            "release_id": int(args.metadata_release_id),
            "asset_id": int(args.metadata_asset_id),
            "asset_digest": args.metadata_asset_digest,
            "producer_sha256": args.metadata_producer_sha256,
        }
    else:
        e.require(
            not any(
                [
                    args.metadata_release_id,
                    args.metadata_asset_id,
                    args.metadata_asset_digest,
                ]
            )
            and (
                not args.metadata_producer_sha256
                or (
                    args.mode == "verify"
                    and args.delivery_scope in {"docs-internal", "docs-public"}
                )
                or (args.mode == "authorize" and args.delivery_scope == "docs-public")
            ),
            "Metadata references require explicit Docs conditional qualification or verifier pin",
        )
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
        record = (
            verify(
                github,
                sha,
                args.authorization_run,
                args.delivery_scope,
                expected_producer_sha256=args.metadata_producer_sha256,
            )
            if args.delivery_scope == "docs-internal"
            or (
                args.delivery_scope == "docs-public"
                and args.metadata_producer_sha256 is not None
            )
            else verify(github, sha, args.authorization_run, args.delivery_scope)
        )
    else:
        e.require(
            os.getenv("GITHUB_REF") == "refs/heads/main",
            "Owner dispatch on main required",
        )
        run = github.run(os.environ["GITHUB_RUN_ID"])
        record = (
            qualification(
                github,
                sha,
                run,
                args.staging_run,
                args.delivery_scope,
                metadata_custody=metadata_custody,
            )
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
                expected_producer_sha256=args.metadata_producer_sha256
                if args.delivery_scope == "docs-public"
                else None,
            )
        )
    e.save(record, args.output)
    print("Evidence SHA256:", e.digest(record))


if __name__ == "__main__":
    try:
        main()
    except (e.Rejected, KeyError, TypeError, ValueError) as error:
        raise SystemExit("BLOCKED: " + str(error)) from None
