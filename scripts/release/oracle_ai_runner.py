"""Pinned AI API operations for oracle_owner; no caller-selected paths or commands.

This new runner is installed by the owner outside Git. It never reads Actions
credentials. Missing migration custody, storage/backup registration, pinned probe
images or complete hosted observations fail before a release can qualify.
"""

import base64
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oracle_release_profiles as profiles

PLAN = Path("/etc/onesa/oracle-ai-release.json")
OPENSSL = "/usr/bin/openssl" if sys.platform == "linux" else "/opt/homebrew/bin/openssl"
VERIFIER = Path(__file__).resolve().with_name("oracle_owner.py")
if not VERIFIER.exists():
    VERIFIER = Path(__file__).resolve().parent.parent / "oracle_owner.py"
ROOT = Path("/var/lib/onesa/release-verification/ai-api")
COMPOSE = Path("/opt/onesa/backends/ai.yaml")
IMAGES = Path("/etc/onesa/backends/ai.images.env")
ENV = {
    e: Path("/etc/onesa/backends/ai-" + e + ".env") for e in ["staging", "production"]
}
TARGET = {e: "onesa-ai-oracle-api-" + e + "-1" for e in ENV}
CHECKS = {
    "staging": {
        "source_build_image_identity",
        "configuration_and_isolation",
        "authentication_and_authorization",
        "persistence",
        "affected_workflows",
        "schema_and_migrations",
        "rollback_readiness",
        "security_and_contracts",
    },
    "operations": {
        "backup_restore",
        "monitoring_and_capacity",
        "privacy_publication_controls",
        "preservation_baseline",
        "rollback_readiness",
    },
    "deploy": {
        "exact_authorized_artifact",
        "configuration_preserved",
        "independent_components_preserved",
        "provider_receipt",
    },
    "production": {
        "source_build_image_identity",
        "health_readiness",
        "authentication_and_authorization",
        "affected_workflows",
        "persistence_preserved",
        "independent_components_preserved",
        "configuration_preserved",
        "no_unapproved_processing_or_actuation",
    },
}


class Refused(ValueError):
    pass


def require(value, code):
    if not value:
        raise Refused(code)


def now():
    return dt.datetime.now(dt.timezone.utc)


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def private(path, *, uid=0, directory=False):
    path = Path(path)
    require(
        path.is_absolute() and not any(p.is_symlink() for p in [path, *path.parents]),
        "CUSTODY_PATH_ALIAS",
    )
    s = path.stat()
    require(
        s.st_uid == uid
        and s.st_mode & 0o077 == 0
        and (
            stat.S_ISDIR(s.st_mode)
            if directory
            else stat.S_ISREG(s.st_mode) and s.st_nlink == 1
        ),
        "PRIVATE_CUSTODY_REQUIRED",
    )
    require(
        all(
            (p.stat().st_uid == 0 and p.stat().st_mode & 0o022 == 0)
            or (uid != 0 and p.stat().st_uid == uid and p.stat().st_mode & 0o077 == 0)
            for p in path.parents
        ),
        "CUSTODY_ANCESTOR",
    )
    return path


def read(path):
    return json.loads(private(path).read_bytes())


def pinned_public_file(path, expected):
    # Existing code and public recovery material are read-only, not secrets.
    # Their reviewed modes need not be changed to match credential custody.
    path = Path(path)
    require(
        path.is_absolute() and not any(p.is_symlink() for p in [path, *path.parents]),
        "PINNED_PUBLIC_FILE_ALIAS",
    )
    info = path.stat()
    require(
        path.is_file()
        and info.st_uid == 0
        and not info.st_mode & 0o022
        and info.st_nlink == 1
        and all(
            p.stat().st_uid == 0 and not p.stat().st_mode & 0o022 for p in path.parents
        )
        and sha(path) == expected,
        "PINNED_PUBLIC_FILE_CHANGED",
    )
    return path


def write(path, value):
    with os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb"
    ) as f:
        f.write(canonical(value))
        f.flush()
        os.fsync(f.fileno())
    fd = os.open(Path(path).parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_raw(path, data):
    with os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb"
    ) as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(Path(path).parent)


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@contextmanager
def backup_lock():
    path = Path("/var/lib/onesa/operations/database-backup-ai.lock")
    if path.exists():
        private(path)
    with os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600), "a"
    ) as stream:
        deadline = time.monotonic() + 300
        while True:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                require(
                    time.monotonic() < deadline,
                    "EXISTING_BACKUP_OPERATION_STILL_RUNNING",
                )
                time.sleep(0.25)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def command(args, *, data=None, timeout=30):
    r = subprocess.run(
        args,
        input=data,
        capture_output=True,
        timeout=timeout,
        check=False,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
    )
    require(
        r.returncode == 0 and len(r.stdout) <= 8 * 1024 * 1024,
        "PINNED_COMMAND_FAILED_INSPECT_WITHOUT_RETRY",
    )
    return r.stdout


def docker(*args, **kwargs):
    return command(["/usr/bin/docker", *args], **kwargs)


def inventory():
    """Capture every workload only after temporary Docker clients finish."""
    deadline = time.monotonic() + 20
    while True:
        require(time.monotonic() < deadline, "RUNTIME_INVENTORY_NOT_QUIESCENT")
        names = docker("ps", "--format", "{{.Names}}", timeout=5).decode().splitlines()
        require(all(v in names for v in TARGET.values()), "AI_RUNTIME_MISSING")
        try:
            values = json.loads(docker("inspect", *names, timeout=5))
        except Refused:
            # A --rm client can finish between list and inspect. Only retry this
            # read when a fresh list proves the inventory actually changed.
            current = docker("ps", "--format", "{{.Names}}", timeout=5)
            require(
                set(current.decode().splitlines()) != set(names),
                "PINNED_COMMAND_FAILED_INSPECT_WITHOUT_RETRY",
            )
        else:
            observed = {v["Name"].lstrip("/"): v for v in values}
            require(set(observed) == set(names), "RUNTIME_INVENTORY_INCOMPLETE")
            require(
                all(
                    type(v.get("HostConfig", {}).get("AutoRemove")) is bool
                    for v in values
                ),
                "RUNTIME_LIFECYCLE_METADATA_REQUIRED",
            )
            # Do not omit helpers or classify an unknown workload as safe. Wait
            # for automatic removal; a long-lived --rm workload blocks release.
            if not any(v["HostConfig"]["AutoRemove"] for v in values):
                return observed
        require(time.monotonic() < deadline, "RUNTIME_INVENTORY_NOT_QUIESCENT")
        time.sleep(0.25)


def summary(row):
    return {
        "container_id": row["Id"],
        "image": row["Image"],
        "started_at": row["State"]["StartedAt"],
        "restart_count": row["RestartCount"],
        "source": row["Config"].get("Labels", {}).get("org.onesa.source-commit")
        or row["Config"].get("Labels", {}).get("org.opencontainers.image.revision"),
        "environment_sha256": hashlib.sha256(
            "\n".join(sorted(row["Config"]["Env"])).encode()
        ).hexdigest(),
    }


def healthy(row):
    return (
        row["State"]["Running"]
        and not row["State"]["OOMKilled"]
        and row["State"].get("Health", {}).get("Status") == "healthy"
    )


def unchanged(before, after, except_names=()):
    require(
        all(
            name in after and summary(row) == summary(after[name])
            for name, row in before.items()
            if name not in except_names
        ),
        "CONCURRENT_OR_INDEPENDENT_RUNTIME_CHANGED",
    )


def runtime_values(path):
    rows = private(path).read_text().splitlines()
    require(
        all("=" in r and not r.startswith("#") for r in rows if r), "RUNTIME_FILE_SHAPE"
    )
    values = dict(r.split("=", 1) for r in rows if r)
    require(len(values) == len([r for r in rows if r]), "DUPLICATE_CONFIGURATION_KEY")
    return values


def candidate_environment(binding, env):
    require(
        env in ENV and re.fullmatch("[a-f0-9]{40}", binding["candidate_commit"]),
        "CANDIDATE_CONFIGURATION_SCOPE",
    )
    return profiles.configuration_folder(
        binding, Path("/etc/onesa/backends/candidates")
    ) / ("ai-" + env + ".env")


def plan_path(binding):
    return profiles.plan_path(
        binding, PLAN, Path("/etc/onesa/oracle-ai-frontend-release.json")
    )


def artifact_folder(binding):
    return profiles.artifact_folder(binding, ROOT)


def trusted_toolchain(plan):
    store = private(Path(plan["verifier_store"]), directory=True)
    trust = read(store / "trust.json")
    registry = read(Path("/etc/onesa/oracle-release-trust.json"))
    anchor = registry["installations"].get(str(store))
    require(
        anchor
        and anchor["active"] is True
        and all(
            anchor[k] == trust[k]
            for k in ["installation_id", "key_id", "verifier_sha256", "policy_sha256"]
        ),
        "TOOL_INSTALLATION_NOT_COMMISSIONED",
    )
    require(
        sha(private(store / "policy.json")) == trust["policy_sha256"]
        and sha(VERIFIER) == trust["verifier_sha256"],
        "COMMISSIONED_TOOL_POLICY_CHANGED",
    )
    policy = read(store / "policy.json")
    selected = profiles.policy_components(policy)
    if "mode" in plan or selected == profiles.SCOPED:
        profiles.validate_mode(plan["binding"], plan.get("mode"), policy)
    tool = policy["toolchain"]
    require(
        plan["probe_image"] == tool["probe_image"],
        "CANDIDATE_CANNOT_SELECT_VERIFICATION_IMAGE",
    )
    return tool


