"""Protected Pages component in the existing commissioned Oracle release store.

Private bytes never enter Actions. Genuine conditional Actions metadata remains a
separate prerequisite; it cannot replace source-bound native hosted acceptance.
"""

import hashlib
import json
import os
import re
import sys
import tarfile
from datetime import datetime
from pathlib import Path

sys.path[:0] = [
    str(Path(__file__).resolve().parent.parent),
    str(Path(__file__).resolve().parent),
]
import oracle_ai_runner as source_parser
import oracle_docs_internal_access as access
import oracle_docs_internal_build as builds
import oracle_docs_internal_checks as checks
import oracle_docs_internal_provider as provider
import oracle_docs_native as native
import oracle_docs_runner as common
import oracle_owner as owner

PLAN = Path("/etc/onesa/oracle-ai-docs-internal-release.json")
ROOT = Path("/var/lib/onesa/release-verification/ai-docs-internal")
ORIGIN = "https://docs.engineering.onesa.eu"


def read(path, store):
    return common.read(Path(path), store)


def scoped(store, binding):
    profile = owner.binding_valid(binding, store.policy)
    owner.require(
        binding["repository"] == "DruHustle/onesa-ai-platform"
        and binding["component"] == "docs-internal"
        and set(store.policy["components"])
        == {binding["repository"] + ":docs-internal"}
        and profile["publication_mechanism"]
        == "existing-isolated-owner-cloudflare-pages-cli",
        "ONLY_COMMISSIONED_INDEPENDENT_PROTECTED_DOCS_PROFILE_SUPPORTED",
    )


def plan(store, binding):
    scoped(store, binding)
    value = read(PLAN, store)
    owner.require(
        set(value)
        == {
            "schema_version",
            "verifier_store",
            "binding",
            "source_archive",
            "archives",
            "approved_documents",
            "provider",
            "rollback",
        }
        and type(value["schema_version"]) is int
        and value["schema_version"] == 1
        and value["binding"] == binding
        and value["verifier_store"] == str(store.root)
        and owner.digest(value["approved_documents"])
        == store.policy["toolchain"]["protected_source_bundle_sha256"],
        "EXACT_SEPARATELY_COMMISSIONED_PRIVATE_DOCS_PLAN_REQUIRED",
    )
    expected = value["provider"]
    owner.require(
        expected["account_id"] == store.policy["toolchain"]["cloudflare_account_id"]
        and re.fullmatch("[a-f0-9]{32}", expected["account_id"])
        and expected["project_id"] == store.policy["toolchain"]["docs_project_id"]
        and expected["production_branch"] == "main",
        "EXISTING_PRIVATE_DOCS_ACCOUNT_AND_PROJECT_REQUIRED",
    )
    for environment in ["staging", "production"]:
        owner.require(
            binding["configuration_sha256"][environment]
            == owner.digest(
                {
                    "plan": {
                        key: item for key, item in value.items() if key != "binding"
                    },
                    "environment": environment,
                }
            ),
            "PRIVATE_DOCS_CONFIGURATION_BINDING_CHANGED",
        )
    return value


def plan_binding(store, component):
    owner.require(
        component == "docs-internal", "INDEPENDENT_PRIVATE_DOCS_COMPONENT_REQUIRED"
    )
    binding = read(PLAN, store)["binding"]
    plan(store, binding)
    return binding


def project(store, value):
    observed = provider.snapshot(value["provider"])
    return access.inspect(*observed, value["provider"])


