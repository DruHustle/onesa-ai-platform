"""Canonical protected Docs metadata custody, with no publication capability.

The owner dispatch records sanitized counts/hashes and a separate reviewed
approve/revoke decision. The external commissioned verifier still proves private
bytes, native access and current release authority. Actions never receives those
bytes or a signing/deployment credential.
"""

import argparse
import base64
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
from datetime import datetime, timedelta, timezone
from pathlib import Path

import oracle_owner as owner

WORKFLOW = "onesa-protected-docs-metadata.yml"
WORKFLOW_PATH = ".github/workflows/" + WORKFLOW
ARTIFACT = "onesa-protected-docs-metadata"
JOB = "Protected Docs metadata custody"
STEP = "Validate source-bound metadata without publication authority"
UPLOAD = "Retain count and hash metadata only"
MAX_ARCHIVE = 1024**2
MAX_RECORD = 64 * 1024
PREFIX = "repos/" + owner.CONSOLIDATED_REPOSITORY + "/"


def source_identity(source):
    owner.require(
        isinstance(source, dict) and set(source) == owner.AI_SOURCE_FIELDS,
        "EXACT_CANONICAL_PROTECTED_SOURCE_REQUIRED",
    )
    return owner.docs_operational_source({**source, "component": "docs-internal"})


def stamp(value):
    owner.require(isinstance(value, str), "CANONICAL_METADATA_TIMESTAMP_REQUIRED")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    owner.require(result.utcoffset() == timedelta(), "CANONICAL_METADATA_UTC_REQUIRED")
    return result


def actual_run(github, source, identifier, *, completed=True):
    source_identity(source)
    owner.require(
        type(identifier) is int and identifier > 0, "ACTUAL_METADATA_RUN_REQUIRED"
    )
    value = github.api(PREFIX + "actions/runs/" + str(identifier))
    owner.require(
        value["id"] == identifier
        and all(
            type(value[k].get("id")) is int
            and value[k]["id"] == source["repository_id"]
            and value[k]["full_name"] == source["repository"]
            for k in ("repository", "head_repository")
        )
        and value["head_sha"] == source["candidate_commit"]
        and value["head_branch"] == "main"
        and value["event"] == "workflow_dispatch"
        and value["path"] == WORKFLOW_PATH
        and type(value["run_attempt"]) is int
        and value["run_attempt"] == 1
        and value["actor"]["login"] == value["triggering_actor"]["login"] == owner.OWNER
        and (
            value["status"] == "completed" and value["conclusion"] == "success"
            if completed
            else value["status"] in {"queued", "in_progress"}
            and value["conclusion"] is None
        ),
        "CANONICAL_METADATA_RUN_PROVENANCE_REQUIRED",
    )
    now = datetime.now(timezone.utc)
    owner.require(
        stamp(value["created_at"]) <= stamp(value["updated_at"]) <= now
        and timedelta() <= now - stamp(value["created_at"]) < timedelta(hours=24),
        "CANONICAL_METADATA_RUN_EXPIRED_OR_FUTURE",
    )
    owner.require(
        github.api(PREFIX + "branches/main")["commit"]["sha"]
        == source["candidate_commit"],
        "CANONICAL_METADATA_MAIN_CHANGED",
    )
    if completed:
        jobs = owner.complete_source_listing(
            github.api(
                PREFIX
                + "actions/runs/"
                + str(identifier)
                + "/jobs?filter=latest&per_page=100"
            ),
            "jobs",
        )
        owner.require(len(jobs) == 1, "ONE_COMPLETE_METADATA_JOB_REQUIRED")
        job = jobs[0]
        owner.require(
            job["name"] == JOB
            and job["run_id"] == identifier
            and job["head_sha"] == source["candidate_commit"]
            and job["run_attempt"] == 1
            and job["status"] == "completed"
            and job["conclusion"] == "success",
            "CANONICAL_METADATA_JOB_FAILED_OR_CHANGED",
        )
        steps = job["steps"]
        for name in (
            "Verify hosted execution, visibility and included-allowance policy",
            STEP,
            UPLOAD,
        ):
            selected = [s for s in steps if s.get("name") == name]
            owner.require(
                len(selected) == 1
                and selected[0]["status"] == "completed"
                and selected[0]["conclusion"] == "success",
                "CANONICAL_METADATA_REQUIRED_STEP_FAILED",
            )
        owner.require(
            all(
                s["status"] == "completed" and s["conclusion"] in {"success", "skipped"}
                for s in steps
            ),
            "CANONICAL_METADATA_INCOMPLETE_STEP",
        )
    return value


