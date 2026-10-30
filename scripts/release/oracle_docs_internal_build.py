"""Private owner-built Docs bytes; never accept Actions as private build custody.

This parser grants no qualification or publication authority. The independently
commissioned owner supplies the reviewed source and protected-document pins.
Private archive bytes and document metadata must never be uploaded to Actions.
"""

import hashlib
import io
import json
import re
import stat
import zipfile
from pathlib import PurePosixPath

import oracle_docs_build as public
import oracle_owner as owner

MAX_ARCHIVE = 128 * 1024**2
MAX_EXPANDED = 256 * 1024**2
MAX_FILE = 16 * 1024**2
CONTEXTS = {
    "staging": "STAGING · Internal Engineering · Authorized access",
    "production": "Internal Engineering · Authorized access",
}
CONTROL_FILES = {"_worker.js", "_routes.json", "_headers", "_redirects"}


def unique(pairs):
    result = {}
    for key, value in pairs:
        owner.require(key not in result, "DUPLICATE_PRIVATE_DOCS_JSON_KEY")
        result[key] = value
    return result


def read_json(raw):
    return json.loads(raw, object_pairs_hook=unique)


def archive_files(raw):
    """Read bounded regular data without extracting or executing a member."""
    owner.require(
        isinstance(raw, bytes) and 0 < len(raw) <= MAX_ARCHIVE,
        "PRIVATE_DOCS_ARCHIVE_BOUND",
    )
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        names = [entry.filename for entry in members]
        owner.require(
            1 <= len(members) <= 20000
            and len(names) == len(set(names))
            and sum(entry.file_size for entry in members) <= MAX_EXPANDED,
            "PRIVATE_DOCS_EXPANSION_OR_DUPLICATE_BOUND",
        )
        files = {}
        for entry in members:
            name = entry.filename
            path = PurePosixPath(name)
            owner.require(
                name == entry.orig_filename
                and name.rstrip("/") == str(path)
                and not path.is_absolute()
                and ".." not in path.parts
                and all(ord(char) >= 32 and ord(char) != 127 for char in name)
                and not any(char in name for char in "\\?#%")
                and 0 < len(name) <= 1024
                and not entry.flag_bits & 1
                and entry.compress_type in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                and stat.S_IFMT(entry.external_attr >> 16)
                in ({0, stat.S_IFDIR} if entry.is_dir() else {0, stat.S_IFREG})
                and (not entry.is_dir() or entry.file_size == 0)
                and entry.file_size <= MAX_FILE,
                "PRIVATE_DOCS_ARCHIVE_MEMBER_REFUSED",
            )
            if not entry.is_dir():
                files[name] = archive.read(entry)
        return files


def protected_provenance(value, approved):
    """Compare original document identities with external owner-held pins."""
    owner.require(
        isinstance(approved, dict)
        and approved
        and type(value["schema_version"]) is int
        and value["schema_version"] == 1
        and value["classification"] == "internal"
        and value["historical_public_copies_removed"] is False
        and value["documents"] == approved
        and value["bundle_sha256"] == owner.digest(approved),
        "EXACT_EXTERNALLY_APPROVED_PRIVATE_DOCUMENTS_REQUIRED",
    )
    for path, row in approved.items():
        owner.require(
            isinstance(path, str)
            and path.startswith("docs/")
            and path.endswith(".md")
            and set(row) == {"sha256", "repository", "source_revision", "source_path"}
            and owner.HEX.fullmatch(row["sha256"])
            and re.fullmatch("[a-f0-9]{40}", row["source_revision"])
            and row["repository"]
            in {"onesa-ai-platform", "onesa-company-portal", "onesa-ai-robot"}
            and isinstance(row["source_path"], str),
            "PRIVATE_DOCUMENT_ORIGINAL_PROVENANCE_REQUIRED",
        )