def prepare(store, binding):
    value = plan(store, binding)
    folder = ROOT / "artifacts" / binding["source_tree"]
    source = {
        key: binding[key]
        for key in ["repository", "candidate_commit", "source_tree", "source_sha256"]
    }
    archive = Path(value["source_archive"])
    owner.require(
        archive == folder / "source.tar", "FIXED_PRIVATE_DOCS_SOURCE_ARCHIVE_REQUIRED"
    )
    owner.private(archive)
    owner.require(
        owner.file_digest(archive) == binding["source_sha256"],
        "PRIVATE_DOCS_SOURCE_ARCHIVE_CHANGED",
    )
    _application, files = source_parser.source_inventory(archive, binding)
    with tarfile.open(archive, "r:") as source_tar:
        members = {
            entry.name: entry for entry in source_tar.getmembers() if entry.isfile()
        }
        groups = [
            sorted(
                name
                for name in members
                if name.startswith(prefix)
                and name.endswith(".py")
                and "/" not in name[len(prefix) :]
            )
            for prefix in [
                "onesa-ai-platform-backend/app/",
                "onesa-ai-platform-backend/migrations/versions/",
            ]
        ]
        backend = hashlib.sha256(
            b"".join(
                source_tar.extractfile(members[name]).read()
                for group in groups
                for name in group
            )
        ).hexdigest()
    owner.require(
        set(value["archives"]) == {"staging", "production"},
        "TWO_SEPARATE_PRIVATE_CONTEXT_BUILDS_REQUIRED",
    )
    identities = {}
    for environment, item in value["archives"].items():
        path = Path(item["path"])
        owner.require(
            set(item) == {"path", "sha256"} and path == folder / (environment + ".zip"),
            "FIXED_PRIVATE_OWNER_ARCHIVE_CUSTODY_REQUIRED",
        )
        owner.private(path)
        owner.require(
            0 < path.stat().st_size <= builds.MAX_ARCHIVE
            and owner.file_digest(path) == item["sha256"],
            "PRIVATE_BUILD_ARCHIVE_CHANGED",
        )
        identities[environment] = builds.identity(
            path.read_bytes(),
            source=source,
            environment=environment,
            approved_documents=value["approved_documents"],
            source_files=files,
            backend_code_sha256=backend,
        )
    owner.require(
        binding["build_sha256"] == owner.digest(identities)
        and binding["artifact_digest"]
        == "sha256:" + identities["production"]["file_manifest_sha256"],
        "ACTUAL_PRIVATE_SOURCE_BUILD_AND_ARTIFACT_IDENTITIES_REQUIRED",
    )
    return {
        "custody": "private-owner-build-not-actions",
        "workflow_run_id": 0,
        "source": source,
        "artifacts": identities,
        "production_deployment_authorized": False,
    }


def publication_spec(store, binding, *, production):
    value = plan(store, binding)
    project(store, value)
    prepared = prepare(store, binding)
    environment = "production" if production else "staging"
    return {
        "provider": "cloudflare-pages",
        "project_id": value["provider"]["project_id"],
        "account_id": value["provider"]["account_id"],
        "source": {
            key: binding[key]
            for key in ["repository", "candidate_commit", "source_tree"]
        },
        "artifact": prepared["artifacts"][environment],
        "environment": environment,
        "access_configuration_sha256": owner.digest(value["provider"]),
        "publication_mechanism": "existing-isolated-owner-cloudflare-pages-cli",
    }


def operation_folder(binding, identifier):
    owner.identifier(identifier)
    return ROOT / "artifacts" / binding["source_tree"] / "operations" / identifier


def operation_matches(store, operation_id):
    value = read(PLAN, store)
    rows = provider.deployments(value["provider"])
    matches = [
        row
        for row in rows
        if row.get("deployment_trigger", {})
        .get("metadata", {})
        .get("commit_message", "")
        .startswith("onesa-oracle:" + operation_id + ":")
    ]
    owner.require(len(matches) <= 1, "DUPLICATE_PRIVATE_PUBLICATION_INSPECT_ONLY")
    return matches


