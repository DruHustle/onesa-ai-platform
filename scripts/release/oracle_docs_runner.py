"""Public Docs driver for the existing Oracle owner store and isolated vendor CLI.

Durable signed intents precede the guarded publication. Native browser observations
are separate source-bound evidence. Caller PASS data never grants authority.
"""

import datetime as dt
import fcntl
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import time
import urllib.parse
import urllib.request
import zipfile
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import oracle_docs_build as builds
import oracle_docs_checks as checks
import oracle_docs_native as native
import oracle_owner as owner

PLAN = Path("/etc/onesa/oracle-ai-docs-release.json")
ROOT = Path("/var/lib/onesa/release-verification/ai-docs")
CLI_AUTH = Path("/etc/onesa/oracle-vercel-cli/auth.json")
ORIGIN = "https://docs.onesa.eu"
SETTINGS = [
    "id",
    "accountId",
    "name",
    "link",
    "framework",
    "rootDirectory",
    "buildCommand",
    "installCommand",
    "outputDirectory",
    "nodeVersion",
    "ssoProtection",
    "passwordProtection",
    "trustedIps",
    "gitForkProtection",
]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def read(path, store):
    owner.private(path, uid=store.root.stat().st_uid)
    owner.require(path.stat().st_size <= 4 * 1024 * 1024, "DOCS_METADATA_SIZE_BOUND")
    return json.loads(path.read_bytes())


def scoped(store, binding):
    owner.binding_valid(binding, store.policy)
    owner.require(
        binding["repository"] == builds.REPOSITORY
        and binding["component"] == "docs-public"
        and store.policy["components"][
            binding["repository"] + ":" + binding["component"]
        ].get("publication_mechanism")
        == "existing-isolated-owner-vercel-cli",
        "ONLY_COMMISSIONED_PUBLIC_DOCS_PROFILE_SUPPORTED",
    )


def target(store):
    tool = store.policy["toolchain"]
    project_id, team_id = tool["docs_project_id"], tool["vercel_team_id"]
    owner.require(
        isinstance(project_id, str)
        and re.fullmatch(r"prj_[A-Za-z0-9]+", project_id)
        and isinstance(team_id, str)
        and re.fullmatch(r"team_[A-Za-z0-9]+", team_id),
        "COMMISSIONED_DOCS_TARGET_REQUIRED",
    )
    return project_id, team_id


def plan(store, binding):
    project_id, team_id = target(store)
    scoped(store, binding)
    value = read(PLAN, store)
    owner.require(
        set(value)
        == {
            "schema_version",
            "verifier_store",
            "binding",
            "build_run_id",
            "archives",
            "source_archive",
            "provider",
            "rollback",
            "vercel_configuration_sha256",
        }
        and type(value["schema_version"]) is int
        and value["schema_version"] == 1
        and value["binding"] == binding
        and value["verifier_store"] == str(store.root),
        "EXACT_DOCS_PLAN_REQUIRED",
    )
    owner.require(
        type(value["build_run_id"]) is int and value["build_run_id"] > 0,
        "GENUINE_DOCS_BUILD_RUN_REQUIRED",
    )
    provider = value["provider"]
    owner.require(
        set(provider)
        == {"project_id", "team_id", "project_settings_sha256", "production_alias"}
        and provider["project_id"] == project_id
        and provider["team_id"] == team_id
        and provider["production_alias"] == ORIGIN
        and owner.HEX.fullmatch(provider["project_settings_sha256"]),
        "EXISTING_DOCS_PROJECT_ONLY",
    )
    for env in ["staging", "production"]:
        owner.require(
            binding["configuration_sha256"][env]
            == owner.digest(
                {
                    "plan": {k: v for k, v in value.items() if k != "binding"},
                    "environment": env,
                }
            ),
            "DOCS_CONFIGURATION_BINDING_CHANGED",
        )
    return value


def plan_binding(store, component):
    owner.require(
        component == "docs-public",
        "PRIVATE_DOCS_REMAINS_SEPARATE_UNSUPPORTED_BY_PUBLIC_ADAPTER",
    )
    binding = read(PLAN, store)["binding"]
    plan(store, binding)
    return binding


def provider_get(store, path):
    project_id, team_id = target(store)
    owner.require(
        path.startswith(
            (
                "/v9/projects/" + project_id,
                "/v6/deployments?",
                "/v13/deployments/",
                "/v4/aliases/docs.onesa.eu",
            )
        )
        and "://" not in path
        and "#" not in path
        and "\\" not in path,
        "READ_ONLY_DOCS_PROVIDER_PATH",
    )
    owner.private(CLI_AUTH)
    auth = json.loads(CLI_AUTH.read_bytes())
    owner.require(
        isinstance(auth.get("token"), str)
        and auth["token"]
        and "\n" not in auth["token"],
        "EXISTING_OWNER_PROVIDER_CUSTODY_REQUIRED",
    )
    expiry = auth.get("expiresAt")
    owner.require(
        expiry is None
        or type(expiry) is int
        and expiry > owner.timestamp().timestamp() + 300,
        "PROVIDER_CUSTODY_EXPIRED_OR_TOO_SHORT",
    )
    url = (
        "https://api.vercel.com"
        + path
        + ("&" if "?" in path else "?")
        + urllib.parse.urlencode({"teamId": team_id})
    )
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + auth["token"],
            "User-Agent": "OnesaOwnerDocsReadOnly/1.0",
        },
    )
    with urllib.request.build_opener(NoRedirect()).open(
        request, timeout=30
    ) as response:
        raw = response.read(4 * 1024 * 1024 + 1)
        owner.require(len(raw) <= 4 * 1024 * 1024, "DOCS_PROVIDER_RESPONSE_BOUND")
        return json.loads(raw)