def scanned_configuration_digest(identity, proof):
    # OCI metadata is a content-addressed proof, never caller authorization.
    # The starting identity is independently pinned/observed from Docker.
    require(
        re.fullmatch("sha256:[a-f0-9]{64}", identity) and isinstance(proof, dict),
        "OCI_DESCRIPTOR_PROOF_REQUIRED",
    )
    current, visited = identity, set()
    for _ in range(5):
        require(current not in visited, "OCI_DESCRIPTOR_CYCLE")
        visited.add(current)
        encoded = proof.get(current)
        require(
            isinstance(encoded, str) and len(encoded) <= 1024 * 1024,
            "OCI_DESCRIPTOR_BOUND",
        )
        raw = base64.b64decode(encoded, validate=True)
        require(
            "sha256:" + hashlib.sha256(raw).hexdigest() == current,
            "OCI_DESCRIPTOR_HASH_MISMATCH",
        )
        item = json.loads(raw)
        require(item.get("schemaVersion") == 2, "OCI_DESCRIPTOR_SCHEMA")
        if "manifests" in item:
            native = [
                row
                for row in item["manifests"]
                if row.get("platform", {}).get("os") == "linux"
                and row.get("platform", {}).get("architecture") == "arm64"
            ]
            require(len(native) == 1, "SINGLE_NATIVE_ARM64_MANIFEST_REQUIRED")
            current = native[0]["digest"]
            require(re.fullmatch("sha256:[a-f0-9]{64}", current), "OCI_CHILD_DIGEST")
            continue
        require(
            item.get("mediaType")
            in [
                "application/vnd.oci.image.manifest.v1+json",
                "application/vnd.docker.distribution.manifest.v2+json",
            ],
            "OCI_IMAGE_MANIFEST_REQUIRED",
        )
        result = item.get("config", {}).get("digest", "")
        require(re.fullmatch("sha256:[a-f0-9]{64}", result), "OCI_CONFIGURATION_DIGEST")
        return result
    raise Refused("OCI_DESCRIPTOR_DEPTH")


def image_security(scan, identity):
    configuration = identity
    if scan["Metadata"]["ImageID"] != identity:
        require(
            re.fullmatch("sha256:[a-f0-9]{64}", identity),
            "EXACT_IMAGE_IDENTITY_REQUIRED",
        )
        configuration = scanned_configuration_digest(
            identity,
            read(
                Path("/var/lib/onesa/release-verification/image-descriptors")
                / (identity[7:] + ".json")
            ),
        )
    require(
        scan["Metadata"]["ImageID"] == configuration
        and scan.get("Results")
        and scan.get("ArtifactName")
        and scan.get("CreatedAt"),
        "COMPLETE_CURRENT_IMAGE_SCAN_REQUIRED",
    )
    require(
        dt.timedelta(0)
        <= now() - dt.datetime.fromisoformat(scan["CreatedAt"].replace("Z", "+00:00"))
        < dt.timedelta(hours=24),
        "IMAGE_SCAN_STALE",
    )
    # Same gate as scripts/release/image_gate.py; retain all vendor findings.
    require(
        not any(
            row.get("Secrets")
            or any(
                v.get("Severity") in ["HIGH", "CRITICAL"]
                for v in row.get("Vulnerabilities", [])
            )
            for row in scan["Results"]
        ),
        "IMAGE_SECURITY_FAILED",
    )


def validate_plan(binding):
    require(
        binding.get("repository") == "DruHustle/onesa-ai-platform"
        and profiles.kind(binding) == "api"
        and binding.get("target_environment") == "production",
        "COMPONENT_SCOPE",
    )
    require(
        re.fullmatch("[a-f0-9]{40}", binding.get("candidate_commit", "")),
        "EXACT_SOURCE_REQUIRED",
    )
    plan = read(plan_path(binding))
    require(
        plan["binding"] == binding and plan["schema_version"] == 1,
        "OWNER_INSTALLED_PLAN_BINDING",
    )
    folder = private(artifact_folder(binding), directory=True)
    for name, expected in [
        ("source.tar", binding["source_sha256"]),
        ("image.tar.gz", binding["build_sha256"]),
    ]:
        require(sha(private(folder / name)) == expected, "ARCHIVE_IDENTITY")
    require(
        sha(private(COMPOSE)) == plan["compose_sha256"], "COMPOSE_CONFIGURATION_CHANGED"
    )
    require(
        plan.get("mode") in ["foundation", "twins", "cybersecurity"],
        "EXPLICIT_API_RELEASE_MODE",
    )
    for env, envpath in ENV.items():
        prepared = private(candidate_environment(binding, env))
        require(
            sha(prepared) == binding["configuration_sha256"][env]
            and sha(private(envpath))
            in [
                binding["configuration_sha256"][env],
                plan["baseline_runtime_sha256"][env],
            ],
            "RUNTIME_CONFIGURATION_CHANGED",
        )
        values = runtime_values(prepared)
        current = runtime_values(envpath)
        enabled = profiles.enabled_features(values, plan["mode"])
        require_probe_policy(binding, env, plan, enabled)
        allowed = {
            "ONESA_DIGITAL_TWINS_ENABLED",
            "ONESA_DIGITAL_TWINS_DEMO_ENABLED",
            "ONESA_DIGITAL_TWINS_STORAGE_DIRECTORY",
            "ONESA_DIGITAL_TWINS_PERSISTENT_MOUNT",
            "ONESA_INDUSTRIAL_DEMO_ENABLED",
            "ONESA_CYBERSECURITY_ENABLED",
        }
        if env == "staging":
            allowed.add("ONESA_PUBLIC_ORIGIN")
        require(
            {k: v for k, v in current.items() if k not in allowed}
            == {k: v for k, v in values.items() if k not in allowed},
            "UNRELATED_CONFIGURATION_OR_CREDENTIAL_CHANGED",
        )
        require(
            values["ONESA_ENVIRONMENT"] == env
            and values["ONESA_SECURE_COOKIES"] == "true"
            and values["ONESA_REGISTRATION_MODE"] == "invitation",
            "HOSTED_AUTHENTICATION_PROFILE",
        )
        if plan["mode"] == "foundation":
            require(
                values.get("ONESA_DIGITAL_TWINS_ENABLED", "false") == "false"
                and values.get("ONESA_DIGITAL_TWINS_DEMO_ENABLED", "false") == "false"
                and values.get("ONESA_INDUSTRIAL_DEMO_ENABLED", "false") == "false"
                and values.get("ONESA_CYBERSECURITY_ENABLED", "false") == "false"
                and values.get("ONESA_CYBERSECURITY_DEMO_ENABLED", "false") == "false"
                and values.get("ONESA_CYBERSECURITY_AI_ENABLED", "false") == "false",
                "FOUNDATION_MUST_REMAIN_FEATURE_OFF",
            )
        elif plan["mode"] == "cybersecurity":
            require(
                values.get("ONESA_CYBERSECURITY_ENABLED") == "true"
                and values.get("ONESA_CYBERSECURITY_DEMO_ENABLED", "false") == "false"
                and values.get("ONESA_CYBERSECURITY_AI_ENABLED", "false") == "false"
                and plan["migration_revision"] == "20261026_cybersecurity"
                and all(
                    values.get(k) == current.get(k)
                    for k in allowed
                    if k not in {"ONESA_CYBERSECURITY_ENABLED", "ONESA_PUBLIC_ORIGIN"}
                ),
                "CYBERSECURITY_INDEPENDENT_ACTIVATION_PROFILE",
            )
        else:
            require(
                values.get("ONESA_CYBERSECURITY_ENABLED", "false")
                == current.get("ONESA_CYBERSECURITY_ENABLED", "false"),
                "INDEPENDENT_CYBERSECURITY_CONFIGURATION_CHANGED",
            )
            require(
                values.get("ONESA_DIGITAL_TWINS_ENABLED") == "true"
                and values.get("ONESA_DIGITAL_TWINS_DEMO_ENABLED", "false") == "false"
                and values.get("ONESA_DIGITAL_TWINS_PERSISTENT_MOUNT") == "true",
                "TWINS_ACTIVATION_PROFILE",
            )
        if "twins" in enabled:
            require(
                values.get("ONESA_DIGITAL_TWINS_PERSISTENT_MOUNT") == "true"
                and values.get("ONESA_DIGITAL_TWINS_STORAGE_DIRECTORY")
                == "/var/lib/onesa/twins",
                "PRIVATE_CONTAINER_STORAGE_PATH",
            )
            root = private(
                Path("/var/lib/onesa/ai-twins") / env, uid=10001, directory=True
            )
            require(
                str(root) == plan["storage"][env]
                and {"device": root.stat().st_dev, "inode": root.stat().st_ino}
                == plan["storage_identity"][env],
                "STORAGE_MOUNT_CHANGED",
            )
    require(
        runtime_values(candidate_environment(binding, "staging"))["ONESA_DATABASE_URL"]
        != runtime_values(candidate_environment(binding, "production"))[
            "ONESA_DATABASE_URL"
        ],
        "DATABASES_NOT_ISOLATED",
    )
    image = json.loads(docker("image", "inspect", binding["artifact_digest"]))[0]
    require(
        image["Id"] == binding["artifact_digest"]
        and image["Architecture"] == "arm64"
        and image["Config"].get("Labels", {}).get("org.opencontainers.image.revision")
        == binding["candidate_commit"]
        and image["Config"]["Labels"].get("org.onesa.source-archive-sha256")
        == binding["source_sha256"],
        "NATIVE_IMAGE_SOURCE_IDENTITY",
    )
    scan = read(folder / "scan.json")
    image_security(scan, image["Id"])
    tool = trusted_toolchain(plan)
    probe = json.loads(docker("image", "inspect", plan["probe_image"]))[0]
    require(
        probe["Id"] == plan["probe_image"]
        and probe["Config"].get("Labels", {}).get("org.opencontainers.image.revision")
        == tool["source_commit"],
        "UNREVIEWED_PROBE_IMAGE",
    )
    require(
        plan["physical_hardware_authorized"] is False
        and plan["processing_scope"] == "owned-synthetic-release-verification"
        and plan["legal_publication_controls_unchanged"] is True,
        "PRIVACY_OR_PHYSICAL_SCOPE",
    )
    verify_application_bytes(folder, binding)
    verify_probe_bytes(folder, binding, plan)
    return folder, plan