def deployment_for(
    store, operation, *, production, require_ready=True, require_canonical=True
):
    binding = operation["binding"]
    value = plan(store, binding)
    spec = publication_spec(store, binding, production=production)
    journal = operation_folder(binding, operation["id"])
    intent = read(journal / "intent.json", store)
    owner.require(
        intent["binding"] == binding
        and intent["operation_id"] == operation["id"]
        and intent["prepared"] == spec
        and type(intent["provider_create_budget"]) is int
        and intent["provider_create_budget"] == 1
        and intent["automatic_retry"] is False,
        "ORIGINAL_DURABLE_PRIVATE_PUBLICATION_REQUIRED",
    )
    rows = operation_matches(store, operation["id"])
    owner.require(
        len(rows) == 1, "PRIVATE_PUBLICATION_OUTCOME_UNCERTAIN_INSPECT_WITHOUT_CREATE"
    )
    identity = rows[0]["id"]
    owner.identifier(identity)
    row = provider.get(
        "/pages/projects/onesa-engineering-docs/deployments/" + identity,
        value["provider"],
    )["result"]
    metadata = row["deployment_trigger"]["metadata"]
    expected_environment = "production" if production else "preview"
    expected_message = (
        "onesa-oracle:"
        + operation["id"]
        + ":"
        + spec["artifact"]["file_manifest_sha256"]
    )
    owner.require(
        row["id"] == identity
        and row["project_id"] == value["provider"]["project_id"]
        and row["environment"] == expected_environment
        and metadata["commit_hash"] == binding["candidate_commit"]
        and metadata["commit_message"] == expected_message
        and metadata["branch"]
        == (
            "main" if production else "onesa-oracle-" + binding["candidate_commit"][:12]
        )
        and (
            not require_ready
            or row["latest_stage"]["name"] == "deploy"
            and row["latest_stage"]["status"] == "success"
        )
        and row["url"]
        == "https://" + identity[:8] + ".onesa-engineering-docs.pages.dev",
        "ACTUAL_PRIVATE_PROVIDER_SOURCE_TARGET_ARTIFACT_OR_STATE_CHANGED",
    )
    created = datetime.fromisoformat(row["created_on"])
    owner.require(
        datetime.fromisoformat(operation["issued_at"])
        <= created
        < datetime.fromisoformat(operation["expires_at"]),
        "PRIVATE_PROVIDER_REQUEST_OUTSIDE_CURRENT_SIGNED_OWNER_INTENT",
    )
    if production and require_canonical:
        current = provider.get(
            "/pages/projects/onesa-engineering-docs", value["provider"]
        )["result"]
        owner.require(
            current["canonical_deployment"]["id"] == identity,
            "PRIVATE_CANONICAL_DEPLOYMENT_MISMATCH",
        )
    return {
        "deployment_id": identity,
        "project_id": value["provider"]["project_id"],
        "account_id": value["provider"]["account_id"],
        "origin": ORIGIN if production else row["url"],
        "immutable_origin": row["url"],
        "source_revision": binding["candidate_commit"],
        "artifact_manifest_sha256": spec["artifact"]["file_manifest_sha256"],
        "asset_count": len(spec["artifact"]["served_asset_paths"]),
        "target": expected_environment,
        "state": row["latest_stage"]["status"],
        "operation_id": operation["id"],
    }


def inspect_preview(store, operation):
    return {
        **deployment_for(store, operation, production=False),
        "binding": operation["binding"],
        "workflow_run_id": 0,
        "environment": "staging",
        "production_deployment_authorized": False,
    }


def inspect_production(store, operation):
    return deployment_for(store, operation, production=True)


def preview_for_binding(store, binding):
    rows = store.db.execute(
        "SELECT id FROM records WHERE kind='documentation-preview-receipt' AND scope=?",
        (binding["repository"] + ":docs-internal",),
    ).fetchall()
    records = [
        store.get(row[0], "documentation-preview-receipt", historical=True)["record"]
        for row in rows
    ]
    records = [row for row in records if row["binding"] == binding]
    owner.require(len(records) == 1, "EXACT_PRIVATE_PREVIEW_RECEIPT_REQUIRED")
    receipt = store.get(records[0]["id"], "documentation-preview-receipt", binding)[
        "record"
    ]
    operation = store.get(receipt["parent"], "documentation-preview-intent", binding)[
        "record"
    ]
    owner.require(
        inspect_preview(store, operation) == receipt["details"]["observation"],
        "PRIVATE_PREVIEW_CHANGED",
    )
    return receipt