def project(store, plan_value):
    project_id, team_id = target(store)
    value = provider_get(store, "/v9/projects/" + project_id)
    owner.require(
        value.get("id") == project_id
        and value.get("accountId") == team_id
        and value.get("name") == "onesa-docs"
        and not value.get("link"),
        "EXISTING_SEPARATE_DOCS_PROJECT_REQUIRED",
    )
    alias = provider_get(store, "/v4/aliases/docs.onesa.eu")
    owner.require(
        alias.get("projectId") == project_id,
        "PROJECT_MUST_OWN_THE_EXISTING_CANONICAL_DOCS_ALIAS",
    )
    settings = {key: value.get(key) for key in SETTINGS}
    owner.require(
        owner.digest(settings) == plan_value["provider"]["project_settings_sha256"],
        "DOCS_PROJECT_OR_PROTECTION_CHANGED",
    )
    return settings


def prepare(store, binding):
    value = plan(store, binding)
    source = {k: binding[k] for k in ["repository", "candidate_commit", "source_tree"]}
    folder = (
        ROOT
        / "artifacts"
        / binding["source_tree"]
        / ("build-" + str(value["build_run_id"]))
    )
    archives = {}
    owner.require(
        isinstance(value["archives"], dict) and len(value["archives"]) == 3,
        "THREE_GENUINE_DOCS_ARTIFACTS_REQUIRED",
    )
    for identifier, item in value["archives"].items():
        owner.require(
            re.fullmatch("[1-9][0-9]{0,19}", identifier)
            and set(item) == {"path", "sha256"}
            and item["path"] == str(folder / (identifier + ".zip"))
            and owner.HEX.fullmatch(item["sha256"]),
            "DOCS_ARCHIVE_PATH_OR_PIN",
        )
        p = Path(item["path"])
        owner.private(p, uid=store.root.stat().st_uid)
        owner.require(
            0 < p.stat().st_size <= 128 * 1024**2
            and owner.file_digest(p) == item["sha256"],
            "DOCS_ARCHIVE_BYTES_CHANGED",
        )
        archives[int(identifier)] = p.read_bytes()
    archive = Path(value["source_archive"])
    owner.require(
        archive == ROOT / "artifacts" / binding["source_tree"] / "source.tar",
        "DOCS_SOURCE_ARCHIVE_PATH",
    )
    owner.private(archive, uid=store.root.stat().st_uid)
    owner.require(
        owner.file_digest(archive) == binding["source_sha256"],
        "DOCS_SOURCE_ARCHIVE_CHANGED",
    )
    # This is the same source-checked stdlib Git-tree parser used by the installer.
    import oracle_ai_runner as parser

    _app, files = parser.source_inventory(
        archive, {"source_tree": binding["source_tree"]}
    )
    owner.require(
        files["onesa-ai-platform-frontend/apps/docs/vercel.json"]
        == value["vercel_configuration_sha256"],
        "QUALIFIED_DOCS_HOST_CONFIGURATION_CHANGED",
    )
    result = builds.read_build(
        store.github, source, value["build_run_id"], archives, require_local_checks=True
    )
    owner.require(
        owner.digest(result) == binding["build_sha256"],
        "GENUINE_DOCS_BUILD_EVIDENCE_CHANGED",
    )
    production = next(
        x for x in result["artifacts"] if x["name"] == "onesa-public-docs-production"
    )
    owner.require(
        binding["artifact_digest"] == "sha256:" + production["file_manifest_sha256"],
        "DOCS_PRODUCTION_ARTIFACT_CHANGED",
    )
    return result


def publication_spec(store, binding, *, production):
    project_id, team_id = target(store)
    build = prepare(store, binding)
    value = plan(store, binding)
    project(store, value)
    name = "onesa-public-docs-production" if production else "onesa-public-docs-staging"
    artifact = next(x for x in build["artifacts"] if x["name"] == name)
    return {
        "provider": "vercel",
        "project_id": project_id,
        "team_id": team_id,
        "source": build["source"],
        "actions_build_run_id": build["actions_build_run_id"],
        "artifact": artifact,
        "vercel_configuration_sha256": value["vercel_configuration_sha256"],
        "environment": "production" if production else "staging",
        "cli_image": store.policy["toolchain"]["cli_image"],
        "transport_guard_sha256": store.policy["toolchain"]["transport_guard_sha256"],
    }


def operation_folder(binding, operation_id):
    owner.identifier(operation_id)
    return ROOT / "artifacts" / binding["source_tree"] / "operations" / operation_id


def operation_matches(store, operation_id):
    project_id, _team_id = target(store)
    result = provider_get(
        store,
        "/v6/deployments?"
        + urllib.parse.urlencode({"projectId": project_id, "limit": 100}),
    )
    rows = result["deployments"]
    owner.require(
        isinstance(rows, list) and len(rows) < 100,
        "COMPLETE_BOUNDED_DOCS_PROVIDER_HISTORY_REQUIRED",
    )
    matches = [
        row
        for row in rows
        if row.get("meta", {}).get("onesaOracleOperation") == operation_id
    ]
    owner.require(len(matches) <= 1, "DUPLICATE_DOCS_PROVIDER_OPERATIONS_INSPECT_ONLY")
    return matches