def verify_invocation(binding, context, phase, plan, *, dependency=False):
    if phase == "staging":
        require(set(context) == {"context_id"}, "STAGING_SIGNED_CONTEXT_ONLY")
    elif phase == "deploy":
        require(
            set(context) == {"operation_id", "authorization_id"},
            "DEPLOY_SIGNED_AUTHORIZATION_OPERATION_ONLY",
        )
    elif phase == "production":
        require(
            set(context) == {"operation_id", "read_only"}
            and context["read_only"] is True,
            "READ_ONLY_PRODUCTION_OBSERVATION_ONLY",
        )
    elif phase == "operations":
        require(
            set(context) == {"context_id"}
            or set(context) == {"qualification_id", "owner_decision"}
            and context["owner_decision"] == "approve"
            or set(context) == {"authorization_id", "before_deployment"}
            and context["before_deployment"] is True,
            "OPERATIONS_SIGNED_INVOCATION_ONLY",
        )
    else:
        raise Refused("RUNNER_PHASE_SCOPE")
    store = private(Path(plan["verifier_store"]), directory=True)
    for name in ["trust.json", "public.pem", "policy.json", "records.sqlite"]:
        private(store / name)
    trust = read(store / "trust.json")
    registry = read(Path("/etc/onesa/oracle-release-trust.json"))
    anchor = registry["installations"].get(str(store))
    require(
        anchor
        and anchor["active"] is True
        and all(
            anchor[k] == trust[k]
            for k in ["installation_id", "key_id", "verifier_sha256", "policy_sha256"]
        ),
        "ISSUER_NOT_COMMISSIONED",
    )
    require(
        sha(store / "public.pem") == trust["key_id"]
        and sha(store / "policy.json") == trust["policy_sha256"]
        and sha(VERIFIER) == trust["verifier_sha256"],
        "ISSUER_CUSTODY_PIN_CHANGED",
    )
    require(sha(OPENSSL) == trust["openssl_sha256"], "SIGNATURE_TOOL_CHANGED")
    db = sqlite3.connect(
        "file:" + str(store / "records.sqlite") + "?mode=ro", uri=True, timeout=20
    )

    records = []
    visited = set()

    def record(identifier, kind=None, historical=False):
        require(
            identifier not in visited and len(visited) < 12,
            "SIGNED_RECORD_CHAIN_CYCLE_OR_BOUND",
        )
        visited.add(identifier)
        require(str(UUID(identifier)) == identifier, "CANONICAL_LEDGER_RECORD_REQUIRED")
        row = db.execute(
            "SELECT envelope,revoked,parent,kind FROM records WHERE id=?", (identifier,)
        ).fetchone()
        require(
            row and ((historical and not dependency) or not row[1]),
            "SIGNED_LEDGER_RECORD_MISSING_OR_REVOKED",
        )
        envelope = json.loads(row[0])
        r = envelope["record"]
        sig = envelope["signature"]
        require(
            sig["algorithm"] == "Ed25519" and sig["key_id"] == trust["key_id"],
            "FOREIGN_RECORD_SIGNER",
        )
        with tempfile.TemporaryDirectory(
            prefix=".runner-signature-", dir=store
        ) as folder:
            p = Path(folder)
            (p / "record").write_bytes(canonical(r))
            (p / "signature").write_bytes(base64.b64decode(sig["value"], validate=True))
            command(
                [
                    OPENSSL,
                    "pkeyutl",
                    "-verify",
                    "-rawin",
                    "-pubin",
                    "-inkey",
                    str(store / "public.pem"),
                    "-sigfile",
                    str(p / "signature"),
                    "-in",
                    str(p / "record"),
                ]
            )
        require(
            r["id"] == identifier
            and r["kind"] == row[3]
            and r["parent"] == row[2]
            and (kind is None or r["kind"] == kind)
            and r["binding"] == binding
            and r["workflow_run_id"] == 0,
            "SIGNED_RECORD_SOURCE_OR_PROVENANCE_MISMATCH",
        )
        provenance = r["owner_provenance"]
        require(
            provenance["owner"] == "DruHustle"
            and provenance["mechanism"]
            == "commissioned-pinned-OpenSSH-and-authenticated-owner"
            and provenance["installation_id"] == trust["installation_id"]
            and provenance["verifier_sha256"] == trust["verifier_sha256"],
            "OWNER_PROVENANCE_REQUIRED",
        )
        issued, expiry = (
            dt.datetime.fromisoformat(r["issued_at"]),
            dt.datetime.fromisoformat(r["expires_at"]),
        )
        require(
            r.get("schema_version") == 1
            and r.get("execution_context")
            == (
                "owner-operated-oracle-staging"
                if r["kind"] in ["context", "qualification"]
                else "owner-operated-oracle-release"
            )
            and dt.timedelta(0) < expiry - issued <= dt.timedelta(hours=24)
            and (historical or issued <= now() < expiry),
            "SIGNED_RECORD_EXPIRED",
        )
        records.append(r)
        if r["parent"]:
            record(r["parent"], historical=historical)
        return r

    try:
        historical = phase == "production"
        if "operation_id" in context:
            if dependency:
                child = db.execute(
                    "SELECT id FROM records WHERE kind='production-verification' AND parent=? ORDER BY sequence DESC LIMIT 1",
                    (context["operation_id"],),
                ).fetchone()
                require(child, "ACCEPTED_API_VERIFICATION_REQUIRED")
                record(child[0], "production-verification", True)
                op = next(
                    item for item in records if item["id"] == context["operation_id"]
                )
            else:
                op = record(context["operation_id"], "deployment-intent", historical)
            row = db.execute(
                "SELECT state,authorization FROM deployments WHERE id=?", (op["id"],)
            ).fetchone()
            require(
                row
                and (phase != "deploy" or row[0] == "request-recorded")
                and (not dependency or row[0] == "accepted"),
                "DURABLE_DEPLOYMENT_INTENT_REQUIRED",
            )
            require(
                op["details"]["provider_request_budget"] == 1
                and op["details"]["automatic_retry"] is False,
                "SINGLE_REQUEST_BUDGET_REQUIRED",
            )
            if phase == "deploy":
                require(
                    row[1] == context["authorization_id"] and op["parent"] == row[1],
                    "AUTHORIZATION_OPERATION_MISMATCH",
                )
        elif "context_id" in context:
            r = record(context["context_id"], "context")
            state = db.execute(
                "SELECT state FROM contexts WHERE id=?", (r["id"],)
            ).fetchone()
            require(
                state and state[0] == "reserved",
                "QUALIFICATION_NOT_ATOMICALLY_RESERVED",
            )
        elif "qualification_id" in context:
            record(context["qualification_id"], "qualification")
        elif "authorization_id" in context:
            record(context["authorization_id"], "authorization")
        else:
            raise Refused("SIGNED_OWNER_INVOCATION_REQUIRED")
    finally:
        db.close()
    return records


def source_inventory(archive_path, binding):
    expected = {}
    files = {}
    tree = {}
    total = 0
    with tarfile.open(archive_path, "r:") as archive:
        members = archive.getmembers()
        require(len(members) < 20000, "SOURCE_ARCHIVE_ENTRY_BOUND")
        for member in members:
            path = Path(member.name)
            require(
                not path.is_absolute()
                and ".." not in path.parts
                and (member.isfile() or member.isdir()),
                "SOURCE_ARCHIVE_TYPE_OR_PATH",
            )
            if member.isfile():
                total += member.size
                require(
                    member.size <= 32 * 1024 * 1024 and total <= 512 * 1024 * 1024,
                    "SOURCE_ARCHIVE_BYTE_BOUND",
                )
                data = archive.extractfile(member).read()
                node = tree
                for name in path.parts[:-1]:
                    node = node.setdefault(name, {})
                    require(isinstance(node, dict), "SOURCE_DIRECTORY_ALIAS")
                require(path.name not in node, "DUPLICATE_SOURCE_ARCHIVE_PATH")
                files[member.name] = hashlib.sha256(data).hexdigest()
                blob = hashlib.sha1(
                    b"blob " + str(len(data)).encode() + b"\0" + data
                ).digest()
                node[path.name] = (
                    b"100755" if member.mode & 0o111 else b"100644",
                    blob,
                )
            prefix = "onesa-ai-platform-backend/"
            if member.isfile() and member.name.startswith(prefix):
                rel = member.name[len(prefix) :]
                if rel.startswith(("app/", "migrations/")) or rel in [
                    "alembic.ini",
                    "start.sh",
                ]:
                    require(member.size < 8 * 1024 * 1024, "SOURCE_FILE_BOUND")
                    expected[rel] = hashlib.sha256(data).hexdigest()

    def git_tree(node):
        value = b""
        for name, entry in sorted(
            node.items(),
            key=lambda p: (p[0] + ("/" if isinstance(p[1], dict) else "")).encode(),
        ):
            mode, digest = (
                (b"40000", git_tree(entry)) if isinstance(entry, dict) else entry
            )
            value += mode + b" " + name.encode() + b"\0" + digest
        return hashlib.sha1(
            b"tree " + str(len(value)).encode() + b"\0" + value
        ).digest()

    require(
        git_tree(tree).hex() == binding["source_tree"],
        "ARCHIVE_DIFFERS_FROM_QUALIFIED_GIT_TREE",
    )
    require(
        expected and "app/twin_files.py" in expected,
        "COMPLETE_BACKEND_ARCHIVE_REQUIRED",
    )
    return expected, files


def verify_application_bytes(folder, binding):
    expected, _files = source_inventory(private(folder / "source.tar"), binding)
    program = "import pathlib,hashlib,json;root=pathlib.Path('/app');out={}\nfor top in ['app','migrations']:\n for p in (root/top).rglob('*'):\n  if p.is_file() and '__pycache__' not in p.parts and not p.name.endswith('.pyc'):out[str(p.relative_to(root))]=hashlib.sha256(p.read_bytes()).hexdigest()\nfor n in ['alembic.ini','start.sh']:out[n]=hashlib.sha256((root/n).read_bytes()).hexdigest()\nprint(json.dumps({'files':out,'identity':json.loads((root/'source-identity.json').read_text())}))"
    actual = json.loads(
        docker(
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--entrypoint",
            "python",
            binding["artifact_digest"],
            "-c",
            program,
            timeout=60,
        )
    )
    require(
        actual["files"] == expected,
        "IMAGE_APPLICATION_BYTES_DIFFER_FROM_SOURCE_ARCHIVE",
    )
    require(
        actual["identity"]
        == {
            "source_commit": binding["candidate_commit"],
            "source_archive_sha256": binding["source_sha256"],
        },
        "BUILD_SOURCE_IDENTITY_FILE_MISMATCH",
    )
    return hashlib.sha256(canonical(expected)).hexdigest()


PROBE_RESOURCE_FILES = (
    "onesa-ai-platform-frontend/apps/chat/public/brand/icons/v1/sources.json",
)


def probe_source_files(files):
    require(
        all(name in files for name in PROBE_RESOURCE_FILES),
        "MANDATORY_PROBE_RESOURCE_SOURCE_MISSING",
    )
    return {
        name: value
        for name, value in files.items()
        if name.startswith(
            (
                "scripts/",
                "onesa-ai-platform-backend/app/",
                "onesa-ai-platform-backend/migrations/",
            )
        )
        or name
        in [
            "onesa-ai-platform-backend/alembic.ini",
            "onesa-ai-platform-frontend/apps/chat/package.json",
            "onesa-ai-platform-frontend/apps/chat/package-lock.json",
            *PROBE_RESOURCE_FILES,
        ]
    }