def target_for_observation(store, binding, identifier, *, production):
    operation = store.get(
        identifier,
        "deployment-intent" if production else "documentation-preview-intent",
        binding,
    )["record"]
    observed = deployment_for(store, operation, production=production)
    spec = publication_spec(store, binding, production=production)
    preview = (
        observed
        if not production
        else inspect_preview(
            store,
            store.get(
                preview_for_binding(store, binding)["parent"],
                "documentation-preview-intent",
                binding,
            )["record"],
        )
    )
    value = plan(store, binding)
    spec["access"] = {
        "anonymous_origins": [
            ORIGIN,
            "https://onesa-engineering-docs.pages.dev",
            preview["immutable_origin"],
        ],
        "team_origin": value["provider"]["team_origin"],
    }
    if not production:
        spec["rollback"] = value["rollback"]
    return {"provider": observed, "publication": spec}


def preflight(store, binding):
    prepared = prepare(store, binding)
    observed = project(store, plan(store, binding))
    return {
        "state": "PRIVATE_BYTES_AND_EXISTING_ACCESS_PREFLIGHT_NOT_HOSTED_ACCEPTANCE",
        "binding": binding,
        "artifact_digest": binding["artifact_digest"],
        "access_configuration_sha256": owner.digest(observed),
        "private_artifact_custody": prepared["custody"],
        "production_deployment_authorized": False,
    }


def validate_native(store, challenge, payload):
    binding = challenge["binding"]
    prepared = prepare(store, binding)
    environment = challenge["details"]["environment"]
    owner.require(
        environment in {"staging", "production"},
        "EXACT_PRIVATE_NATIVE_ENVIRONMENT_REQUIRED",
    )
    evidence = payload["evidence"]
    owner.require(
        set(evidence)
        == {
            "kind",
            "provider",
            "asset_manifest_sha256",
            "asset_count",
            "acceptance",
            "source_revision",
            "observation_mode",
            "browser",
        },
        "EXACT_SIGNED_PRIVATE_NATIVE_EVIDENCE_REQUIRED",
    )
    if environment == "staging":
        receipt = store.get(
            challenge["details"]["preview_receipt_id"],
            "documentation-preview-receipt",
            binding,
        )["record"]
        operation = store.get(
            receipt["parent"], "documentation-preview-intent", binding
        )["record"]
    else:
        operation = store.get(
            challenge["details"]["operation_id"], "deployment-intent", binding
        )["record"]
    target = target_for_observation(
        store, binding, operation["id"], production=environment == "production"
    )
    observed = target["provider"]
    owner.require(
        evidence["kind"] == "owner-native-protected-docs-observation"
        and evidence["observation_mode"] == "existing-owner-browser-no-profile-export"
        and evidence["source_revision"] == binding["candidate_commit"]
        and evidence["provider"] == observed
        and evidence["asset_manifest_sha256"] == observed["artifact_manifest_sha256"]
        and type(evidence["asset_count"]) is int
        and evidence["asset_count"] == observed["asset_count"],
        "ACTUAL_PRIVATE_NATIVE_SOURCE_PROVIDER_AND_COMPLETE_BYTES_REQUIRED",
    )
    browser = evidence["browser"]
    owner.require(
        set(browser) == {"product", "reported_headless", "connection"}
        and re.fullmatch(r"Chrome/[0-9.]+", browser["product"])
        and browser["reported_headless"] is False
        and browser["connection"] == "existing-owner-native-cdp",
        "COMMISSIONED_HEADED_ENGINEERING_OWNER_BROWSER_REQUIRED",
    )
    artifact = prepared["artifacts"][environment]
    value = plan(store, binding)
    files = builds.archive_files(
        Path(value["archives"][environment]["path"]).read_bytes()
    )
    # Use source-checked static metadata only after its complete artifact identity.
    assets = builds.served_assets(
        Path(value["archives"][environment]["path"]).read_bytes(), artifact
    )
    with tarfile.open(value["source_archive"], "r:") as source_tar:
        registry = builds.read_json(
            source_tar.extractfile(
                "onesa-ai-platform-frontend/packages/onesa-design/onesa-applications.json"
            ).read()
        )
        icons = builds.read_json(
            source_tar.extractfile(
                "onesa-ai-platform-frontend/apps/docs/static/brand/icons/v1/sources.json"
            ).read()
        )
    checks.validate(
        evidence["acceptance"],
        navigation=builds.read_json(files["generated/engineering-navigation.json"]),
        catalog=builds.read_json(files["generated/diagrams.json"]),
        registry=registry,
        icon_manifest=icons,
        assets=[item["route"] for item in assets],
        origins=target["publication"]["access"]["anonymous_origins"],
        team_origin=value["provider"]["team_origin"],
        rollback=target["publication"].get("rollback"),
        require=owner.require,
    )
    owner.require(
        evidence["acceptance"]["environment_context"] == environment
        and evidence["acceptance"]["provenance"]
        == {"revision": binding["candidate_commit"], "classification": "internal"},
        "PRIVATE_NATIVE_AUDIENCE_OR_PROVENANCE_CHANGED",
    )