def inspect_retained_publications(store):
    """Resolve prior request outcomes by GET, without running old candidate code.

    A different source/store cannot hide a request whose acknowledgement was lost.
    Terminal provider observations identify outcomes; they grant no qualification,
    authorization or production acceptance to either source.
    """
    project_id, _team_id = target(store)
    journals = sorted((ROOT / "artifacts").glob("*/operations/*/intent.json"))
    owner.require(len(journals) <= 1000, "BOUNDED_DOCS_PUBLICATION_JOURNAL_REQUIRED")
    observations = []
    for path in journals:
        intent = read(path, store)
        spec = intent["prepared"]
        if spec["environment"] != "production":
            continue
        binding = intent["binding"]
        operation_id = intent["operation_id"]
        owner.require(
            path.parent == operation_folder(binding, operation_id)
            and binding["repository"] == builds.REPOSITORY
            and binding["component"] == "docs-public"
            and spec["project_id"] == project_id
            and spec["source"]["candidate_commit"] == binding["candidate_commit"]
            and intent["provider_create_budget"] == 1
            and intent["automatic_retry"] is False,
            "RETAINED_DOCS_REQUEST_SCOPE_CHANGED",
        )
        rows = operation_matches(store, operation_id)
        owner.require(
            len(rows) == 1,
            "PRIOR_DOCS_REQUEST_OUTCOME_UNCERTAIN_INSPECT_WITHOUT_CREATE",
        )
        deployment_id = rows[0].get("uid")
        owner.require(
            isinstance(deployment_id, str)
            and re.fullmatch("dpl_[A-Za-z0-9]+", deployment_id),
            "PRIOR_DOCS_PROVIDER_ID_REQUIRED",
        )
        row = provider_get(store, "/v13/deployments/" + deployment_id)
        meta = row.get("meta", {})
        owner.require(
            row.get("id") == deployment_id
            and row.get("projectId") == project_id
            and row.get("target") == "production"
            and meta.get("onesaOracleOperation") == operation_id
            and meta.get("onesaSourceRevision") == binding["candidate_commit"]
            and meta.get("onesaArtifactManifest")
            == spec["artifact"]["file_manifest_sha256"]
            and row.get("readyState") in {"READY", "ERROR", "CANCELED"},
            "PRIOR_DOCS_REQUEST_NOT_TERMINAL_OR_BINDING_CHANGED",
        )
        observation = {
            "operation_id": operation_id,
            "deployment_id": deployment_id,
            "source_revision": binding["candidate_commit"],
            "state": row["readyState"],
            "provider_writes": 0,
            "production_acceptance_claimed": False,
        }
        observed_path = path.parent / "provider-terminal-inspection.json"
        if not observed_path.exists():
            durable(observed_path, owner.canonical(observation))
        else:
            owner.require(
                read(observed_path, store) == observation,
                "RETAINED_PROVIDER_TERMINAL_OUTCOME_CHANGED",
            )
        observations.append(observation)
    return observations


def deployment_for(
    store, operation, *, production, require_ready=True, require_canonical=True
):
    project_id, team_id = target(store)
    binding = operation["binding"]
    value = plan(store, binding)
    project(store, value)
    expected = publication_spec(store, binding, production=production)
    journal = operation_folder(binding, operation["id"])
    intent = read(journal / "intent.json", store)
    owner.require(
        intent["binding"] == binding
        and intent["operation_id"] == operation["id"]
        and intent["prepared"] == expected,
        "DURABLE_DOCS_REQUEST_BINDING_CHANGED",
    )
    listing = provider_get(
        store,
        "/v6/deployments?"
        + urllib.parse.urlencode({"projectId": project_id, "limit": 100}),
    )
    rows = listing["deployments"]
    owner.require(
        isinstance(rows, list) and len(rows) < 100,
        "BOUNDED_COMPLETE_DOCS_OPERATION_LIST_REQUIRED",
    )
    matches = [
        row
        for row in rows
        if row.get("meta", {}).get("onesaOracleOperation") == operation["id"]
    ]
    owner.require(
        len(matches) == 1, "ACTUAL_SINGLE_DOCS_PROVIDER_OPERATION_REQUIRED_INSPECT_ONLY"
    )
    listed_identifier = matches[0].get("uid")
    owner.require(
        isinstance(listed_identifier, str)
        and re.fullmatch("dpl_[A-Za-z0-9]+", listed_identifier),
        "DOCS_LISTED_DEPLOYMENT_ID_REQUIRED",
    )
    row = provider_get(store, "/v13/deployments/" + listed_identifier)
    meta = row.get("meta", {})
    identifier = row.get("id")
    host = row.get("url", "")
    owner.require(
        isinstance(identifier, str)
        and re.fullmatch("dpl_[A-Za-z0-9]+", identifier)
        and re.fullmatch(r"[a-z0-9-]+\.vercel\.app", host),
        "DOCS_PROVIDER_IDENTITY_OR_ORIGIN",
    )
    owner.require(
        row.get("projectId") == project_id
        and identifier == listed_identifier
        and (
            row.get("readyState") == "READY"
            if require_ready
            else row.get("readyState")
            in {"QUEUED", "INITIALIZING", "BUILDING", "READY", "ERROR", "CANCELED"}
        )
        and row.get("target") == ("production" if production else None)
        and meta.get("onesaSourceRevision") == binding["candidate_commit"]
        and meta.get("onesaOracleOperation") == operation["id"]
        and meta.get("onesaArtifactManifest")
        == expected["artifact"]["file_manifest_sha256"],
        "ACTUAL_DOCS_SOURCE_ARTIFACT_TARGET_OR_CLAIM_CHANGED",
    )
    created = row.get("createdAt", row.get("created"))
    owner.require(
        type(created) is int
        and dt.datetime.fromisoformat(operation["issued_at"])
        <= dt.datetime.fromtimestamp(created / 1000, dt.timezone.utc)
        < dt.datetime.fromisoformat(operation["expires_at"]),
        "PROVIDER_REQUEST_OUTSIDE_CURRENT_OWNER_INTENT",
    )
    if production and require_canonical:
        alias = provider_get(store, "/v4/aliases/docs.onesa.eu")
        owner.require(
            alias.get("projectId") == project_id
            and alias.get("deployment", {}).get("id") == identifier,
            "ACTUAL_CANONICAL_DOCS_ALIAS_MISMATCH",
        )
    return {
        "deployment_id": identifier,
        "project_id": project_id,
        "team_id": team_id,
        "origin": ORIGIN if production else "https://" + host,
        "immutable_origin": "https://" + host,
        "source_revision": binding["candidate_commit"],
        "artifact_manifest_sha256": expected["artifact"]["file_manifest_sha256"],
        "asset_count": expected["artifact"]["files"],
        "target": "production" if production else None,
        "state": row["readyState"],
        "operation_id": operation["id"],
    }