def verify_probe_bytes(folder, binding, plan):
    # Verification code belongs to the explicitly commissioned tool release,
    # independent of a later application candidate. Candidate scripts cannot
    # select a replacement verifier by changing their own source archive.
    expected = trusted_toolchain(plan)["probe_files"]
    resources = [
        "onesa-ai-platform-backend/alembic.ini",
        "onesa-ai-platform-frontend/apps/chat/package.json",
        "onesa-ai-platform-frontend/apps/chat/package-lock.json",
        *PROBE_RESOURCE_FILES,
    ]
    program = (
        "import pathlib,hashlib,json;root=pathlib.Path('/opt/onesa-ai-platform');out={}\n"
        "for top in ['scripts','onesa-ai-platform-backend/app','onesa-ai-platform-backend/migrations']:\n"
        " for p in (root/top).rglob('*'):\n"
        "  if p.is_file() and '__pycache__' not in p.parts and not p.name.endswith('.pyc'):out[str(p.relative_to(root))]=hashlib.sha256(p.read_bytes()).hexdigest()\n"
        "for n in "
        + json.dumps(resources)
        + ":out[n]=hashlib.sha256((root/n).read_bytes()).hexdigest()\n"
        "print(json.dumps(out))"
    )
    actual = json.loads(
        docker(
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--entrypoint",
            "python3",
            plan["probe_image"],
            "-c",
            program,
            timeout=60,
        )
    )
    require(actual == expected, "PROBE_BYTES_DIFFER_FROM_COMMISSIONED_TOOL_SOURCE")
    scan = read(private(folder / "probe-scan.json"))
    image_security(scan, plan["probe_image"])


def migration_prerequisites(plan):
    if plan["mode"] == "foundation":
        return
    # The migration owner is a separate operator binding. Never upgrade the runtime
    # role, use another product's key, or execute DDL with a caller-supplied URL.
    for env in ENV:
        p = Path("/etc/onesa/backends/ai-" + env + "-migration.env")
        require(p.exists(), "MISSING_AI_" + env.upper() + "_MIGRATION_OWNER_BINDING")
        values = runtime_values(p)
        require(
            set(values) == {"ONESA_DATABASE_URL"}
            and values["ONESA_DATABASE_URL"]
            != runtime_values(ENV[env])["ONESA_DATABASE_URL"],
            "SEPARATE_MIGRATION_OWNER_REQUIRED",
        )
    require(
        plan["migration_revision"] in ["20261025_twins", "20261026_cybersecurity"]
        and plan["expected_schema_revision"] == plan["migration_revision"],
        "ADDITIVE_MIGRATION_SCOPE",
    )


def prepare_artifact_directories(folder):
    """Initialize only private journal parents; never reuse an operation directory."""
    folder = private(Path(folder), directory=True)
    for name in ["operations", "observations"]:
        path = folder / name
        try:
            path.mkdir(mode=0o700, exist_ok=False)
        except FileExistsError:
            pass
        private(path, directory=True)


def preflight(binding):
    folder, plan = validate_plan(binding)
    migration_prerequisites(plan)
    cpus = probe_cpu_limit()
    network = probe_network()
    require(shutil.disk_usage("/").free > 12 * 1024**3, "DISK_BUDGET")
    import oracle_ai_frontend

    frontend = oracle_ai_frontend.preview_binding(binding)
    frontend_folder, _frontend_plan = oracle_ai_frontend.validate(frontend)
    prepare_artifact_directories(folder)
    prepare_artifact_directories(frontend_folder)
    authentication = oracle_ai_frontend.cli_authentication(plan)
    retained = None
    if profiles.component(binding) not in profiles.LEGACY:
        metadata = oracle_ai_frontend.observe_provider(
            binding, "production", plan, "preflight"
        )
        retained = oracle_ai_frontend.verify_retained_frontend(binding, plan, metadata)
    return {
        "state": "PREREQUISITES_READY_NOT_QUALIFIED",
        "source": binding["candidate_commit"],
        "provider_requests": 0,
        "records_issued": 0,
        "plan_sha256": sha(plan_path(binding)),
        "artifact_folder": str(folder),
        "hosted_probe_cpu_limit": cpus,
        "hosted_probe_network": network,
        "provider_cli_authentication": authentication,
        "retained_frontend_inspection": retained,
    }


def accepted_rollback_proof(plan):
    old = plan["rollback"]
    binding = old["binding"]
    require(
        binding["repository"] == plan["binding"]["repository"] == profiles.REPOSITORY
        and binding["target_environment"] == "production"
        and profiles.kind(binding) == "api"
        and binding["artifact_digest"] == old["image"]
        and binding["candidate_commit"] != plan["binding"]["candidate_commit"],
        "ROLLBACK_SOURCE_BINDING",
    )
    chain = verify_invocation(
        binding,
        {"operation_id": old["operation_id"], "read_only": True},
        "production",
        {**plan, "verifier_store": old.get("verifier_store", plan["verifier_store"])},
        dependency=True,
    )
    context = next(record["id"] for record in chain if record["kind"] == "context")
    output = artifact_folder(binding) / "observations" / context
    proof = read(output / "forward-check-receipt.json")
    require(
        proof["binding"] == binding
        and proof["operation_id"] == context
        and proof["candidate_image"] == old["image"]
        and proof["status"] == "PASS"
        and proof["synthetic_database_restore"] == "PASS"
        and proof["twins_disabled"] is True
        and (
            plan["mode"] != "cybersecurity"
            or (
                proof.get("cybersecurity_disabled") is True
                and proof.get("schema_revision") == "20261026_cybersecurity"
            )
        )
        and proof["production_writes"] == 0,
        "ACCEPTED_FUTURE_SCHEMA_ROLLBACK_REQUIRED",
    )
    return sha(output / "forward-check-receipt.json")


def coordinated_backup_observation(binding, plan):
    registration = read(Path("/etc/onesa/ai-twin-backup-registration.json"))
    producer = Path(__file__).with_name("oracle_ai_backup.py")
    require(
        registration["storage_root"] == plan["storage"]["production"]
        and registration["source_commit"] == trusted_toolchain(plan)["source_commit"]
        and registration["release_candidate_commit"] == binding["candidate_commit"]
        and registration["producer_sha256"] == sha(private(producer))
        and registration["automatic_deletion"] is False
        and registration["cap_bytes"] == 64 * 1024 * 1024,
        "COORDINATED_BACKUP_REGISTRATION_CHANGED",
    )
    # Execute the pinned observer: it GETs the actual registered database/file
    # ciphertext. An unsigned caller PASS/receipt is never accepted as a check.
    coordinated = json.loads(
        command(["/usr/bin/python3", "-I", str(producer), "--inspect"], timeout=240)
    )
    require(
        coordinated["status"] == "PASS"
        and coordinated["coordinated_snapshot"] is True
        and coordinated["encrypted"] is True
        and coordinated["off_instance_readback"] == "PASS"
        and coordinated["source_commit"] == trusted_toolchain(plan)["source_commit"]
        and coordinated["release_candidate_commit"] == binding["candidate_commit"]
        and coordinated["application_runtime"]
        == {
            "source_commit": inventory()[TARGET["production"]]["Config"]["Labels"][
                "org.onesa.source-commit"
            ],
            "image": inventory()[TARGET["production"]]["Image"],
            "container_id": inventory()[TARGET["production"]]["Id"],
            "runtime_sha256": sha(ENV["production"]),
        }
        and coordinated["producer_sha256"] == sha(producer),
        "COORDINATED_BACKUP_READBACK_FAILED",
    )
    require(
        dt.timedelta(0)
        <= now() - dt.datetime.fromisoformat(coordinated["verified_at"])
        < dt.timedelta(hours=36),
        "COORDINATED_BACKUP_STALE",
    )
    return {
        "producer_source": coordinated["source_commit"],
        "release_candidate_commit": coordinated["release_candidate_commit"],
        "application_runtime": coordinated["application_runtime"],
        "verified_at": coordinated["verified_at"],
        "registration_sha256": sha(Path("/etc/onesa/ai-twin-backup-registration.json")),
        "off_instance_readback": "PASS",
    }


def post_deployment_backup(binding, plan):
    profiles.bound_mode(binding, plan["mode"])
    actual = inventory()[TARGET["production"]]
    enabled = profiles.enabled_features(
        running_configuration(binding, "production", actual), plan["mode"]
    )
    if "twins" not in enabled:
        return None
    command(
        [
            "/usr/bin/python3",
            "-I",
            str(Path(__file__).with_name("oracle_ai_backup.py")),
        ],
        timeout=240,
    )
    return operational_observations(binding, plan)


