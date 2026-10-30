"""Retain the existing Actions conditional handoff inside the external boundary.

Only genuine API metadata and digest-checked Actions ZIPs are consumed. Conditional
records remain explicitly BLOCKED for hosted acceptance and deployment authority;
the separately commissioned native observer and owner store supply those gates.
"""

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import oracle_owner as owner

FILES = frozenset(
    {
        "scripts/release/free_gate.py",
        "scripts/release/evidence.py",
        "scripts/release/qualify.py",
    }
)
ROOT = Path("/var/lib/onesa/release-verification/ai-docs-internal")


def checked_checkout(store, binding):
    path = ROOT / "checkouts" / binding["candidate_commit"] / "onesa-ai-platform"
    owner.private(path, directory=True)
    tool = store.policy["toolchain"]
    owner.require(
        tool["conditional_source_pins"].keys() == FILES,
        "CLOSED_CONDITIONAL_VERIFIER_SOURCE_REQUIRED",
    )
    for name, pin in tool["conditional_source_pins"].items():
        owner.private(path / name)
        owner.require(
            owner.file_digest(path / name) == pin,
            "EXTERNAL_CONDITIONAL_VERIFIER_SOURCE_CHANGED",
        )
    environment = {
        "PATH": "/usr/bin:/bin",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }
    for command, expected in [
        (["rev-parse", "HEAD"], binding["candidate_commit"].encode()),
        (["rev-parse", "HEAD^{tree}"], binding["source_tree"].encode()),
        (["status", "--porcelain", "--untracked-files=all"], b""),
    ]:
        result = subprocess.run(
            ["/usr/bin/git", *command],
            cwd=path,
            env=environment,
            capture_output=True,
            timeout=15,
            check=False,
        )
        owner.require(
            result.returncode == 0 and result.stdout.strip() == expected,
            "EXACT_CLEAN_EXTERNAL_CONDITIONAL_CHECKOUT_REQUIRED",
        )
    return path


def load(store, binding):
    checkout = checked_checkout(store, binding)
    previous = sys.modules.get("evidence")
    path = checkout / "scripts/release/evidence.py"
    spec = importlib.util.spec_from_file_location("evidence", path)
    evidence = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evidence)
    owner.require(
        evidence.ROOT == checkout
        and evidence.REPOSITORY == binding["repository"]
        and evidence.PRODUCT == "onesa-ai-platform",
        "EXACT_EXISTING_CONDITIONAL_VERIFIER_PRODUCT_REQUIRED",
    )
    try:
        sys.modules["evidence"] = evidence
        spec = importlib.util.spec_from_file_location(
            "commissioned_internal_docs_conditional",
            checkout / "scripts/release/free_gate.py",
        )
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
    finally:
        if previous is None:
            sys.modules.pop("evidence", None)
        else:
            sys.modules["evidence"] = previous

    class GitHub(evidence.GitHub):
        def api(self, path, pages=False, binary=False):
            owner.require(
                isinstance(path, str)
                and path.startswith("repos/" + binding["repository"] + "/")
                and ".." not in path
                and "://" not in path,
                "FIXED_REPOSITORY_CONDITIONAL_READS_ONLY",
            )
            if binary:
                match = re.fullmatch(
                    "repos/"
                    + re.escape(binding["repository"])
                    + r"/actions/artifacts/([1-9][0-9]*)/zip",
                    path,
                )
                owner.require(
                    match and not pages, "ONLY_GENUINE_ACTIONS_ZIP_CUSTODY_ALLOWED"
                )
                metadata = store.github.api(path.removesuffix("/zip"))
                artifact = ROOT / "conditional-artifacts" / (match[1] + ".zip")
                owner.private(artifact)
                owner.require(
                    not metadata["expired"]
                    and 0 < artifact.stat().st_size <= 1024 * 1024
                    and metadata["digest"] == "sha256:" + owner.file_digest(artifact),
                    "GENUINE_CONDITIONAL_ARTIFACT_BYTES_REQUIRED",
                )
                return artifact.read_bytes()
            if not pages:
                return store.github.api(path)
            owner.require(
                "page=" not in path.replace("per_page=", ""),
                "READER_OWNS_COMPLETE_PAGINATION",
            )
            result = []
            for page in range(1, 11):
                value = store.github.api(
                    path + ("&" if "?" in path else "?") + "page=" + str(page)
                )
                result.append(value)
                if isinstance(value, list):
                    rows = value
                else:
                    keys = set(value) & {"workflow_runs", "jobs", "artifacts"}
                    owner.require(len(keys) == 1, "KNOWN_COMPLETE_GITHUB_LIST_REQUIRED")
                    rows = value[next(iter(keys))]
                owner.require(
                    isinstance(rows, list) and len(rows) <= 100,
                    "BOUNDED_CONDITIONAL_API_LIST_REQUIRED",
                )
                if len(rows) < 100:
                    return result
            raise owner.Rejected("CONDITIONAL_API_LIST_INCOMPLETE")

    return gate, GitHub()