def inspect_preview(store, operation):
    observation = deployment_for(store, operation, production=False)
    return {
        **observation,
        "binding": operation["binding"],
        "workflow_run_id": 0,
        "environment": "staging",
        "production_deployment_authorized": False,
    }


def inspect_production(store, operation):
    return deployment_for(store, operation, production=True)


def target_for_observation(store, binding, operation_id, *, production):
    kind = "deployment-intent" if production else "documentation-preview-intent"
    operation = store.get(operation_id, kind, binding)["record"]
    return {
        "provider": deployment_for(store, operation, production=production),
        "publication": publication_spec(store, binding, production=production),
    }


def preview_for_binding(store, binding):
    rows = store.db.execute(
        "SELECT id FROM records WHERE kind='documentation-preview-receipt' AND scope=?",
        (binding["repository"] + ":" + binding["component"],),
    ).fetchall()
    matches = []
    for row in rows:
        historical = store.get(
            row[0], "documentation-preview-receipt", historical=True
        )["record"]
        if historical["binding"] == binding:
            matches.append(
                store.get(row[0], "documentation-preview-receipt", binding)["record"]
            )
    owner.require(len(matches) == 1, "EXACT_CURRENT_DOCS_PREVIEW_RECEIPT_REQUIRED")
    receipt = matches[0]
    operation = store.get(receipt["parent"], "documentation-preview-intent", binding)[
        "record"
    ]
    owner.require(
        inspect_preview(store, operation) == receipt["details"]["observation"],
        "PREVIEW_PROVIDER_OBSERVATION_CHANGED",
    )
    return receipt


def preflight(store, binding):
    evidence = prepare(store, binding)
    value = plan(store, binding)
    project(store, value)
    return {
        "state": "DOCS_BUILD_AND_PROVIDER_PREFLIGHT_NOT_HOSTED_ACCEPTANCE",
        "binding": binding,
        "actions_build_run_id": evidence["actions_build_run_id"],
        "production_deployment_authorized": False,
    }