def operational_observations(binding, plan):
    if profiles.component(binding) not in profiles.LEGACY:
        import oracle_ai_frontend

        metadata = oracle_ai_frontend.observe_provider(
            binding, "production", plan, "operations"
        )
        oracle_ai_frontend.verify_retained_frontend(binding, plan, metadata)
    metrics = read(Path("/var/lib/onesa/operations/metrics.json"))
    require(
        not metrics["simulation"]
        and not metrics["alerts"]
        and not metrics.get("notification_pending")
        and not metrics.get("notification_reconciliation_required"),
        "OPERATIONS_ALERT_OR_UNQUALIFIED_SAMPLE",
    )
    require(
        dt.timedelta(0)
        <= now() - dt.datetime.fromisoformat(metrics["checked_at"])
        < dt.timedelta(minutes=5),
        "OPERATIONS_SAMPLE_STALE",
    )
    m = metrics["metrics"]
    require(
        m["database_available"]
        and not m["database_backup_failed"]
        and m["memory_available_bytes"] > 2 * 1024**3
        and m["disk_used_percent"] < 80,
        "OPERATIONS_CAPACITY_FAILED",
    )
    for timer in ["onesa-database-backup-ai.timer", "onesa-portal-monitor.timer"]:
        require(
            command(["/usr/bin/systemctl", "is-active", timer]).strip() == b"active",
            "EXISTING_TIMER_INACTIVE",
        )
    backup = read(Path("/var/lib/onesa/operations/database-backup-ai-success.json"))
    require(
        backup["consistent_snapshot"] is True
        and dt.timedelta(0)
        <= now() - dt.datetime.fromisoformat(backup["verified_at"])
        < dt.timedelta(hours=36),
        "DATABASE_BACKUP_STALE",
    )
    if plan["mode"] == "foundation":
        observed = inspect_database_backup(backup, plan)
        output = (
            Path(plan["artifact_folder"])
            / "observations"
            / plan["qualification_context_id"]
        )
        proof = read(output / "forward-check-receipt.json")
        replacement = read(output / "replacement-ok.json")
        hosted = read(output / "receipt.json")
        require(
            proof["binding"] == binding
            and proof["operation_id"] == plan["qualification_context_id"]
            and proof["candidate_image"] == binding["artifact_digest"]
            and proof["status"] == "PASS"
            and proof["synthetic_database_restore"] == "PASS"
            and proof["twins_disabled"] is True
            and proof["cybersecurity_disabled"] is True
            and proof["schema_revision"] == "20261026_cybersecurity"
            and proof["production_writes"] == 0,
            "FORWARD_COMPATIBLE_ROLLBACK_NOT_PROVEN",
        )
        require(
            replacement["restore_receipt_sha256"]
            == sha(output / "forward-check-receipt.json")
            and hosted["controlled_replacement"] == replacement
            and hosted["status"] == "PASS"
            and hosted["binding"] == binding
            and hosted["checks"]["twins_disabled"] == "PASS"
            and hosted["checks"]["cybersecurity_disabled"] == "PASS",
            "FOUNDATION_HOSTED_PRESERVATION_NOT_PROVEN",
        )
        old = plan["rollback"]
        require(
            json.loads(docker("image", "inspect", old["image"]))[0]["Id"]
            == old["image"]
            and old["compatible_schema_revision"] == plan["expected_schema_revision"]
            and old["retain_additive_schema_and_files"] is True,
            "CURRENT_SCHEMA_ROLLBACK_ARTIFACT_MISSING",
        )
        return {
            "checks": {k: "PASS" for k in CHECKS["operations"]},
            "mode": "foundation",
            "twins_enabled": False,
            "migration_performed": False,
            "backup_readback": observed,
            "forward_rollback_receipt_sha256": sha(
                output / "forward-check-receipt.json"
            ),
            "metrics_checked_at": metrics["checked_at"],
            "backup_verified_at": backup["verified_at"],
            "physical_hardware_authorized": False,
        }
    if plan["mode"] == "cybersecurity":
        observed = inspect_database_backup(backup, plan)
        output = (
            Path(plan["artifact_folder"])
            / "observations"
            / plan["qualification_context_id"]
        )
        restored = read(output / "restore-receipt.json")
        replacement = read(output / "replacement-ok.json")
        hosted = read(output / "receipt.json")
        require(
            restored["binding"] == binding
            and restored["operation_id"] == plan["qualification_context_id"]
            and restored["status"] == "PASS"
            and restored["profile"] == "cybersecurity"
            and restored["schema_revision"] == "20261026_cybersecurity"
            and restored["production_writes"] == 0
            and restored["database_manifest_matches"] is True
            and restored["encrypted_fixture_recovery"] == "PASS"
            and restored["fixture_owners"] == 2
            and replacement["restore_receipt_sha256"]
            == sha(output / "restore-receipt.json")
            and hosted["controlled_replacement"] == replacement
            and hosted["binding"] == binding
            and hosted["status"] == "PASS"
            and hosted["fixture_identities_disabled"] is True
            and hosted["existing_records_preserved"] is True,
            "CYBERSECURITY_HOSTED_RESTORE_CHAIN_REQUIRED",
        )
        rollback = accepted_rollback_proof(plan)
        require(
            json.loads(docker("image", "inspect", plan["rollback"]["image"]))[0]["Id"]
            == plan["rollback"]["image"]
            and plan["rollback"]["retain_additive_schema_and_files"] is True,
            "CYBERSECURITY_ROLLBACK_IMAGE_MISSING",
        )
        enabled = profiles.enabled_features(
            runtime_values(candidate_environment(binding, "production")), plan["mode"]
        )
        coordinated = (
            coordinated_backup_observation(binding, plan)
            if "twins" in enabled
            else None
        )
        return {
            "checks": {k: "PASS" for k in CHECKS["operations"]},
            "mode": "cybersecurity",
            "coordinated_backup": coordinated,
            "backup_readback": observed,
            "restore_receipt_sha256": sha(output / "restore-receipt.json"),
            "accepted_rollback_proof_sha256": rollback,
            "metrics_checked_at": metrics["checked_at"],
            "physical_hardware_authorized": False,
        }
    coordinated = coordinated_backup_observation(binding, plan)
    output = (
        Path(plan["artifact_folder"])
        / "observations"
        / plan["qualification_context_id"]
    )
    restore = read(output / "restore-receipt.json")
    replacement = read(output / "replacement-ok.json")
    hosted = read(output / "receipt.json")
    require(
        restore["binding"] == binding
        and restore["operation_id"] == plan["qualification_context_id"]
        and restore["status"] == "PASS"
        and restore["profile"] == "twins"
        and restore["schema_revision"] == plan["expected_schema_revision"]
        and restore["production_writes"] == 0
        and restore["database_manifest_matches"] is True
        and restore["file_hashes_match"] is True
        and restore["encrypted_fixture_recovery"] == "PASS"
        and restore["fixture_owners"] == 2,
        "OWNED_ISOLATED_RESTORE_FAILED",
    )
    require(
        replacement["restore_receipt_sha256"] == sha(output / "restore-receipt.json")
        and hosted["controlled_replacement"] == replacement
        and hosted["binding"] == binding
        and hosted["status"] == "PASS"
        and hosted["fixture_identities_disabled"] is True
        and hosted["existing_records_preserved"] is True,
        "GENUINE_STAGING_RESTORE_CHAIN_REQUIRED",
    )
    require(shutil.disk_usage("/").free > 12 * 1024**3, "DISK_BUDGET")
    rollback_proof = accepted_rollback_proof(plan)
    old = plan["rollback"]
    require(
        json.loads(docker("image", "inspect", old["image"]))[0]["Id"] == old["image"]
        and old["retain_additive_schema_and_files"] is True,
        "ROLLBACK_ARTIFACT_MISSING",
    )
    return {
        "checks": {k: "PASS" for k in CHECKS["operations"]},
        "metrics_checked_at": metrics["checked_at"],
        "backup_verified_at": backup["verified_at"],
        "restore_receipt_sha256": sha(output / "restore-receipt.json"),
        "registration_sha256": sha(Path("/etc/onesa/ai-twin-backup-registration.json")),
        "coordinated_backup": coordinated,
        "accepted_rollback_proof_sha256": rollback_proof,
        "legal_publication_controls_unchanged": True,
        "physical_hardware_authorized": False,
    }


def inspect_database_backup(receipt, plan):
    profile = plan["legacy_backup"]
    script = pinned_public_file(
        Path(profile["transport_path"]), profile["transport_sha256"]
    )
    require(
        sha(script) == profile["transport_sha256"]
        and json.loads(docker("image", "inspect", profile["transport_image"]))[0]["Id"]
        == profile["transport_image"],
        "ESTABLISHED_BACKUP_TRANSPORT_CHANGED",
    )
    public = Path("/etc/onesa/recovery-public.pem")
    require(
        not public.is_symlink()
        and public.stat().st_uid == 0
        and not public.stat().st_mode & 0o022
        and sha(public) == profile["key_id"] == receipt["key_id"],
        "RECOVERY_PUBLIC_KEY_CHANGED",
    )
    require(
        receipt["product"] == "ai"
        and receipt["off_instance_storage_verified"] is True
        and re.fullmatch(
            r"\.onesa-database-backups/v1/ai/[a-f0-9]{32}\.json", receipt["object_key"]
        ),
        "AI_BACKUP_IDENTITY",
    )
    values = runtime_values(Path(profile["transport_env"]))
    keys = [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "S3_ENDPOINT",
        "S3_REGION",
        "S3_BUCKET",
    ]
    selected = {k: values[k] for k in keys if k in values}
    require(
        {
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "S3_ENDPOINT",
            "S3_REGION",
            "S3_BUCKET",
        }
        <= set(selected),
        "EXISTING_AI_BACKUP_S3_CUSTODY",
    )
    with tempfile.TemporaryDirectory(prefix=".backup-readback-", dir=ROOT) as folder:
        env = Path(folder) / "transport.env"
        with os.fdopen(
            os.open(env, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600),
            "w",
        ) as f:
            f.write("".join(k + "=" + v + "\n" for k, v in selected.items()))
        objects = [
            (receipt["object_key"], receipt["ciphertext_sha256"]),
            (profile["escrow_object"], profile["escrow_ciphertext_sha256"]),
        ]
        for key, expected in objects:
            require(
                re.fullmatch(
                    r"\.onesa-(?:database-backups/v1/ai/[a-f0-9]{32}\.json|portal-backups/v1/keys/[a-f0-9]{64}\.enc)",
                    key,
                ),
                "ESTABLISHED_BACKUP_OBJECT_SCOPE",
            )
            raw = docker(
                "run",
                "--rm",
                "-i",
                "--pull=never",
                "--read-only",
                "--tmpfs",
                "/tmp",
                "--memory",
                "256m",
                "--cpus",
                "0.1",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges:true",
                "--env-file",
                str(env),
                "-v",
                str(script) + ":/app/backup.mjs:ro",
                "--entrypoint",
                "node",
                profile["transport_image"],
                "/app/backup.mjs",
                data=canonical({"action": "read", "key": key}),
                timeout=90,
            )
            require(
                hashlib.sha256(raw).hexdigest() == expected,
                "BACKUP_OR_ESCROW_CIPHERTEXT_DIFFERS",
            )
    return {
        "database_ciphertext_sha256": receipt["ciphertext_sha256"],
        "key_id": receipt["key_id"],
        "escrow_ciphertext_sha256": profile["escrow_ciphertext_sha256"],
        "actual_off_instance_readback": "PASS",
        "key_custody_changed": False,
        "production_restore_performed": False,
    }