def verify(store, binding, authorization_run, expected_metadata):
    owner.require(
        type(authorization_run) is int and authorization_run > 0,
        "GENUINE_CONDITIONAL_ACTIONS_RUN_REQUIRED",
    )
    gate, github = load(store, binding)
    try:
        value = gate.internal_docs_conditional_verify(
            github,
            binding["candidate_commit"],
            authorization_run,
            store.policy["toolchain"]["native_producer_sha256"],
        )
    except (gate.e.Rejected, OSError, ValueError, KeyError, TypeError):
        raise owner.Rejected("GENUINE_CURRENT_CONDITIONAL_HANDOFF_FAILED") from None
    owner.require(
        value["status"] == "CONDITIONAL_EXTERNAL_HANDOFF"
        and value["delivery_scope"] == "docs-internal"
        and value["STAGING_VERIFIED"] == "BLOCKED"
        and all(
            value[key] is False
            for key in [
                "application_deployment_authorized",
                "backend_deployment_authorized",
                "production_deployment_authorized",
                "deployment_triggered",
            ]
        )
        and value["staging"]["metadata"] == expected_metadata,
        "CONDITIONAL_HANDOFF_MUST_MATCH_ACTUAL_PRIVATE_NATIVE_OBSERVATION",
    )
    return {
        "authorization_run_id": authorization_run,
        "qualification_run_id": value["qualification"]["workflow_run_id"],
        "authorization_artifact": value["artifact"],
        "qualification_artifact": value["qualification_artifact"],
        "metadata_sha256": owner.digest(expected_metadata),
        "verified_at": value["verified_at"],
        "conditional_authority": value["conditional_authority"],
        "production_deployment_authorized": False,
    }


METADATA = "protected-docs-conditional-metadata"
HANDOFF = "protected-docs-conditional-handoff"


def exported(store, context_id):
    context = store.get(context_id, "context")["record"]
    rows = store.db.execute(
        "SELECT id FROM records WHERE kind=? AND parent=?", (METADATA, context_id)
    ).fetchall()
    owner.require(len(rows) == 1, "EXACT_SIGNED_PRIVATE_METADATA_EXPORT_REQUIRED")
    return store.get(rows[0][0], METADATA, context["binding"])["record"]


def export(store, context_id):
    import oracle_docs_internal_runner as docs
    import oracle_docs_native as native

    context = store.get(context_id, "context")["record"]
    binding = context["binding"]
    docs.scoped(store, binding)
    observed = native.staging_observation(store, context_id)
    payload = observed["details"]["native_payload"]
    evidence = payload["evidence"]
    # Validation above independently compares the entire signed observation with
    # live provider/source/artifact/Access and every mandatory native UI check.
    prepared = docs.prepare(store, binding)
    value = docs.plan(store, binding)
    gate, github = load(store, binding)
    code, ci = gate.e.checked_ci(github, binding["candidate_commit"])
    owner.require(code == "PASS", "CURRENT_PRIVATE_CONDITIONAL_CI_REQUIRED")
    actual_ci = [item for item in ci if item["workflow"] == gate.e.POLICY["ci"]]
    owner.require(len(actual_ci) == 1, "ONE_CURRENT_PRIVATE_CI_RUN_REQUIRED")
    preview = evidence["provider"]
    accepted = evidence["acceptance"]
    metadata = {
        "schema_version": 2,
        "kind": "protected-docs-preview-qualification",
        "repository": binding["repository"],
        "candidate_commit": binding["candidate_commit"],
        "source_sha256": gate._internal_docs_local_source(binding["candidate_commit"]),
        "producer_sha256": store.policy["toolchain"]["native_producer_sha256"],
        "ci_run_id": actual_ci[0]["run_id"],
        "verified_at": payload["observed_at"],
        "delivery_scope": "docs-internal",
        "staging": {
            "project": "onesa-engineering-docs",
            "environment": "preview",
            "deployment_id": preview["deployment_id"],
            "source_commit": binding["candidate_commit"],
            "origin": preview["immutable_origin"],
        },
        "private_artifacts": {
            "staging_tree_sha256": prepared["artifacts"]["staging"][
                "file_manifest_sha256"
            ],
            "staging_archive_sha256": prepared["artifacts"]["staging"][
                "archive_sha256"
            ],
            "production_tree_sha256": prepared["artifacts"]["production"][
                "file_manifest_sha256"
            ],
            "production_archive_sha256": prepared["artifacts"]["production"][
                "archive_sha256"
            ],
        },
        "access_configuration_sha256": owner.digest(value["provider"]),
        "counts": {
            "source_provenance_checks": 1,
            "accessibility_views": len(accepted["accessibility"]),
            "layout_views": len(accepted["layouts"]),
            "architecture_topics": len(accepted["architecture"]),
            "engineering_chapters": len(accepted["chapters"]),
            "onboarding_days": len(accepted["learning_days"]),
            "application_navigation_views": len(accepted["application_navigation"]),
            "identity_icons": len(accepted["icons"]),
            "pdfs": accepted["manuals"],
            "diagrams": gate._internal_docs_diagram_count(),
            "authentication_policy_checks": 1,
            "blocking_accessibility": 0,
            "unexpected_browser_errors": len(accepted["javascript_errors"]),
            "unauthenticated_denials": len(accepted["anonymous_denials"]),
            "verified_asset_responses": len(accepted["asset_security"]),
        },
        "application_deployment_authorized": False,
        "backend_deployment_authorized": False,
        "production_deployment_authorized": False,
    }
    gate._internal_docs_metadata(
        metadata,
        binding["candidate_commit"],
        store.policy["toolchain"]["native_producer_sha256"],
        ci,
        metadata["source_sha256"],
        store.clock(),
    )
    with store.transaction():
        rows = store.db.execute(
            "SELECT id FROM records WHERE kind=? AND parent=?", (METADATA, context_id)
        ).fetchall()
        owner.require(len(rows) <= 1, "DUPLICATE_PRIVATE_METADATA_EXPORTS_REFUSED")
        if rows:
            result = store.get(rows[0][0], METADATA, binding)
            owner.require(
                result["record"]["details"]["metadata"] == metadata,
                "PRIVATE_METADATA_ALREADY_EXPORTED_INSPECT_ONLY",
            )
            return result
        return store.put(
            METADATA,
            binding,
            {
                "native_observation_id": observed["id"],
                "metadata": metadata,
                "production_deployment_authorized": False,
            },
            parent=context_id,
        )