def identity(
    raw, *, source, environment, approved_documents, source_files, backend_code_sha256
):
    """Derive identity from actual bytes and independently pinned source inputs."""
    owner.require(
        source["repository"] == public.REPOSITORY
        and re.fullmatch("[a-f0-9]{40}", source["candidate_commit"])
        and re.fullmatch("[a-f0-9]{40}", source["source_tree"])
        and owner.HEX.fullmatch(source["source_sha256"])
        and environment in CONTEXTS
        and isinstance(source_files, dict),
        "EXACT_PRIVATE_DOCS_SOURCE_AND_CONTEXT_REQUIRED",
    )
    try:
        files = archive_files(raw)
        owner.require(len(files) >= 100, "COMPLETE_PRIVATE_DOCS_TREE_REQUIRED")
        provenance = read_json(files["generated/provenance.json"])
        owner.require(
            provenance["classification"] == "internal"
            and provenance["revision"] == source["candidate_commit"]
            and type(provenance["policy_schema_version"]) is int
            and provenance["policy_schema_version"] == 1
            and owner.HEX.fullmatch(backend_code_sha256)
            and provenance["code_sha256"] == backend_code_sha256,
            "PRIVATE_BUILD_SOURCE_OR_CLASSIFICATION_CHANGED",
        )
        protected_provenance(
            provenance["protected_document_sources"], approved_documents
        )
        expected = {
            **source_files,
            **{p: v["sha256"] for p, v in approved_documents.items()},
        }
        owner.require(
            isinstance(provenance["sources"], dict)
            and provenance["sources"]
            and set(approved_documents) <= set(provenance["sources"])
            and all(
                expected.get(path) == pin for path, pin in provenance["sources"].items()
            ),
            "PRIVATE_BUILD_INPUTS_DIFFER_FROM_APPROVED_SOURCE",
        )
        page = public.Audience()
        page.feed(files["index.html"].decode("utf-8", errors="strict"))
        owner.require(
            page.depth == 0 and page.labels == [CONTEXTS[environment]],
            "PRIVATE_DOCS_CONTEXT_MISMATCH_NEVER_RELABEL",
        )
        worker = files["_worker.js"]
        owner.require(
            hashlib.sha256(worker).hexdigest()
            == source_files["infra/cloudflare-docs/worker.mjs"]
            and read_json(files["_routes.json"])
            == {"version": 1, "include": ["/*"], "exclude": []}
            and files["robots.txt"] == b"User-agent: *\nDisallow: /\n"
            and not {"_redirects", "_headers"} & files.keys(),
            "REVIEWED_ALL_PATH_ACCESS_WORKER_REQUIRED",
        )
        hashes = {
            path: hashlib.sha256(body).hexdigest() for path, body in files.items()
        }
        return {
            "schema_version": 1,
            "custody": "private-owner-build-not-actions",
            "source": source,
            "environment": environment,
            "archive_sha256": hashlib.sha256(raw).hexdigest(),
            "archive_bytes": len(raw),
            "file_manifest_sha256": owner.digest(hashes),
            "files": hashes,
            "protected_source_bundle_sha256": owner.digest(approved_documents),
            "served_asset_paths": sorted(set(files) - CONTROL_FILES),
            "qualification_or_publication_authorized": False,
        }
    except owner.Rejected:
        raise
    except (KeyError, TypeError, ValueError, UnicodeError, zipfile.BadZipFile) as error:
        raise owner.Rejected("PRIVATE_DOCS_ARCHIVE_INCOMPLETE_OR_INVALID") from error


def served_assets(raw, descriptor):
    """Compare every byte with the root-signed private artifact, without extraction."""
    files = archive_files(raw)
    hashes = {name: hashlib.sha256(body).hexdigest() for name, body in files.items()}
    owner.require(
        descriptor["custody"] == "private-owner-build-not-actions"
        and hashlib.sha256(raw).hexdigest() == descriptor["archive_sha256"]
        and len(raw) == descriptor["archive_bytes"]
        and hashes == descriptor["files"]
        and owner.digest(hashes) == descriptor["file_manifest_sha256"]
        and sorted(set(files) - CONTROL_FILES) == descriptor["served_asset_paths"],
        "EXACT_ROOT_BOUND_PRIVATE_ARTIFACT_REQUIRED",
    )
    mimes = {
        ".html": ["text/html"],
        ".js": ["application/javascript", "text/javascript"],
        ".css": ["text/css"],
        ".json": ["application/json"],
        ".svg": ["image/svg+xml"],
        ".png": ["image/png"],
        ".ico": ["image/x-icon", "image/vnd.microsoft.icon"],
        ".pdf": ["application/pdf"],
        ".txt": ["text/plain"],
        ".mmd": ["text/plain"],
        ".xml": ["application/xml", "text/xml"],
    }
    result, routes = [], set()
    for name in descriptor["served_asset_paths"]:
        route = "/" + name
        if route == "/index.html":
            route = "/"
        elif route.endswith("/index.html"):
            route = route[:-10]
        elif route.endswith(".html"):
            route = route[:-5]
        canonical = route.rstrip("/") or "/"
        owner.require(canonical not in routes, "PRIVATE_ASSET_ROUTE_COLLISION")
        routes.add(canonical)
        result.append(
            {
                "route": route,
                "bytes": len(files[name]),
                "sha256": hashes[name],
                "mimes": mimes.get(
                    PurePosixPath(name).suffix, ["application/octet-stream"]
                ),
            }
        )
    return result