MIGRATION_PROGRAM = r"""import json,sys,re,os
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from alembic.config import Config
from alembic import command
from urllib.parse import urlsplit
request=json.load(sys.stdin)
target=request.get('target_revision','20261025_twins')
assert target in ['20261025_twins','20261026_cybersecurity']
role=urlsplit(request['runtime']).username
assert re.fullmatch('[a-z_][a-z0-9_]{0,62}',role)
owner=make_url(request['owner']).set(drivername='postgresql+psycopg')
engine=create_engine(owner,connect_args={'connect_timeout':10,'sslmode':'verify-full','sslrootcert':'/etc/ssl/cert.pem','channel_binding':'require'})
with engine.begin() as connection:
 revision=connection.scalar(text('SELECT version_num FROM alembic_version'))
 assert revision in ['20261010_capacity','20261021_industrial','20261025_twins','20261026_cybersecurity']
 assert revision!='20261026_cybersecurity' or target=='20261026_cybersecurity'
 assert connection.scalar(text("SELECT has_schema_privilege(current_user,'public','CREATE') AND pg_has_role(current_user,c.relowner,'USAGE') FROM pg_class c WHERE c.oid='alembic_version'::regclass"))
 config=Config('alembic.ini');config.attributes['connection']=connection
 # env.py requires the URL even when the already verified connection is supplied.
 # This stays inside this short-lived process; it is not a Docker argument/env-file.
 os.environ['ONESA_DATABASE_URL']=owner.render_as_string(hide_password=False)
 command.upgrade(config,target)
 tables=['industrial_investigations','twin_files','twin_templates','twin_assets','twin_models','twin_notes','twin_sources','twin_readings','twin_events']
 if target=='20261026_cybersecurity':tables+=['cyber_assets','cyber_sources','cyber_mappings','cyber_policies','cyber_baselines','cyber_events','cyber_findings','cyber_results','cyber_investigations','cyber_actions','cyber_reports','cyber_summaries']
 connection.execute(text('GRANT SELECT,INSERT,UPDATE,DELETE ON TABLE '+','.join('public.'+table for table in tables)+' TO "'+role+'"'))
 assert not connection.scalar(text("SELECT has_schema_privilege(:role,'public','CREATE') OR has_table_privilege(:role,'alembic_version','INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER')"),{'role':role})
 assert connection.scalar(text('SELECT version_num FROM alembic_version'))==target
print(json.dumps({'migration_revision':target,'runtime_DDL_granted':False,'runtime_new_tables_DML_granted':len(tables)}))
"""


def migrate(binding, env, operation, plan):
    # Exact reviewed forward migrations and scoped table DML. No
    # runtime CREATE, role membership or migration-table permission is granted.
    owner = runtime_values(Path("/etc/onesa/backends/ai-" + env + "-migration.env"))
    current = runtime_values(ENV[env])
    request = {
        "owner": owner["ONESA_DATABASE_URL"],
        "runtime": current["ONESA_DATABASE_URL"],
        "target_revision": plan["migration_revision"],
    }
    raw = docker(
        "run",
        "--rm",
        "-i",
        "--network",
        "host",
        "--read-only",
        "--tmpfs",
        "/tmp",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--entrypoint",
        "python",
        binding["artifact_digest"],
        "-c",
        MIGRATION_PROGRAM,
        data=canonical(request),
        timeout=180,
    )
    result = json.loads(raw)
    require(
        result
        == {
            "migration_revision": plan["migration_revision"],
            "runtime_DDL_granted": False,
            "runtime_new_tables_DML_granted": 21
            if plan["migration_revision"] == "20261026_cybersecurity"
            else 9,
        },
        "ADDITIVE_MIGRATION_OR_ROLE_SCOPE_FAILED",
    )
    return result


def update_backup_runtime_binding(binding, env, operation, op, plan):
    config = Path("/etc/onesa/database-backups.json")
    previous = private(config).read_bytes()
    index = json.loads(previous)
    require(
        index["products"]["ai"]["runtime_sha256"]
        == plan["baseline_runtime_sha256"][env],
        "ESTABLISHED_BACKUP_RUNTIME_BINDING_CHANGED",
    )
    write_raw(op / "previous-database-backups.json", previous)
    index["products"]["ai"]["runtime_sha256"] = binding["configuration_sha256"][env]
    temporary = config.with_name(config.name + "." + operation)
    write(temporary, index)
    os.replace(temporary, config)
    sync_directory(config.parent)


def activate(binding, env, operation, folder, plan):
    if env == "production" and plan["mode"] != "foundation":
        with backup_lock():
            return _activate(binding, env, operation, folder, plan)
    return _activate(binding, env, operation, folder, plan)


def _activate(binding, env, operation, folder, plan):
    require(str(UUID(operation)) == operation, "OPERATION_UUID")
    before = inventory()
    name = TARGET[env]
    require(healthy(before[name]), "TARGET_UNHEALTHY_BEFORE_CHANGE")
    expected = plan["baseline"][env]
    require(summary(before[name]) == expected, "TARGET_CHANGED_SINCE_PREPARATION")
    prepare_artifact_directories(folder)
    op = folder / "operations" / operation
    op.mkdir(mode=0o700, parents=False, exist_ok=False)
    oldbytes = private(IMAGES).read_bytes()
    values = runtime_values(IMAGES)
    prefix = "ORACLE_" + env.upper()
    require(
        values[prefix + "_IMAGE"] == before[name]["Image"]
        and values[prefix + "_COMMIT"] == expected["source"],
        "CURRENT_IMAGE_MAP_CHANGED",
    )
    write(
        op / "intent.json",
        {
            "binding": binding,
            "environment": env,
            "operation_id": operation,
            "before": {n: summary(r) for n, r in before.items()},
            "provider_request_budget": 1,
            "automatic_retry": False,
        },
    )
    old_runtime = private(ENV[env]).read_bytes()
    require(
        sha(ENV[env]) == plan["baseline_runtime_sha256"][env],
        "CURRENT_RUNTIME_FILE_CHANGED_SINCE_PREPARATION",
    )
    with os.fdopen(
        os.open(
            op / "previous-runtime.env",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        ),
        "wb",
    ) as f:
        f.write(old_runtime)
        f.flush()
        os.fsync(f.fileno())
    if plan["mode"] != "foundation":
        migrate(binding, env, operation, plan)
    next_runtime = ENV[env].with_name(ENV[env].name + "." + operation)
    with os.fdopen(
        os.open(
            next_runtime, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
        ),
        "wb",
    ) as f:
        f.write(private(candidate_environment(binding, env)).read_bytes())
        f.flush()
        os.fsync(f.fileno())
    sync_directory(op)
    os.replace(next_runtime, ENV[env])
    sync_directory(ENV[env].parent)
    if env == "production" and plan["mode"] != "foundation":
        update_backup_runtime_binding(binding, env, operation, op, plan)
    with os.fdopen(
        os.open(
            op / "previous-images.env",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        ),
        "wb",
    ) as f:
        f.write(oldbytes)
        f.flush()
        os.fsync(f.fileno())
    updates = {
        prefix + "_IMAGE": binding["artifact_digest"],
        prefix + "_COMMIT": binding["candidate_commit"],
    }
    new = "\n".join(k + "=" + updates.get(k, v) for k, v in values.items()) + "\n"
    temp = IMAGES.with_name(IMAGES.name + "." + operation)
    with os.fdopen(
        os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb"
    ) as f:
        f.write(new.encode())
        f.flush()
        os.fsync(f.fileno())
    sync_directory(op)
    os.replace(temp, IMAGES)
    sync_directory(IMAGES.parent)
    args = [
        "/usr/bin/docker",
        "compose",
        "--env-file",
        str(IMAGES),
        "-f",
        str(COMPOSE),
        "--profile",
        env,
        "up",
        "-d",
        "--no-build",
        "--no-deps",
        "--wait",
        "--wait-timeout",
        "120",
        env,
    ]
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            timeout=360,
            check=False,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
        )
        provider_exit = result.returncode
    except subprocess.TimeoutExpired:
        provider_exit = None
    after = inventory()
    actual = after[name]
    receipt = {
        "binding": binding,
        "operation_id": operation,
        "deployment_id": actual["Id"],
        "provider_exit": provider_exit,
        "actual": summary(actual),
        "observed_at": now().isoformat(),
        "independent_after": {n: summary(row) for n, row in after.items() if n != name},
    }
    write(op / "provider-receipt.json", receipt)
    require(
        healthy(actual)
        and actual["Image"] == binding["artifact_digest"]
        and actual["Config"]["Labels"]["org.onesa.source-commit"]
        == binding["candidate_commit"],
        "PROVIDER_REQUEST_NOT_ACCEPTED_INSPECT_EXISTING_OPERATION",
    )
    actual_values = dict(v.split("=", 1) for v in actual["Config"]["Env"])
    require(
        all(
            actual_values.get(k) == v
            for k, v in runtime_values(candidate_environment(binding, env)).items()
        ),
        "ACTUAL_CONTAINER_CONFIGURATION_DIFFERS",
    )
    unchanged(before, after, [name])
    return receipt


def backend_identity(binding, env):
    program = "import json,os,urllib.request;print(urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/health',timeout=5).read().decode())"
    value = json.loads(docker("exec", TARGET[env], "python", "-c", program, timeout=15))
    require(
        value.get("status") == "ok"
        and value.get("source_commit") == binding["candidate_commit"]
        and value.get("source_archive_sha256") == binding["source_sha256"]
        and re.fullmatch("[a-f0-9]{64}", value.get("instance_id", "")),
        "RUNNING_BACKEND_BUILD_IDENTITY_MISMATCH",
    )
    return value


def running_configuration(binding, env, actual):
    require(env in ENV, "RUNTIME_ENVIRONMENT_SCOPE")
    path = private(ENV[env])
    require(
        sha(path) == binding["configuration_sha256"][env],
        "RUNNING_CONFIGURATION_FILE_BINDING",
    )
    configured = runtime_values(path)
    rows = actual["Config"]["Env"]
    require(
        isinstance(rows, list)
        and all(isinstance(row, str) and "=" in row for row in rows),
        "RUNNING_CONFIGURATION_SHAPE",
    )
    live = dict(row.split("=", 1) for row in rows)
    require(
        len(live) == len(rows)
        and all(live.get(key) == value for key, value in configured.items()),
        "RUNNING_CONFIGURATION_DIFFERS_FROM_BOUND_FILE",
    )
    return configured


def extract_reference(folder, destination, binding):
    _app, index = source_inventory(private(folder / "source.tar"), binding)
    destination.mkdir(mode=0o700)
    prefix = "onesa-ai-platform-backend/app/twin_fixture_data/"
    with tarfile.open(folder / "source.tar") as archive:
        for name in ["manifest.json", "pump.glb", "maintenance.txt"]:
            member = archive.getmember(prefix + name)
            require(
                member.isfile() and 0 < member.size <= 4194304, "REFERENCE_DATA_BOUND"
            )
            data = archive.extractfile(member).read()
            require(
                hashlib.sha256(data).hexdigest() == index[prefix + name],
                "CANDIDATE_REFERENCE_DATA_CHANGED",
            )
            with os.fdopen(
                os.open(
                    destination / name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                ),
                "wb",
            ) as f:
                f.write(data)