def accept(store, context_id, authorization_run):
    import oracle_docs_internal_runner as docs
    import oracle_docs_native as native

    record = exported(store, context_id)
    docs.scoped(store, record["binding"])
    current = native.staging_observation(store, context_id)
    owner.require(
        current["id"] == record["details"]["native_observation_id"],
        "PRIVATE_NATIVE_OBSERVATION_CHANGED_AFTER_EXPORT",
    )
    result = verify(
        store, record["binding"], authorization_run, record["details"]["metadata"]
    )
    with store.transaction():
        rows = store.db.execute(
            "SELECT id FROM records WHERE kind=? AND parent=?", (HANDOFF, context_id)
        ).fetchall()
        owner.require(
            not rows, "PRIVATE_CONDITIONAL_HANDOFF_ALREADY_IMPORTED_INSPECT_ONLY"
        )
        return store.put(
            HANDOFF,
            record["binding"],
            {
                "conditional": result,
                "metadata_record_id": record["id"],
                "production_deployment_authorized": False,
            },
            parent=context_id,
        )


def current(store, binding, context_id):
    metadata = exported(store, context_id)
    owner.require(metadata["binding"] == binding, "PRIVATE_CONDITIONAL_SOURCE_CHANGED")
    rows = store.db.execute(
        "SELECT id FROM records WHERE kind=? AND parent=?", (HANDOFF, context_id)
    ).fetchall()
    owner.require(
        len(rows) == 1, "CURRENT_GENUINE_PRIVATE_CONDITIONAL_HANDOFF_REQUIRED"
    )
    handoff = store.get(rows[0][0], HANDOFF, binding)["record"]
    owner.require(
        handoff["details"]["metadata_record_id"] == metadata["id"],
        "PRIVATE_CONDITIONAL_METADATA_LINK_CHANGED",
    )
    return verify(
        store,
        binding,
        handoff["details"]["conditional"]["authorization_run_id"],
        metadata["details"]["metadata"],
    )


def inspect(store, context_id):
    """Recover retained IDs and metadata without issuing or consuming anything."""
    import oracle_docs_internal_runner as docs

    context = store.get(context_id, "context")["record"]
    binding = context["binding"]
    docs.scoped(store, binding)
    result = {
        "state": "PRIVATE_CONDITIONAL_INSPECTION_NOT_AUTHORIZATION",
        "context_id": context_id,
        "metadata_record_id": None,
        "handoff_record_id": None,
        "metadata": None,
        "conditional": None,
        "provider_writes": 0,
        "production_deployment_authorized": False,
    }
    rows = store.db.execute(
        "SELECT id FROM records WHERE kind=? AND parent=?", (METADATA, context_id)
    ).fetchall()
    owner.require(len(rows) <= 1, "DUPLICATE_PRIVATE_METADATA_EXPORTS_REFUSED")
    if rows:
        metadata = exported(store, context_id)
        result.update(
            metadata_record_id=metadata["id"], metadata=metadata["details"]["metadata"]
        )
    handoffs = store.db.execute(
        "SELECT id FROM records WHERE kind=? AND parent=?", (HANDOFF, context_id)
    ).fetchall()
    owner.require(
        len(handoffs) <= 1 and (not handoffs or rows),
        "EXACT_PRIVATE_CONDITIONAL_METADATA_LINK_REQUIRED",
    )
    if handoffs:
        result.update(
            handoff_record_id=handoffs[0][0],
            conditional=current(store, binding, context_id),
        )
    return result
