"""Read explicitly mapped operational documents only for an owner-built private site.

Public builds never open the private bundle. Public Git retains safe reference pages;
the private artifact records the original document revision and exact content hash.
"""

import hashlib
import json
import os
import re
from pathlib import Path

REFERENCES = {
    "docs/engineering/DEPLOYMENT.md": "ai-deployment",
    "docs/engineering/ORACLE_VM_OPERATIONS.md": "oracle-vm-operations",
    "docs/operations/TAILSCALE_ADMINISTRATION.md": "tailscale-administration",
    "docs/operations/INCIDENT_RESPONSE.md": "incident-response",
    "docs/operations/MONITORING.md": "monitoring",
    "docs/operations/RECOVERY.md": "recovery",
    "docs/operations/RUNBOOK.md": "operations-runbook",
    "docs/ecosystem/COMPLETE_ARCHITECTURE.md": "complete-architecture",
    "docs/ecosystem/INFRASTRUCTURE.md": "infrastructure",
    "docs/ecosystem/VISUAL_WORKFLOWS.md": "visual-workflows",
    "docs/ecosystem/PORTAL_PRIVACY_GOVERNANCE.md": "portal-governance",
    "docs/ecosystem/PORTAL_ENGINEERING_DOCS_IDENTITY.md": "portal-engineering-identity",
    "docs/ecosystem/PORTAL_DEPLOYMENT.md": "portal-deployment",
    "docs/ecosystem/PORTAL_WORKER_RUNTIME.md": "portal-worker-runtime",
    "docs/ecosystem/ROBOT_DEPLOYMENT.md": "robot-deployment",
    "docs/ecosystem/ROBOT_AUTOMATED_QUALIFICATION.md": "robot-automated-qualification",
    "docs/ecosystem/ROBOT_STAGING_HOST_SETUP.md": "robot-staging-host-setup",
}
MARKER = re.compile(r"<!-- onesa-protected-source: ([a-z0-9-]+) -->")
MAX_DOCUMENT_BYTES = 512 * 1024


class ProtectedSourceError(ValueError):
    """Fixed safe error text; never include a private path, record or credential."""


def _private_file(path):
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise ProtectedSourceError(
            "Protected document file permissions or identity invalid"
        )
    if path.stat().st_size > MAX_DOCUMENT_BYTES:
        raise ProtectedSourceError("Protected document exceeds its size bound")
    return path.read_bytes()


def _bundle():
    location = os.environ.get("ONESA_INTERNAL_DOCS_SOURCE_ROOT", "")
    if not location:
        if os.environ.get("ONESA_REQUIRE_PROTECTED_SOURCES") == "1":
            raise ProtectedSourceError(
                "Private publication requires its protected source bundle"
            )
        return None
    root = Path(location)
    if (
        not root.is_absolute()
        or not root.is_dir()
        or root.is_symlink()
        or root.stat().st_mode & 0o077
    ):
        raise ProtectedSourceError("Protected document directory identity invalid")
    try:
        manifest = json.loads(_private_file(root / "manifest.json"))
        if manifest["schema_version"] != 1 or not isinstance(
            manifest["documents"], dict
        ):
            raise ValueError
    except (KeyError, TypeError, ValueError, UnicodeError, OSError):
        raise ProtectedSourceError("Protected source manifest invalid") from None
    return root, manifest


def _record(bundle, identifier):
    root, manifest = bundle
    try:
        record = manifest["documents"][identifier]
        if (
            record["file"] != identifier + ".md"
            or not re.fullmatch(r"[a-f0-9]{64}", record["sha256"])
            or not re.fullmatch(r"[a-f0-9]{40}", record["source_revision"])
            or record["repository"]
            not in {"onesa-company-portal", "onesa-ai-platform", "onesa-ai-robot"}
            or record["classification"] != "restricted-operational-document"
        ):
            raise ValueError
        raw = _private_file(root / record["file"])
        if hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise ValueError
        return raw.decode("utf-8"), record
    except (KeyError, TypeError, ValueError, UnicodeError, OSError):
        raise ProtectedSourceError("Protected document provenance invalid") from None


def content(source, root, scope="internal"):
    if scope not in {"internal", "public"}:
        raise ProtectedSourceError("Unknown publication classification")
    raw = source.read_text()
    if scope == "public":
        return raw  # Must not inspect environment, manifest or private files.
    relative = source.relative_to(root).as_posix()
    identifier = REFERENCES.get(relative)
    marker = MARKER.search(raw)
    if not identifier:
        if marker:
            raise ProtectedSourceError("Unmapped protected document reference")
        return raw
    if not marker or marker[1] != identifier:
        raise ProtectedSourceError(
            "Protected document reference differs from approved map"
        )
    bundle = _bundle()
    return _record(bundle, identifier)[0] if bundle else raw


def provenance(scope="internal"):
    if scope == "public":
        return None
    if scope != "internal":
        raise ProtectedSourceError("Unknown publication classification")
    bundle = _bundle()
    if not bundle:
        return None
    documents = {}
    for path, identifier in REFERENCES.items():
        _, record = _record(bundle, identifier)
        documents[path] = {
            key: record[key]
            for key in ["sha256", "repository", "source_revision", "source_path"]
        }
    digest = hashlib.sha256(
        json.dumps(documents, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "schema_version": 1,
        "classification": "internal",
        "documents": documents,
        "bundle_sha256": digest,
        "historical_public_copies_removed": False,
    }


def validate_publication(provenance_record):
    """Packaging a real protected edition must not silently publish reference stubs."""
    try:
        bundle = provenance_record["protected_document_sources"]
        if bundle["schema_version"] != 1 or bundle["classification"] != "internal":
            raise ValueError
        documents = bundle["documents"]
        if set(documents) != set(REFERENCES):
            raise ValueError
        for path, record in documents.items():
            if (
                not re.fullmatch(r"[a-f0-9]{64}", record["sha256"])
                or not re.fullmatch(r"[a-f0-9]{40}", record["source_revision"])
                or record["repository"]
                not in {"onesa-company-portal", "onesa-ai-platform", "onesa-ai-robot"}
                or provenance_record["sources"][path] != record["sha256"]
            ):
                raise ValueError
        digest = hashlib.sha256(
            json.dumps(documents, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if bundle["bundle_sha256"] != digest:
            raise ValueError
        return digest
    except (KeyError, TypeError, ValueError):
        raise ProtectedSourceError(
            "Protected publication requires complete, matching private-document provenance"
        ) from None