def create_publication(store, operation, *, production):
    import oracle_docs_internal_publish as publisher

    return publisher.create(store, operation, production=production)


def create_preview(store, operation):
    return create_publication(store, operation, production=False)


def inspect_retained_publications(store):
    import oracle_docs_internal_publish as publisher

    return publisher.inspect_retained(store)


def component_lock():
    import oracle_docs_internal_publish as publisher

    return publisher.component_lock()


def rollback_readiness(store, binding, observed):
    value = plan(store, binding)
    rollback = value["rollback"]
    owner.require(
        set(rollback)
        == {"deployment_id", "source", "index_sha256", "provenance_sha256"},
        "EXACT_PRIVATE_STATIC_ROLLBACK_REQUIRED",
    )
    owner.identifier(rollback["deployment_id"])
    row = provider.get(
        "/pages/projects/onesa-engineering-docs/deployments/"
        + rollback["deployment_id"],
        value["provider"],
    )["result"]
    current = provider.get("/pages/projects/onesa-engineering-docs", value["provider"])[
        "result"
    ]
    owner.require(
        row["project_id"] == value["provider"]["project_id"]
        and row["environment"] == "production"
        and row["latest_stage"]["name"] == "deploy"
        and row["latest_stage"]["status"] == "success"
        and row["deployment_trigger"]["metadata"]["commit_hash"] == rollback["source"]
        and current["canonical_deployment"]["id"] == rollback["deployment_id"],
        "RETAINED_PRIVATE_ROLLBACK_PROVIDER_CHANGED",
    )
    proof = observed["details"]["native_payload"]["evidence"]["acceptance"].get(
        "rollback_readiness"
    )
    owner.require(
        proof
        == {
            **rollback,
            "origin": ORIGIN,
            "private_headers": True,
            "index_and_provenance_read_back": True,
            "classification": "internal",
            "provider_writes": 0,
        },
        "GENUINE_PRIVATE_ROLLBACK_BYTES_NOT_OBSERVED",
    )
    return {
        "mode": "retained-static-provider-and-native-readback-no-database",
        **proof,
        "restore_authorized": False,
    }