def required_probe_checks(binding, env, mode, enabled_features=None):
    require(mode in {"foundation", "twins", "cybersecurity"}, "UNKNOWN_PROBE_MODE")
    profiles.bound_mode(binding, mode)
    require(env in {"staging", "production"}, "UNKNOWN_PROBE_ENVIRONMENT")
    features = (
        (frozenset() if mode == "foundation" else frozenset({mode}))
        if enabled_features is None
        else frozenset(enabled_features)
    )
    require(
        features <= {"twins", "cybersecurity"}
        and (not features if mode == "foundation" else mode in features),
        "ACTUAL_ENABLED_FEATURE_SCOPE_REQUIRED",
    )
    mandatory = {
        "authentication",
        "owner_isolation",
        "tls",
        "chat_knowledge_retained",
        "database_persistence",
        "session_persistence",
    }
    if "twins" in features:
        mandatory |= {
            "twins_model_delivery",
            "twins_saved_state",
            "optional_sources_absent",
            "file_persistence",
        }
    if "cybersecurity" in features:
        mandatory |= {
            "cybersecurity_scoped_readiness",
            "cybersecurity_ingestion",
            "cybersecurity_findings",
            "cybersecurity_decisions",
            "cybersecurity_native_configuration",
            "cybersecurity_revocation",
            "cybersecurity_export",
            "optional_sources_absent",
        }
        if (
            profiles.kind(binding) == "frontend"
            or env == "staging"
            or profiles.component(binding) not in profiles.LEGACY
        ):
            mandatory.add("cybersecurity_ui")
    if mode == "foundation":
        require(mode == "foundation", "UNKNOWN_PROBE_MODE")
        mandatory |= {"twins_disabled", "cybersecurity_disabled", "ordinary_workflows"}
    if "twins" in features and (
        (env == "staging" and profiles.kind(binding) == "frontend")
        or profiles.component(binding) not in profiles.LEGACY
    ):
        mandatory.add("twins_inspection")
    return mandatory


def require_probe_policy(binding, env, plan, enabled):
    mandatory = required_probe_checks(binding, env, plan["mode"], enabled)
    required = plan.get("mandatory_probe_checks", {}).get(env)
    require(
        isinstance(required, list)
        and all(isinstance(key, str) for key in required)
        and len(set(required)) == len(required)
        and mandatory <= set(required),
        "INCOMPLETE_HOSTED_POLICY",
    )
    return set(required)


def verify_observed_features(binding, observed, mode, enabled):
    # Previously accepted legacy receipts predate the explicit feature-set field.
    # They can cover only their original, single mode with the same live flags.
    # They never qualify a new named profile or a combined-feature runtime.
    if "enabled_features" not in observed:
        original = set() if mode == "foundation" else {mode}
        require(
            profiles.component(binding) in profiles.LEGACY and set(enabled) == original,
            "LEGACY_RECEIPT_CANNOT_COVER_NEW_FEATURE_SCOPE",
        )
    else:
        require(
            observed["enabled_features"] == sorted(enabled),
            "OBSERVED_FEATURE_SCOPE_CHANGED",
        )


def probe_cpu_limit():
    """Fit the bounded probe to the actual daemon; never request new capacity."""
    value = docker("info", "--format", "{{.NCPU}}", timeout=15).strip()
    require(re.fullmatch(rb"[1-9][0-9]{0,3}", value), "PROBE_HOST_CPU_UNVERIFIED")
    return str(min(2, int(value)))


def probe_network():
    """Use the existing bridge namespace, never the host's interface notifications."""
    value = json.loads(docker("network", "inspect", "bridge", timeout=15))
    require(
        isinstance(value, list)
        and len(value) == 1
        and isinstance(value[0], dict)
        and value[0].get("Name") == "bridge"
        and value[0].get("Driver") == "bridge"
        and value[0].get("Scope") == "local"
        and value[0].get("Internal") is False,
        "ISOLATED_OUTBOUND_PROBE_NETWORK_REQUIRED",
    )
    return "bridge"


def probe(binding, env, operation, folder, plan, *, plan_file=None):
    cpus = probe_cpu_limit()
    network = probe_network()
    plan_file = plan_path(binding) if plan_file is None else private(Path(plan_file))
    installed_plan = read(plan_file)
    require(
        installed_plan["binding"] == binding
        and all(
            installed_plan[key] == plan[key]
            for key in ["mode", "expected_schema_revision", "mandatory_probe_checks"]
        ),
        "PROBE_PLAN_FILE_BINDING",
    )
    name = TARGET[env]
    current = inventory()
    actual = current[name]
    runtime_binding = plan.get("api_binding", binding)
    require(
        healthy(actual)
        and actual["Image"] == runtime_binding["artifact_digest"]
        and actual["Config"]["Labels"]["org.onesa.source-commit"]
        == runtime_binding["candidate_commit"],
        "ACTUAL_RUNTIME_IDENTITY",
    )
    values = running_configuration(runtime_binding, env, actual)
    enabled = profiles.enabled_features(values, plan["mode"])
    required = require_probe_policy(binding, env, plan, enabled)
    if "twins" in enabled:
        mounts = actual.get("Mounts", [])
        require(
            any(
                m["Type"] == "bind"
                and m["Source"] == plan["storage"][env]
                and m["Destination"] == "/var/lib/onesa/twins"
                and m["RW"]
                for m in mounts
            ),
            "PRIVATE_DURABLE_MOUNT_MISSING",
        )
    output = folder / "observations" / operation
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    if "twins" in enabled:
        extract_reference(folder, output / "reference", binding)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import oracle_ai_frontend

    metadata = oracle_ai_frontend.observe_provider(binding, env, plan, operation)
    if (
        env == "production"
        and profiles.kind(binding) == "api"
        and profiles.component(binding) not in profiles.LEGACY
    ):
        metadata["retained_frontend"] = oracle_ai_frontend.verify_retained_frontend(
            binding, plan, metadata
        )
    metadata["backend_identity"] = backend_identity(runtime_binding, env)
    write(output / "private-provider-observation.json", metadata)
    narrowed = output / "private-runtime.env"
    with os.fdopen(
        os.open(narrowed, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600),
        "w",
    ) as f:
        f.write(
            "".join(
                k + "=" + values[k] + "\n"
                for k in [
                    "ONESA_DATABASE_URL",
                    "ONESA_ENVIRONMENT",
                    "ONESA_PUBLIC_ORIGIN",
                ]
            )
        )
        for key in ["ONESA_DIGITAL_TWINS_ENABLED", "ONESA_CYBERSECURITY_ENABLED"]:
            f.write(key + "=" + values.get(key, "false") + "\n")
    # This immutable, credential-free-built probe image contains the reviewed
    # existing hosted API/UI harnesses and the owned Twins journey. It observes the
    # actual provider and application; no caller PASS or stored Actions artifact is read.
    args = [
        "/usr/bin/docker",
        "run",
        "--rm",
        "-i",
        "--read-only",
        "--network",
        network,
        "--tmpfs",
        "/tmp:rw,mode=700,size=512m",
        "--memory",
        "2g",
        "--cpus",
        cpus,
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "-v",
        str(plan_file) + ":/private/plan.json:ro",
        "-v",
        str(narrowed) + ":/private/runtime.env:ro",
        "-v",
        str(output / "private-provider-observation.json") + ":/private/vercel.json:ro",
        "-v",
        str(plan["preview_receipt_path"]) + ":/private/frontend-preview.json:ro",
        *(
            [
                "-v",
                str(output / "reference") + ":/private/reference:ro",
            ]
            if "twins" in enabled
            else []
        ),
        "-v",
        str(output) + ":/private/output:rw",
        "--entrypoint",
        "python3",
        plan["probe_image"],
        "/opt/onesa-ai-platform/scripts/release/oracle_ai_probe.py",
        env,
    ]
    data = canonical(
        {
            "binding": binding,
            "operation_id": operation,
            "plan_sha256": sha(plan_file),
            "ci_run_id": plan["observed_ci_run_id"],
            "frontend_deployment_id": plan.get("current_frontend_deployment_id"),
            "provider_observation_sha256": sha(
                output / "private-provider-observation.json"
            ),
        }
    )
    # The process output is private and bounded after completion. A durable marker
    # coordinates one staging replacement; no provider request is retried.
    stdout = output / "producer.stdout"
    stderr = output / "producer.stderr"
    with stdout.open("xb") as out, stderr.open("xb") as err:
        os.chmod(stdout, 0o600)
        os.chmod(stderr, 0o600)
        process = subprocess.Popen(
            [*args, "--stdin-request"],
            stdin=subprocess.PIPE,
            stdout=out,
            stderr=err,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
        )
        process.stdin.write(data)
        process.stdin.close()
        deadline = time.monotonic() + 1800
        handled = False
        try:
            while process.poll() is None:
                require(time.monotonic() < deadline, "HOSTED_PROBE_DEADLINE")
                if (
                    env == "staging"
                    and profiles.kind(binding) == "api"
                    and not handled
                    and (output / "prepared-for-replacement.json").exists()
                ):
                    prepared = read(output / "prepared-for-replacement.json")
                    require(
                        prepared["binding"] == binding
                        and prepared["operation_id"] == operation
                        and prepared["environment"] == env,
                        "REPLACEMENT_MARKER_BINDING",
                    )
                    sys.path.insert(0, str(Path(__file__).resolve().parent))
                    import oracle_twin_restore

                    if plan["mode"] in ["twins", "cybersecurity"]:
                        if plan["mode"] == "twins":
                            oracle_twin_restore.capture_fixture_files(
                                output, binding, operation, plan["storage"][env]
                            )
                        oracle_twin_restore.restore(output, binding, operation)
                    else:
                        import oracle_forward_check

                        oracle_forward_check.check(output, binding, operation)
                    before = inventory()
                    old = before[name]
                    write(
                        output / "replacement-intent.json",
                        {
                            "binding": binding,
                            "operation_id": operation,
                            "old_container": old["Id"],
                            "provider_request_budget": 1,
                            "automatic_retry": False,
                        },
                    )
                    docker(
                        "compose",
                        "--env-file",
                        str(IMAGES),
                        "-f",
                        str(COMPOSE),
                        "--profile",
                        "staging",
                        "up",
                        "-d",
                        "--no-build",
                        "--no-deps",
                        "--force-recreate",
                        "--wait",
                        "--wait-timeout",
                        "120",
                        "staging",
                        timeout=180,
                    )
                    after = inventory()
                    new = after[name]
                    require(
                        new["Id"] != old["Id"]
                        and healthy(new)
                        and new["Image"] == binding["artifact_digest"],
                        "STAGING_REPLACEMENT_FAILED_INSPECT_ONLY",
                    )
                    unchanged(before, after, [name])
                    write(
                        output / "replacement-ok.json",
                        {
                            "binding": binding,
                            "operation_id": operation,
                            "old_container": old["Id"],
                            "new_container": new["Id"],
                            "image_digest": new["Image"],
                            "backend_identity": backend_identity(binding, env),
                            "restore_receipt_sha256": sha(
                                output
                                / (
                                    "restore-receipt.json"
                                    if plan["mode"] != "foundation"
                                    else "forward-check-receipt.json"
                                )
                            ),
                        },
                    )
                    handled = True
                time.sleep(0.25)
            require(
                process.returncode == 0 and stdout.stat().st_size <= 8 * 1024 * 1024,
                "HOSTED_PRODUCER_FAILED_INSPECT_PRIVATE_RECEIPT",
            )
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=20)
            narrowed.unlink(missing_ok=True)
            (output / "private-provider-observation.json").unlink(missing_ok=True)
    observed = json.loads(stdout.read_bytes())
    require(
        observed["binding"] == binding
        and observed["operation_id"] == operation
        and observed["workflow_run_id"] == 0
        and observed["environment"] == env,
        "HOSTED_PROBE_BINDING_MISMATCH",
    )
    require(
        observed["enabled_features"] == sorted(enabled)
        and set(observed["checks"]) >= required
        and all(observed["checks"][k] == "PASS" for k in required),
        "HOSTED_REQUIRED_CHECK_FAILED_SKIPPED_OR_MISSING",
    )
    require(
        observed["fixture_identities_disabled"] is True
        and observed["existing_records_preserved"] is True,
        "FIXTURE_CLEANUP_OR_PRESERVATION_FAILED",
    )
    after_provider = oracle_ai_frontend.observe_provider(binding, env, plan, operation)
    require(
        after_provider["provider"] == metadata["provider"]
        and after_provider["origin"] == metadata["origin"],
        "FRONTEND_PROVIDER_CHANGED_DURING_PROBE",
    )
    unchanged(current, inventory(), [name] if env == "staging" else [])
    actual = inventory()[name]
    identity = backend_identity(runtime_binding, env)
    require(
        observed["backend_identity"] == identity,
        "SERVED_BACKEND_DIFFERS_FROM_RUNNING_CONTAINER",
    )
    return {
        "runtime": summary(actual),
        "deployment_id": actual["Id"],
        "hosted": observed,
        "receipt_sha256": sha(output / "receipt.json"),
    }