def latest(github, source):
    rows = owner.complete_source_listing(
        github.api(
            PREFIX
            + "actions/workflows/"
            + WORKFLOW
            + "/runs?head_sha="
            + source["candidate_commit"]
            + "&per_page=100"
        ),
        "workflow_runs",
    )
    rows = [
        r
        for r in rows
        if r.get("head_sha") == source["candidate_commit"]
        and r.get("head_branch") == "main"
        and r.get("event") == "workflow_dispatch"
    ]
    owner.require(rows, "LATEST_METADATA_DECISION_MISSING")
    selected = max(rows, key=lambda r: r["id"])
    owner.require(
        all(
            r["id"] == selected["id"]
            or r["status"] == "completed"
            and stamp(r["updated_at"]) < stamp(selected["created_at"])
            for r in rows
        ),
        "OVERLAPPING_METADATA_ACTIVITY_REQUIRES_FRESH_REVIEW",
    )
    return selected


def artifact(github, source, run, read_archive, gate):
    rows = owner.complete_source_listing(
        github.api(
            PREFIX + "actions/runs/" + str(run["id"]) + "/artifacts?per_page=100"
        ),
        "artifacts",
    )
    owner.require(
        len(rows) == 1 and rows[0]["name"] == ARTIFACT,
        "ONE_SANITIZED_METADATA_ARTIFACT_REQUIRED",
    )
    item = github.api(PREFIX + "actions/artifacts/" + str(rows[0]["id"]))
    origin = {
        "id": run["id"],
        "repository_id": source["repository_id"],
        "head_repository_id": source["repository_id"],
        "head_branch": "main",
        "head_sha": source["candidate_commit"],
    }
    owner.require(
        item["id"] == rows[0]["id"]
        and item["name"] == ARTIFACT
        and item["expired"] is False
        and item["workflow_run"] == origin
        and type(item["size_in_bytes"]) is int
        and 0 < item["size_in_bytes"] <= MAX_ARCHIVE
        and re.fullmatch(r"sha256:[a-f0-9]{64}", item["digest"])
        and all(item[k] == rows[0][k] for k in ("name", "digest", "size_in_bytes")),
        "CANONICAL_METADATA_ARTIFACT_CUSTODY_CHANGED",
    )
    raw = read_archive(item["id"])
    owner.require(
        isinstance(raw, bytes)
        and len(raw) == item["size_in_bytes"]
        and "sha256:" + hashlib.sha256(raw).hexdigest() == item["digest"],
        "CANONICAL_METADATA_ARCHIVE_BYTES_CHANGED",
    )
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        owner.require(len(entries) == 1, "ONE_METADATA_JSON_MEMBER_REQUIRED")
        entry = entries[0]
        owner.require(
            entry.filename == entry.orig_filename == "record.json"
            and not entry.flag_bits & 1
            and entry.compress_type in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
            and stat.S_IFMT(entry.external_attr >> 16) in {0, stat.S_IFREG}
            and 0 < entry.file_size <= MAX_RECORD,
            "METADATA_MEMBER_REFUSED",
        )
        value = gate._internal_docs_json(archive.read(entry))
    return value, {
        "id": item["id"],
        "name": ARTIFACT,
        "digest": item["digest"],
        "run_id": run["id"],
        "record_sha256": owner.digest(value),
    }


def qualify_ci(github, source, archives):
    source_identity(source)
    # The inherited method only reads GitHub source/CI/artifacts. It neither calls
    # owner() nor creates a Store, so this is also safe in credential-free Actions.
    return [owner.GitHub.verify_source(github, source, archives)]