def runner(store, phase, binding, context):
    import oracle_docs_internal_conditional as conditional

    owner.require(phase in owner.PHASES, "PRIVATE_DOCS_PHASE_SCOPE_REQUIRED")
    prepared = prepare(store, binding)
    value = plan(store, binding)
    settings = project(store, value)
    details = {
        "binding": binding,
        "environment": "staging" if phase == "staging" else "production",
        "workflow_run_id": 0,
        "artifact_digest": binding["artifact_digest"],
        "private_artifact_custody": prepared["custody"],
        "configuration_preserved": True,
        "database_migrations": 0,
        "new_real_data_processing": False,
        "physical_actuation": False,
        "artifact_kind": "private-static-files-and-reviewed-access-worker-no-application-container",
    }
    if phase in {"staging", "operations"}:
        context_id = common.context_for(store, binding, context)
        observed = native.staging_observation(store, context_id)
        details["conditional"] = conditional.current(store, binding, context_id)
        details["native_observation_id"] = observed["id"]
        details["preview_receipt_id"] = preview_for_binding(store, binding)["id"]
        details["backup_restore"] = rollback_readiness(store, binding, observed)
        details["persistence_scope"] = (
            "private-immutable-static-artifact-and-existing-owner-progress-preservation"
        )
        details["schema_scope"] = "static-documentation-no-schema-or-migration"
        if phase == "operations":
            stats = os.statvfs(store.root)
            owner.require(
                stats.f_bavail * stats.f_frsize >= 64 * 1024**2
                and store.db.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
                "PRIVATE_OWNER_STORE_INTEGRITY_OR_CAPACITY_FAILED",
            )
            details["capacity_scope"] = (
                "existing-private-static-project-no-new-resource"
            )
            details["access_configuration_sha256"] = owner.digest(settings)
    elif phase == "deploy":
        owner.require(
            set(context) == {"operation_id", "authorization_id"},
            "EXACT_PRIVATE_AUTHORIZED_DEPLOYMENT_CONTEXT_REQUIRED",
        )
        operation = store.get(context["operation_id"], "deployment-intent", binding)[
            "record"
        ]
        owner.require(
            operation["parent"] == context["authorization_id"],
            "PRIVATE_AUTHORIZATION_OPERATION_CHANGED",
        )
        actual = create_publication(store, operation, production=True)
        details.update(
            operation_id=operation["id"],
            deployment_id=actual["deployment_id"],
            actual_provider=actual,
            native_production_acceptance="PENDING",
        )
    else:
        owner.require(
            set(context) == {"operation_id", "read_only"}
            and context["read_only"] is True,
            "READ_ONLY_PRIVATE_PRODUCTION_OBSERVATION_REQUIRED",
        )
        operation = store.get(context["operation_id"], "deployment-intent", binding)[
            "record"
        ]
        authorization = store.get(operation["parent"], "authorization", binding)[
            "record"
        ]
        qualification = store.get(authorization["parent"], "qualification", binding)[
            "record"
        ]
        details["conditional"] = conditional.current(
            store, binding, qualification["parent"]
        )
        latest = store.db.execute(
            "SELECT id FROM records WHERE scope=? AND kind='authorization-attempt' ORDER BY sequence DESC LIMIT 1",
            (binding["repository"] + ":docs-internal",),
        ).fetchone()
        owner.require(
            latest and latest[0] == authorization["details"]["attempt_id"],
            "PRIVATE_PRODUCTION_OWNER_DECISION_SUPERSEDED",
        )
        actual = inspect_production(store, operation)
        observed = native.production_observation(store, operation["id"])
        details.update(
            operation_id=operation["id"],
            deployment_id=actual["deployment_id"],
            actual_provider=actual,
            native_observation_id=observed["id"],
            production_provider_writes=0,
        )
    verified = set(owner.REQUIRED_CHECKS[phase])
    if phase == "production":
        verified.update(owner.REQUIRED_CHECKS["deploy"])
    return {
        **details,
        "observed_at": owner.timestamp().isoformat(),
        "checks": {key: "PASS" for key in verified},
    }


def main():
    owner.require(
        os.geteuid() == 0 and not os.getenv("GITHUB_ACTIONS") and len(sys.argv) == 2,
        "COMMISSIONED_PRIVATE_ROOT_RUNNER_ONLY",
    )
    raw = sys.stdin.buffer.read(128 * 1024 + 1)
    owner.require(0 < len(raw) <= 128 * 1024, "PRIVATE_DOCS_RUNNER_REQUEST_BOUND")
    request = json.loads(raw)
    owner.require(
        set(request) == {"binding", "context", "owner_token"},
        "EXACT_PRIVATE_OWNER_RUNNER_REQUEST_REQUIRED",
    )
    value = read(PLAN, type("PlanCustody", (), {"root": Path("/var/lib/onesa")})())
    store = owner.Store(
        Path(value["verifier_store"]), owner.GitHub(request["owner_token"])
    )
    print(
        json.dumps(runner(store, sys.argv[1], request["binding"], request["context"]))
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 -- never print arbitrary provider or private input data
        raise SystemExit(
            "PRIVATE_DOCS_OWNER_OBSERVATION_FAILED_INSPECT_WITHOUT_RETRY"
        ) from None