def validate_native(store, challenge, payload):
    binding = challenge["binding"]
    build = prepare(store, binding)
    environment = challenge["details"]["environment"]
    evidence = payload["evidence"]
    owner.require(
        environment in {"staging", "production"}
        and isinstance(evidence, dict)
        and set(evidence)
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
        "EXACT_NATIVE_PUBLIC_DOCS_EVIDENCE_REQUIRED",
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
        observed = deployment_for(store, operation, production=False)
    else:
        operation = store.get(
            challenge["details"]["operation_id"], "deployment-intent", binding
        )["record"]
        observed = inspect_production(store, operation)
        owner.require(
            observed == challenge["details"]["provider"],
            "PRODUCTION_CHANGED_AFTER_NATIVE_CHALLENGE",
        )
    owner.require(
        evidence["kind"] == "owner-native-public-docs-observation"
        and evidence["observation_mode"] == "existing-owner-browser-no-profile-export"
        and evidence["source_revision"] == binding["candidate_commit"]
        and evidence["provider"] == observed
        and evidence["asset_manifest_sha256"] == observed["artifact_manifest_sha256"]
        and type(evidence["asset_count"]) is int
        and evidence["asset_count"] == observed["asset_count"],
        "NATIVE_PROVIDER_SOURCE_OR_COMPLETE_ASSET_BYTES_CHANGED",
    )
    browser = evidence["browser"]
    owner.require(
        isinstance(browser, dict)
        and set(browser) == {"product", "reported_headless", "connection"}
        and isinstance(browser["product"], str)
        and re.fullmatch(r"Chrome/[0-9.]+", browser["product"])
        and browser["reported_headless"] is False
        and browser["connection"] == "existing-owner-native-cdp",
        "SOURCE_PINNED_HEADED_NATIVE_BROWSER_REQUIRED",
    )
    contract = builds.source_contract(store.github, binding["candidate_commit"])
    checks.validate(
        evidence["acceptance"],
        contract["registry"],
        contract["icons"],
        require=owner.require,
    )
    owner.require(
        evidence["acceptance"].get("environment_context") == environment
        and evidence["acceptance"].get("result") == "PASS",
        "NATIVE_AUDIENCE_OR_REQUIRED_WORKFLOW_FAILED",
    )
    accepted = evidence["acceptance"]
    owner.require(
        accepted.get("origin") == observed["origin"]
        and accepted.get("provenance")
        == {"revision": binding["candidate_commit"], "classification": "public"}
        and type(accepted.get("links")) is int
        and 0 < accepted["links"] <= 500000
        and accepted.get("diagrams") == 21
        and accepted.get("pdfs") == 11,
        "COMPLETE_NATIVE_DOCS_PROVENANCE_LINKS_DIAGRAMS_AND_PDFS_REQUIRED",
    )
    owner.require(build["local_acceptance"], "GENUINE_LOCAL_DOCS_CHECKS_REQUIRED")


def public_get(origin, path):
    owner.require(
        origin == ORIGIN
        and path
        in {
            "/",
            "/generated/provenance.json",
            "/onboarding",
            "/generated/engineering-navigation.json",
            "/docs/operations/TAILSCALE_ADMINISTRATION",
        },
        "READ_ONLY_PUBLIC_DOCS_BOUNDARY",
    )
    request = urllib.request.Request(
        origin + path,
        headers={
            "User-Agent": "OnesaDocsAnonymousAcceptance/1.0",
            "Cache-Control": "no-cache",
        },
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(
            request, timeout=30
        ) as response:
            raw = response.read(4 * 1024 * 1024 + 1)
            owner.require(len(raw) <= 4 * 1024 * 1024, "PUBLIC_DOCS_RESPONSE_BOUND")
            return response.status, raw
    except urllib.error.HTTPError as error:
        owner.require(
            error.code in {401, 403, 404}, "PUBLIC_DOCS_HTTP_FAILED_NO_REDIRECT"
        )
        return error.code, b""


def rollback_readiness(store, binding):
    project_id, _team_id = target(store)
    value = plan(store, binding)
    rollback = value["rollback"]
    owner.require(
        set(rollback)
        == {"deployment_id", "source", "index_sha256", "provenance_sha256"}
        and re.fullmatch("dpl_[A-Za-z0-9]+", rollback["deployment_id"])
        and re.fullmatch("[a-f0-9]{40}", rollback["source"])
        and all(
            owner.HEX.fullmatch(rollback[k])
            for k in ["index_sha256", "provenance_sha256"]
        ),
        "EXACT_RETAINED_STATIC_ROLLBACK_REQUIRED",
    )
    row = provider_get(store, "/v13/deployments/" + rollback["deployment_id"])
    meta = row.get("meta", {})
    source = (
        meta.get("onesaSourceRevision")
        or meta.get("githubCommitSha")
        or row.get("gitSource", {}).get("sha")
    )
    owner.require(
        row.get("id") == rollback["deployment_id"]
        and row.get("projectId") == project_id
        and row.get("readyState") == "READY"
        and row.get("target") == "production"
        and source == rollback["source"],
        "ACTUAL_RETAINED_DOCS_ROLLBACK_NOT_READY",
    )
    alias = provider_get(store, "/v4/aliases/docs.onesa.eu")
    owner.require(
        alias.get("projectId") == project_id
        and alias.get("deployment", {}).get("id") == rollback["deployment_id"],
        "RETAINED_DOCS_BASELINE_CHANGED_BEFORE_PUBLICATION",
    )
    for path, key in [
        ("/", "index_sha256"),
        ("/generated/provenance.json", "provenance_sha256"),
    ]:
        status, raw = public_get(ORIGIN, path)
        owner.require(
            status == 200 and hashlib.sha256(raw).hexdigest() == rollback[key],
            "RETAINED_STATIC_ARTIFACT_READBACK_FAILED",
        )
        if path.endswith(".json"):
            provenance = json.loads(raw)
            owner.require(
                provenance.get("revision") == rollback["source"]
                and provenance.get("classification") == "public"
                and provenance.get("protected_document_sources") is None,
                "RETAINED_DOCS_PROVENANCE_CHANGED",
            )
    return {
        "mode": "immutable-static-provider-artifact-readback-no-database",
        "deployment_id": rollback["deployment_id"],
        "source_revision": rollback["source"],
        "index_and_provenance_read_back": True,
        "restore_authorized": False,
        "production_alias_changes": 0,
    }


def context_for(store, binding, context):
    if set(context) == {"context_id"}:
        identifier = context["context_id"]
    elif set(context) == {"qualification_id", "owner_decision"}:
        owner.require(
            context["owner_decision"] == "approve", "OWNER_AUTHORIZATION_PHASE_REQUIRED"
        )
        identifier = store.get(context["qualification_id"], "qualification", binding)[
            "record"
        ]["parent"]
    elif set(context) == {"authorization_id", "before_deployment"}:
        owner.require(
            context["before_deployment"] is True, "EXACT_PRE_PUBLICATION_PHASE_REQUIRED"
        )
        authorization = store.get(
            context["authorization_id"], "authorization", binding
        )["record"]
        identifier = store.get(authorization["parent"], "qualification", binding)[
            "record"
        ]["parent"]
    else:
        raise owner.Rejected("EXACT_SIGNED_DOCS_CONTEXT_REQUIRED")
    store.get(identifier, "context", binding)
    return identifier


def runner(store, phase, binding, context):
    owner.require(phase in owner.PHASES, "DOCS_PHASE_SCOPE")
    build = prepare(store, binding)
    value = plan(store, binding)
    settings = project(store, value)
    details = {
        "binding": binding,
        "environment": "staging" if phase == "staging" else "production",
        "workflow_run_id": 0,
        "observed_at": owner.timestamp().isoformat(),
        "actions_build_run_id": build["actions_build_run_id"],
        "artifact_digest": binding["artifact_digest"],
        "configuration_preserved": True,
        "database_migrations": 0,
        "new_real_data_processing": False,
        "physical_actuation": False,
        "artifact_kind": "static-file-manifest-no-container-image",
    }
    if phase in {"staging", "operations"}:
        context_id = context_for(store, binding, context)
        observed = native.staging_observation(store, context_id)
        owner.require(observed["binding"] == binding, "STAGING_NATIVE_SOURCE_CHANGED")
        details.update(
            native_observation_id=observed["id"],
            preview_receipt_id=preview_for_binding(store, binding)["id"],
        )
        if phase == "operations":
            stats = os.statvfs(store.root)
            owner.require(
                stats.f_bavail * stats.f_frsize >= 64 * 1024**2
                and store.db.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
                "OWNER_STORE_INTEGRITY_OR_CAPACITY_FAILED",
            )
            details["backup_restore"] = rollback_readiness(store, binding)
            details["capacity_scope"] = (
                "existing-static-provider-project-no-new-hosted-resource"
            )
            details["project_settings_sha256"] = owner.digest(settings)
        else:
            details["persistence_scope"] = (
                "immutable-static-artifact-and-real-browser-reload-no-application-database"
            )
            details["schema_scope"] = "static-documentation-no-schema-or-migration"
    elif phase == "deploy":
        owner.require(
            set(context) == {"operation_id", "authorization_id"},
            "EXACT_AUTHORIZED_DOCS_DEPLOYMENT_CONTEXT_REQUIRED",
        )
        operation = store.get(context["operation_id"], "deployment-intent", binding)[
            "record"
        ]
        owner.require(
            operation["parent"] == context["authorization_id"],
            "DOCS_AUTHORIZATION_OPERATION_CHANGED",
        )
        actual = create_publication(store, operation, production=True)
        details.update(
            operation_id=operation["id"],
            deployment_id=actual["deployment_id"],
            actual_provider=actual,
            native_production_acceptance="PENDING",
            independent_provider_projects_modified=0,
        )
    else:
        owner.require(
            set(context) == {"operation_id", "read_only"}
            and context["read_only"] is True,
            "READ_ONLY_NATIVE_DOCS_PRODUCTION_OBSERVATION_REQUIRED",
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
        store.get(qualification["parent"], "context", binding)
        latest = store.db.execute(
            "SELECT id FROM records WHERE scope=? AND kind='authorization-attempt' ORDER BY sequence DESC LIMIT 1",
            (binding["repository"] + ":" + binding["component"],),
        ).fetchone()
        owner.require(
            latest and latest[0] == authorization["details"]["attempt_id"],
            "DOCS_PRODUCTION_OWNER_DECISION_SUPERSEDED",
        )
        actual = inspect_production(store, operation)
        observed = native.production_observation(store, operation["id"])
        status, raw = public_get(ORIGIN, "/generated/provenance.json")
        owner.require(
            status == 200
            and json.loads(raw).get("revision") == binding["candidate_commit"],
            "ACTUAL_ANONYMOUS_CANONICAL_DOCS_SOURCE_FAILED",
        )
        for path in [
            "/onboarding",
            "/generated/engineering-navigation.json",
            "/docs/operations/TAILSCALE_ADMINISTRATION",
        ]:
            owner.require(
                public_get(ORIGIN, path)[0] == 404, "PRIVATE_DOCS_BOUNDARY_FAILED"
            )
        details.update(
            operation_id=operation["id"],
            deployment_id=actual["deployment_id"],
            actual_provider=actual,
            native_observation_id=observed["id"],
            production_provider_writes=0,
            independent_provider_projects_modified=0,
        )
    verified = set(owner.REQUIRED_CHECKS[phase])
    if phase == "production":
        verified.update(owner.REQUIRED_CHECKS["deploy"])
    return {**details, "checks": {key: "PASS" for key in verified}}


@contextmanager
def component_lock():
    owner.private(ROOT, directory=True)
    lock = ROOT / "publication.lock"
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def durable(path, raw):
    with os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb"
    ) as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def cli_authentication(store):
    import oracle_ai_frontend as cli
    import oracle_ai_runner as system

    tool = store.policy["toolchain"]
    image = tool["cli_image"]
    owner.require(
        re.fullmatch("sha256:[a-f0-9]{64}", image), "PINNED_EXISTING_CLI_IMAGE_REQUIRED"
    )
    actual = json.loads(system.docker("image", "inspect", image))[0]
    owner.require(
        actual["Id"] == image
        and actual["Architecture"] == "arm64"
        and actual["Config"]["Labels"].get("org.onesa.vercel-cli") == "65.2.0",
        "EXACT_SCANNED_CLI_TOOL_REQUIRED",
    )
    scan = read(Path(tool["cli_image_security_path"]), store)
    system.image_security(scan, image)
    custody = CLI_AUTH.parent
    owner.private(custody, directory=True)
    files = [custody / "auth.json", custody / "config.json"]
    for file in files:
        owner.private(file)
    pins = {str(file): owner.file_digest(file) for file in files}
    auth = read(CLI_AUTH, store)
    expiry = auth.get("expiresAt")
    owner.require(
        expiry is None
        or type(expiry) is int
        and expiry - owner.timestamp().timestamp() >= 3600,
        "EXISTING_OWNER_SESSION_TOO_SHORT_FOR_QUALIFICATION",
    )
    raw = system.command(
        [
            "/usr/bin/docker",
            "run",
            "--rm",
            "--pull=never",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,mode=700,size=256m",
            "--memory",
            "512m",
            "--cpus",
            "1",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "-v",
            str(custody) + ":/private/creds:ro",
            "--entrypoint",
            "node",
            image,
            "-e",
            cli.CLI_BOOTSTRAP,
            "--",
            "/opt/onesa-vercel-tool/node_modules/vercel/dist/index.js",
            "api",
            "/v2/user",
            "-X",
            "GET",
            "--raw",
            "--global-config",
            "/tmp/onesa-vercel-cli",
        ],
        timeout=60,
    )
    owner.require(
        len(raw) <= 131072
        and json.loads(raw)["user"]["username"].lower() == "druhustle",
        "EXISTING_AUTHENTICATED_OWNER_REQUIRED",
    )
    owner.require(
        all(owner.file_digest(Path(path)) == pin for path, pin in pins.items()),
        "OWNER_CUSTODY_CHANGED_DURING_PREFLIGHT",
    )
    return {
        "state": "EXISTING_ISOLATED_OWNER_CLI_AUTHENTICATED_READ_ONLY",
        "cli_image": image,
        "provider_create_requests": 0,
        "credentials_exported": False,
    }


def unpack_static(store, binding, spec, workspace):
    value = plan(store, binding)
    identifier = str(spec["artifact"]["artifact_id"])
    archive = Path(value["archives"][identifier]["path"])
    owner.private(archive)
    raw = archive.read_bytes()
    owner.require(
        hashlib.sha256(raw).hexdigest() == spec["artifact"]["archive_sha256"],
        "PREBUILT_DOCS_ARCHIVE_CHANGED",
    )
    builds.archive_identity(
        raw,
        {
            "id": int(identifier),
            "name": spec["artifact"]["name"],
            "digest": "sha256:" + spec["artifact"]["archive_sha256"],
        },
        binding["candidate_commit"],
    )
    static = workspace / ".vercel/output/static"
    static.mkdir(mode=0o700, parents=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as zipped:
        for item in zipped.infolist():
            if item.is_dir():
                continue
            output = static / item.filename
            output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            durable(output, zipped.read(item))
    with tarfile.open(value["source_archive"], "r:") as source:
        entry = source.getmember("onesa-ai-platform-frontend/apps/docs/vercel.json")
        owner.require(entry.isfile(), "REVIEWED_STATIC_HOST_CONFIGURATION_REQUIRED")
        config = source.extractfile(entry).read()
        owner.require(
            hashlib.sha256(config).hexdigest() == spec["vercel_configuration_sha256"],
            "REVIEWED_STATIC_HOST_CONFIGURATION_CHANGED",
        )
    durable(workspace / "vercel.json", config)
    durable(
        workspace / ".vercel/project.json",
        owner.canonical({"projectId": spec["project_id"], "orgId": spec["team_id"]}),
    )
    routes = []
    if spec["environment"] == "staging":
        routes.append(
            {
                "src": "/(.*)",
                "headers": {"X-Robots-Tag": "noindex, nofollow"},
                "continue": True,
            }
        )
    routes.extend(
        [
            {"handle": "filesystem"},
            {"src": "/((?:[^/]+/)*[^/.]+)", "dest": "/$1.html"},
            {"src": "/.*", "dest": "/404.html", "status": 404},
        ]
    )
    durable(
        workspace / ".vercel/output/config.json",
        owner.canonical({"version": 3, "routes": routes}),
    )
    settings = project(store, value)
    owner.require(
        settings["rootDirectory"] in {None, "", "onesa-ai-platform-frontend/apps/docs"},
        "EXISTING_STATIC_DOCS_PROJECT_ROOT_ONLY",
    )
    if settings["rootDirectory"]:
        (workspace / settings["rootDirectory"]).mkdir(mode=0o700, parents=True)


def create_publication(store, operation, *, production):
    import oracle_ai_frontend as cli

    binding = operation["binding"]
    scoped(store, binding)
    kind = "deployment-intent" if production else "documentation-preview-intent"
    store.get(operation["id"], kind, binding)
    with component_lock():
        if production:
            inspect_retained_publications(store)
        spec = publication_spec(store, binding, production=production)
        folder = operation_folder(binding, operation["id"])
        owner.require(
            not folder.exists(), "DOCS_PUBLICATION_OPERATION_EXISTS_INSPECT_ONLY"
        )
        owner.require(
            not operation_matches(store, operation["id"]),
            "DOCS_PROVIDER_OPERATION_ALREADY_EXISTS_INSPECT_ONLY",
        )
        cli_authentication(store)
        if production:
            authorization = store.get(operation["parent"], "authorization", binding)[
                "record"
            ]
            store.get(authorization["parent"], "qualification", binding)
            latest = store.db.execute(
                "SELECT id FROM records WHERE scope=? AND kind='authorization-attempt' ORDER BY sequence DESC LIMIT 1",
                (binding["repository"] + ":" + binding["component"],),
            ).fetchone()
            owner.require(
                latest and latest[0] == authorization["details"]["attempt_id"],
                "DOCS_OWNER_AUTHORIZATION_SUPERSEDED",
            )
        folder.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        folder.mkdir(mode=0o700)
        workspace = folder / "prebuilt"
        workspace.mkdir(mode=0o700)
        unpack_static(store, binding, spec, workspace)
        transport = folder / "transport"
        transport.mkdir(mode=0o700)
        guard = Path(__file__).with_name("oracle_vercel_transport_guard.cjs")
        owner.private(guard)
        owner.require(
            owner.file_digest(guard) == spec["transport_guard_sha256"],
            "EXACT_ONE_CREATE_TRANSPORT_REQUIRED",
        )
        durable(
            transport / "scope.json",
            owner.canonical(
                {
                    "repository": binding["repository"],
                    "component": "docs-public",
                    "candidate_commit": binding["candidate_commit"],
                    "environment": spec["environment"],
                    "operation_id": operation["id"],
                    "request_budget": 1,
                }
            ),
        )
        durable(
            folder / "intent.json",
            owner.canonical(
                {
                    "binding": binding,
                    "operation_id": operation["id"],
                    "verifier_store": str(store.root),
                    "prepared": spec,
                    "provider_create_budget": 1,
                    "automatic_retry": False,
                    "recorded_at": owner.timestamp().isoformat(),
                }
            ),
        )
        command = [
            "/usr/bin/docker",
            "run",
            "--rm",
            "--pull=never",
            "--name",
            "onesa-docs-publication-" + operation["id"],
            "--read-only",
            "--tmpfs",
            "/tmp:rw,mode=700,size=256m",
            "--memory",
            "512m",
            "--cpus",
            "1",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "-v",
            str(workspace) + ":/workspace:ro",
            "-v",
            str(CLI_AUTH.parent) + ":/private/creds:ro",
            "-v",
            str(guard) + ":/private/guard.cjs:ro",
            "-v",
            str(transport) + ":/private/transport:rw",
            "-e",
            "ONESA_ORACLE_VERIFIER_PRELOAD=1",
            "--entrypoint",
            "node",
            "-w",
            "/workspace",
            spec["cli_image"],
            "-e",
            cli.CLI_BOOTSTRAP,
            "--",
            "--require",
            "/private/guard.cjs",
            "/opt/onesa-vercel-tool/node_modules/vercel/dist/index.js",
            "deploy",
            "--prebuilt",
            "--yes",
            "--no-wait",
            "--json",
            "--global-config",
            "/tmp/onesa-vercel-cli",
            "--project",
            spec["project_id"],
            "--meta",
            "githubCommitRef=" + ("main" if production else "staging"),
            "--meta",
            "githubCommitSha=" + binding["candidate_commit"],
            "--meta",
            "onesaSourceRevision=" + binding["candidate_commit"],
            "--meta",
            "onesaOracleOperation=" + operation["id"],
            "--meta",
            "onesaArtifactManifest=" + spec["artifact"]["file_manifest_sha256"],
            *(["--prod"] if production else ["--target=preview"]),
        ]
        with (
            (folder / "cli.stdout").open("xb") as out,
            (folder / "cli.stderr").open("xb") as err,
        ):
            os.chmod(out.name, 0o600)
            os.chmod(err.name, 0o600)
            try:
                result = subprocess.run(
                    command,
                    stdout=out,
                    stderr=err,
                    timeout=600,
                    check=False,
                    env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                )
                exit_code = result.returncode
            except subprocess.TimeoutExpired:
                exit_code = None
        durable(
            folder / "cli-result.json",
            owner.canonical(
                {
                    "exit_code": exit_code,
                    "automatic_retry": False,
                    "provider_outcome": "REQUIRES_READ_ONLY_RECONCILIATION",
                }
            ),
        )
        deadline = time.monotonic() + 120
        while not operation_matches(store, operation["id"]):
            owner.require(
                time.monotonic() < deadline,
                "DOCS_PROVIDER_OUTCOME_UNCERTAIN_INSPECT_WITHOUT_CREATE",
            )
            time.sleep(2)
        owner.require(
            (transport / "create-request.json").is_file(),
            "ACTUAL_DOCS_CREATE_TRANSPORT_NOT_OBSERVED",
        )
        immediate = deployment_for(
            store,
            operation,
            production=production,
            require_ready=False,
            require_canonical=False,
        )
        durable(folder / "provider-receipt-immediate.json", owner.canonical(immediate))
        deadline = time.monotonic() + 600
        while immediate["state"] not in {"READY", "ERROR", "CANCELED"}:
            owner.require(
                time.monotonic() < deadline, "DOCS_DEPLOYMENT_NOT_READY_INSPECT_ONLY"
            )
            time.sleep(2)
            immediate = deployment_for(
                store,
                operation,
                production=production,
                require_ready=False,
                require_canonical=False,
            )
        owner.require(
            immediate["state"] == "READY",
            "DOCS_PROVIDER_DEPLOYMENT_FAILED_RETAIN_RECEIPT",
        )
        observed = deployment_for(store, operation, production=production)
        durable(folder / "provider-receipt-ready.json", owner.canonical(observed))
        return observed


def create_preview(store, operation):
    return create_publication(store, operation, production=False)


def main():
    owner.require(
        os.geteuid() == 0 and not os.getenv("GITHUB_ACTIONS") and len(sys.argv) == 2,
        "COMMISSIONED_ROOT_RUNNER_ONLY",
    )
    raw = sys.stdin.buffer.read(128 * 1024 + 1)
    owner.require(0 < len(raw) <= 128 * 1024, "DOCS_RUNNER_REQUEST_BOUND")
    request = json.loads(raw)
    owner.require(
        set(request) == {"binding", "context", "owner_token"},
        "EXACT_OWNER_RUNNER_REQUEST",
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
    except Exception:  # noqa: BLE001 -- redact arbitrary private provider/input failures
        print(
            json.dumps(
                {"state": "DOCS_OBSERVATION_FAILED_INSPECT_PRIVATE_STATE_WITHOUT_RETRY"}
            )
        )
        raise SystemExit(1) from None