def qualification(github, source, archives, run, metadata, producer, gate):
    ci = qualify_ci(github, source, archives)
    fingerprint = gate._internal_docs_local_source(source["candidate_commit"])
    gate._internal_docs_metadata(
        metadata,
        source["candidate_commit"],
        producer,
        ci,
        fingerprint,
        datetime.now(timezone.utc),
        source=source,
    )
    result = {
        "schema_version": 2,
        "kind": "canonical-protected-docs-qualification",
        "source": source,
        "workflow_run_id": run["id"],
        "verified_at": run["created_at"],
        "ci": ci,
        "metadata": metadata,
        "metadata_sha256": owner.digest(metadata),
        "conditional_authority": gate.INTERNAL_DOCS_CONDITIONAL_AUTHORITY,
        "STAGING_VERIFIED": "BLOCKED",
        "application_deployment_authorized": False,
        "backend_deployment_authorized": False,
        "production_deployment_authorized": False,
    }
    owner.require(
        qualify_ci(github, source, archives) == ci
        and gate._internal_docs_local_source(source["candidate_commit"]) == fingerprint,
        "CANONICAL_METADATA_SOURCE_OR_CI_CHANGED",
    )
    return result


def decision(
    github, source, archives, run, action, qualification_run, digest, read_archive, gate
):
    owner.require(
        action in {"approve", "revoke"}, "EXPLICIT_CONDITIONAL_DECISION_REQUIRED"
    )
    origin = None
    if action == "approve":
        owner.require(
            isinstance(digest, str) and owner.HEX.fullmatch(digest),
            "EXACT_REVIEWED_QUALIFICATION_DIGEST_REQUIRED",
        )
        qrun = actual_run(github, source, qualification_run)
        record, origin = artifact(github, source, qrun, read_archive, gate)
        owner.require(
            owner.digest(record) == digest
            and record.get("source") == source
            and record.get("kind") == "canonical-protected-docs-qualification",
            "REVIEWED_PROTECTED_QUALIFICATION_CHANGED",
        )
        refreshed = qualification(
            github,
            source,
            archives,
            qrun,
            record["metadata"],
            record["metadata"]["producer_sha256"],
            gate,
        )
        owner.require(record == refreshed, "CURRENT_PROTECTED_QUALIFICATION_REQUIRED")
    else:
        owner.require(
            qualification_run is None and digest is None,
            "REVOCATION_CANNOT_BORROW_QUALIFICATION",
        )
    return {
        "schema_version": 2,
        "kind": "canonical-protected-docs-decision",
        "source": source,
        "workflow_run_id": run["id"],
        "approved_at": run["created_at"],
        "decision": action,
        "approver": owner.OWNER,
        "qualification": origin,
        "evidence_sha256": digest,
        "conditional_authority": gate.INTERNAL_DOCS_CONDITIONAL_AUTHORITY,
        "STAGING_VERIFIED": "BLOCKED",
        "application_deployment_authorized": False,
        "backend_deployment_authorized": False,
        "production_deployment_authorized": False,
    }


def verify(
    github,
    source,
    archives,
    identifier,
    expected_metadata,
    producer,
    read_archive,
    gate,
):
    selected = latest(github, source)
    owner.require(
        selected["id"] == identifier, "ONLY_LATEST_METADATA_DECISION_IS_USABLE"
    )
    run = actual_run(github, source, identifier)
    record, origin = artifact(github, source, run, read_archive, gate)
    owner.require(
        record.get("kind") == "canonical-protected-docs-decision"
        and record.get("decision") == "approve"
        and record.get("source") == source,
        "PROTECTED_METADATA_DECISION_MISSING_OR_REVOKED",
    )
    qualified_id = record["qualification"]["run_id"]
    refreshed = decision(
        github,
        source,
        archives,
        run,
        "approve",
        qualified_id,
        record["evidence_sha256"],
        read_archive,
        gate,
    )
    owner.require(refreshed == record, "CANONICAL_METADATA_DECISION_CHANGED")
    qrun = actual_run(github, source, qualified_id)
    qualified, qorigin = artifact(github, source, qrun, read_archive, gate)
    owner.require(
        qualified["metadata"] == expected_metadata
        and expected_metadata["producer_sha256"] == producer,
        "EXTERNAL_PRIVATE_NATIVE_METADATA_OR_PRODUCER_CHANGED",
    )
    owner.require(
        latest(github, source) == selected
        and actual_run(github, source, identifier) == run
        and artifact(github, source, run, read_archive, gate) == (record, origin),
        "CONDITIONAL_METADATA_CHANGED_DURING_READ",
    )
    return {
        "authorization_run_id": identifier,
        "qualification_run_id": qualified_id,
        "authorization_artifact": origin,
        "qualification_artifact": qorigin,
        "metadata_sha256": owner.digest(expected_metadata),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "conditional_authority": gate.INTERNAL_DOCS_CONDITIONAL_AUTHORITY,
        "production_deployment_authorized": False,
    }