def observe_production(binding, operation, folder, plan):
    # Read-only reconciliation. No identity creation, migration or restart here.
    op = folder / "operations" / operation
    intent = read(op / "intent.json")
    receipt = read(op / "provider-receipt.json")
    require(
        intent["binding"] == binding
        and receipt["binding"] == binding
        and intent["operation_id"] == operation
        and receipt["operation_id"] == operation,
        "DEPLOYMENT_OPERATION_BINDING",
    )
    current = inventory()
    actual = current[TARGET["production"]]
    require(
        healthy(actual)
        and actual["Id"] == receipt["deployment_id"]
        and actual["Image"] == binding["artifact_digest"]
        and summary(actual)["source"] == binding["candidate_commit"],
        "ACTUAL_PRODUCTION_IDENTITY_OR_HEALTH",
    )
    require(
        receipt["independent_after"]
        == {
            name: row
            for name, row in intent["before"].items()
            if name != TARGET["production"]
        },
        "DEPLOYMENT_PRESERVATION_PROOF_MISSING",
    )
    output = folder / "observations" / operation
    observed = read(output / "receipt.json")
    require(
        observed == read(output / "producer.stdout")
        and observed["binding"] == binding
        and observed["environment"] == "production"
        and observed["operation_id"] == operation
        and observed["status"] == "PASS"
        and observed["workflow_run_id"] == 0
        and observed["fixture_identities_disabled"] is True
        and observed["existing_records_preserved"] is True,
        "POST_DEPLOY_WORKFLOWS_NOT_VERIFIED",
    )
    enabled = profiles.enabled_features(
        running_configuration(binding, "production", actual), plan["mode"]
    )
    required = require_probe_policy(binding, "production", plan, enabled)
    verify_observed_features(binding, observed, plan["mode"], enabled)
    require(
        all(observed["checks"].get(k) == "PASS" for k in required),
        "PRODUCTION_CHECK_FAILED_SKIPPED_OR_MISSING",
    )
    require(
        dt.datetime.fromisoformat(observed["observed_at"])
        >= dt.datetime.fromisoformat(receipt["observed_at"]),
        "WORKFLOWS_PREDATE_DEPLOYMENT",
    )
    if plan["mode"] != "foundation":
        operational_observations(binding, plan)
    require(
        observed["backend_identity"] == backend_identity(binding, "production"),
        "CURRENT_SERVED_API_IDENTITY_REQUIRED",
    )
    return {
        "deployment_id": actual["Id"],
        "runtime": summary(actual),
        "hosted_receipt_sha256": sha(output / "receipt.json"),
        "provider_receipt_sha256": sha(op / "provider-receipt.json"),
        "fresh_health_readback": True,
        "read_only_observer": True,
    }


def record_runner_failure(phase, request, error):
    """Bounded diagnostics only; never an approval or a retry allowance."""
    try:
        require(phase in {*CHECKS, "preflight"}, "PHASE_SCOPE")
        binding = request["binding"]
        require(
            binding["repository"] == "DruHustle/onesa-ai-platform"
            and profiles.kind(binding) == "api"
            and re.fullmatch(r"[a-f0-9]{40}", binding["candidate_commit"]),
            "FAILURE_SOURCE_SCOPE",
        )
        folder = private(artifact_folder(binding), directory=True)
        failures = folder / "failures"
        failures.mkdir(mode=0o700, exist_ok=True)
        private(failures, directory=True)
        code = (
            str(error)
            if type(error).__name__ == "Refused"
            and re.fullmatch(r"[A-Z0-9_]{1,120}", str(error))
            else type(error).__name__
        )
        ids = {
            key: value
            for key, value in request.get("context", {}).items()
            if key
            in {"context_id", "operation_id", "authorization_id", "qualification_id"}
            and isinstance(value, str)
            and re.fullmatch(r"[a-f0-9-]{36}", value)
        }
        write(
            failures / (phase + "-" + str(time.time_ns()) + ".json"),
            {
                "status": "FAILED_NOT_QUALIFIED",
                "diagnostic_only": True,
                "candidate_commit": binding["candidate_commit"],
                "component": binding["component"],
                "phase": phase,
                "record_ids": ids,
                "failure_code": code,
                "observed_at": now().isoformat(),
                "provider_retry_allowed": False,
            },
        )
    except (ValueError, TypeError, KeyError, OSError):
        pass


def run_request(phase, request):
    binding = request["binding"]
    context = request["context"]
    if phase == "preflight":
        print(json.dumps(preflight(binding)))
        return
    require(phase in CHECKS, "PHASE_SCOPE")
    folder, plan = validate_plan(binding)
    signed_chain = verify_invocation(binding, context, phase, plan)
    ci = next(
        (
            record["details"]["ci"]
            for record in signed_chain
            if record["kind"] == "context"
        ),
        None,
    )
    require(
        ci
        and any(
            row.get("workflow") == "ci.yml"
            and type(row.get("run_id")) is int
            and row["run_id"] > 0
            for row in ci
        ),
        "SIGNED_GENUINE_CI_REFERENCE_MISSING",
    )
    plan["qualification_context_id"] = next(
        record["id"] for record in signed_chain if record["kind"] == "context"
    )
    plan["artifact_folder"] = str(folder)
    import oracle_ai_frontend

    plan["preview_receipt_path"] = str(
        oracle_ai_frontend.preview_receipt_path(
            binding, plan["qualification_context_id"]
        )
    )
    plan["observed_ci_run_id"] = next(
        row["run_id"] for row in ci if row.get("workflow") == "ci.yml"
    )
    migration_prerequisites(plan)
    if phase == "operations":
        details = operational_observations(binding, plan)
    elif phase == "staging":
        operation = context["context_id"]
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import oracle_ai_frontend

        plan["preview_receipt_path"] = str(
            oracle_ai_frontend.prepare_preview(binding, context)
        )
        activate(binding, "staging", operation, folder, plan)
        details = probe(binding, "staging", operation, folder, plan)
    elif phase == "deploy":
        stage = inventory()[TARGET["staging"]]
        require(
            healthy(stage) and stage["Image"] == binding["artifact_digest"],
            "MATCHING_STAGING_ARTIFACT_REQUIRED",
        )
        operational_observations(binding, plan)
        operation = context["operation_id"]
        details = activate(binding, "production", operation, folder, plan)
        try:
            details["hosted_verification"] = probe(
                binding, "production", operation, folder, plan
            )
            backup = post_deployment_backup(binding, plan)
            if backup is not None:
                details["post_deploy_backup"] = backup
        except Exception as error:  # noqa: BLE001 -- Preserve a real provider receipt even when post-deploy checks fail.
            details["verification_state"] = "FAILED_OR_INTERRUPTED"
            details["failure_category"] = type(error).__name__
    else:
        operation = context["operation_id"]
        details = observe_production(binding, operation, folder, plan)
    print(
        json.dumps(
            {
                "binding": binding,
                "workflow_run_id": 0,
                "environment": "staging" if phase == "staging" else "production",
                "observed_at": now().isoformat(),
                "checks": {k: "PASS" for k in CHECKS[phase]},
                "observations": details,
                "operation_id": context.get("operation_id"),
                "deployment_id": details.get("deployment_id"),
            }
        )
    )


def main():
    require(
        os.geteuid() == 0 and not os.getenv("GITHUB_ACTIONS"), "EXTERNAL_OWNER_ONLY"
    )
    require(len(sys.argv) == 2, "ONE_RUNNER_PHASE_REQUIRED")
    phase = sys.argv[1]
    raw = sys.stdin.buffer.read(131073)
    require(len(raw) <= 131072, "REQUEST_BOUND")
    request = json.loads(raw)
    try:
        run_request(phase, request)
    except Exception as error:  # noqa: BLE001 -- Redact and preserve failures before or during the hosted producer.
        record_runner_failure(phase, request, error)
        raise Refused("PINNED_RUNNER_FAILED_INSPECT_RETAINED_DIAGNOSTIC") from None


if __name__ == "__main__":
    try:
        main()
    except Refused as error:
        raise SystemExit("Oracle AI prerequisite: " + str(error)) from None
    except Exception:  # noqa: BLE001 -- CLI boundary redacts private input and provider diagnostics.
        raise SystemExit(
            "Oracle AI operation refused; inspect private prerequisites and retained operation; no automatic retry"
        ) from None