def download(identifier, *, limit=MAX_ARCHIVE):
    """Bound the read-only CLI response; credential bytes never enter arguments."""
    owner.require(type(identifier) is int and identifier > 0, "ARTIFACT_ID_REQUIRED")
    process = subprocess.Popen(
        ["gh", "api", PREFIX + "actions/artifacts/" + str(identifier) + "/zip"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    output, deadline = bytearray(), time.monotonic() + 25
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
        while True:
            remaining = deadline - time.monotonic()
            owner.require(remaining > 0, "METADATA_ARCHIVE_READ_TIMEOUT")
            owner.require(selector.select(remaining), "METADATA_ARCHIVE_READ_TIMEOUT")
            chunk = os.read(
                process.stdout.fileno(), min(65536, limit + 1 - len(output))
            )
            if not chunk:
                break
            output.extend(chunk)
            owner.require(len(output) <= limit, "METADATA_ARCHIVE_READ_BOUND")
        owner.require(
            process.wait(timeout=max(0.001, deadline - time.monotonic())) == 0,
            "METADATA_ARCHIVE_READ_FAILED",
        )
        return bytes(output)
    finally:
        selector.close()
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()


def source_archives(github, source):
    rows = owner.complete_source_listing(
        github.api(
            PREFIX
            + "actions/workflows/verify.yml/runs?head_sha="
            + source["candidate_commit"]
            + "&per_page=100"
        ),
        "workflow_runs",
    )
    rows = [
        r
        for r in rows
        if r.get("head_branch") == "main"
        and r.get("head_sha") == source["candidate_commit"]
        and r.get("event") in {"push", "workflow_dispatch"}
    ]
    owner.require(rows, "CANONICAL_SOURCE_CI_REQUIRED")
    run = max(rows, key=lambda r: r["id"])
    artifacts = owner.complete_source_listing(
        github.api(
            PREFIX + "actions/runs/" + str(run["id"]) + "/artifacts?per_page=100"
        ),
        "artifacts",
    )
    result = {}
    for name in owner.CONSOLIDATED_ARTIFACTS["platform"]:
        selected = [a for a in artifacts if a.get("name") == name]
        owner.require(
            len(selected) == 1
            and selected[0]["expired"] is False
            and type(selected[0]["size_in_bytes"]) is int
            and 0 < selected[0]["size_in_bytes"] <= owner.SOURCE_ARCHIVE_LIMIT,
            "CANONICAL_SOURCE_ARCHIVE_MISSING",
        )
        result[name] = base64.b64encode(
            download(selected[0]["id"], limit=owner.SOURCE_ARCHIVE_LIMIT)
        ).decode()
    # Exact metadata/digest/archive/source checks follow before any output.
    qualify_ci(github, source, result)
    return result


def action_source(environment, gate):
    owner.require(
        environment.get("GITHUB_ACTIONS") == "true"
        and environment.get("RUNNER_ENVIRONMENT") == "github-hosted"
        and environment.get("RUNNER_OS") == "Linux"
        and environment.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
        and environment.get("GITHUB_REPOSITORY") == owner.CONSOLIDATED_REPOSITORY
        and environment.get("GITHUB_REPOSITORY_ID")
        == str(owner.CONSOLIDATED_REPOSITORY_ID)
        and environment.get("GITHUB_REF") == "refs/heads/main"
        and environment.get("GITHUB_RUN_ATTEMPT") == "1"
        and environment.get("GITHUB_ACTOR")
        == environment.get("GITHUB_TRIGGERING_ACTOR")
        == owner.OWNER,
        "FIXED_HOSTED_OWNER_MAIN_METADATA_CONTEXT_REQUIRED",
    )
    sha = environment.get("GITHUB_SHA", "")
    owner.require(
        re.fullmatch(r"[a-f0-9]{40}", sha)
        and environment.get("GITHUB_WORKFLOW_SHA") == sha
        and environment.get("GITHUB_WORKFLOW_REF")
        == owner.CONSOLIDATED_REPOSITORY + "/" + WORKFLOW_PATH + "@refs/heads/main",
        "CANONICAL_METADATA_WORKFLOW_SOURCE_CHANGED",
    )
    gate._internal_docs_local_source(sha)

    def git(value):
        result = subprocess.run(
            ["git", "rev-parse", value],
            cwd=gate.e.ROOT,
            capture_output=True,
            timeout=10,
            check=False,
        )
        owner.require(result.returncode == 0, "CANONICAL_METADATA_TREE_UNAVAILABLE")
        return result.stdout.decode().strip()

    return source_identity(
        {
            "schema_version": 2,
            "repository": owner.CONSOLIDATED_REPOSITORY,
            "repository_id": owner.CONSOLIDATED_REPOSITORY_ID,
            "product": "platform",
            "source_path": "onesa-ai-platform",
            "candidate_commit": sha,
            "source_tree": git("HEAD^{tree}"),
            "product_source_tree": git("HEAD:onesa-ai-platform"),
            "branch": "main",
        }
    )


def main():
    import free_gate as gate

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = action_source(os.environ, gate)
    identifier = os.environ.get("GITHUB_RUN_ID", "")
    owner.require(
        re.fullmatch(r"[1-9][0-9]{0,18}", identifier), "ACTUAL_METADATA_RUN_REQUIRED"
    )
    event_path = Path(os.environ["GITHUB_EVENT_PATH"])
    owner.require(
        event_path.stat().st_size <= 1024**2, "BOUNDED_METADATA_EVENT_REQUIRED"
    )
    inputs = gate._internal_docs_json(event_path.read_bytes())["inputs"]
    owner.require(
        isinstance(inputs, dict)
        and set(inputs)
        == {
            "action",
            "native_metadata",
            "producer_sha256",
            "qualification_run",
            "evidence_digest",
        }
        and all(isinstance(v, str) for v in inputs.values()),
        "EXPLICIT_METADATA_INPUTS_REQUIRED",
    )
    github = owner.GitHub(os.environ.get("GH_TOKEN"))
    run = actual_run(github, source, int(identifier), completed=False)
    action = inputs["action"]
    if action == "qualify":
        owner.require(
            not inputs["qualification_run"]
            and not inputs["evidence_digest"]
            and 0 < len(inputs["native_metadata"].encode()) <= 32768
            and owner.HEX.fullmatch(inputs["producer_sha256"]),
            "SANITIZED_PROTECTED_METADATA_ONLY",
        )
        record = qualification(
            github,
            source,
            source_archives(github, source),
            run,
            gate._internal_docs_json(inputs["native_metadata"]),
            inputs["producer_sha256"],
            gate,
        )
    else:
        owner.require(
            action in {"approve", "revoke"}
            and not inputs["native_metadata"]
            and not inputs["producer_sha256"],
            "SEPARATE_METADATA_OWNER_DECISION_REQUIRED",
        )
        qrun = inputs["qualification_run"]
        owner.require(
            not qrun or re.fullmatch(r"[1-9][0-9]{0,18}", qrun),
            "QUALIFICATION_RUN_ID_REQUIRED",
        )
        record = decision(
            github,
            source,
            source_archives(github, source) if action == "approve" else None,
            run,
            action,
            int(qrun) if qrun else None,
            inputs["evidence_digest"] or None,
            download,
            gate,
        )
    raw = owner.canonical(record)
    owner.require(
        len(raw) <= MAX_RECORD
        and args.output.is_absolute()
        and args.output.parent.resolve().is_relative_to(
            Path(os.environ["RUNNER_TEMP"]).resolve()
        ),
        "BOUNDED_RUNNER_METADATA_OUTPUT_REQUIRED",
    )
    args.output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with os.fdopen(
        os.open(
            args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
        ),
        "wb",
    ) as out:
        out.write(raw)
    print(
        json.dumps(
            {
                "status": "CONDITIONAL_METADATA_ONLY",
                "action": action,
                "evidence_sha256": owner.digest(record),
                "production_deployment_authorized": False,
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
        zipfile.BadZipFile,
    ):
        raise SystemExit(
            "Protected Docs metadata refused; no publication authority"
        ) from None
