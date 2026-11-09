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
import urllib.parse
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
IDENTITY_CREDENTIALS = Path("/run/onesa-release/ai-identity.json")
IDENTITY_KEYS = frozenset(
    {
        "ONESA_IDENTITY_ENABLED",
        "ONESA_IDENTITY_ISSUER",
        "ONESA_IDENTITY_CLIENT_ID",
        "ONESA_IDENTITY_CLIENT_SECRET",
        "ONESA_IDENTITY_CALLBACK_URL",
        "ONESA_IDENTITY_ENCRYPTION_KEY",
    }
)
IDENTITY_SCHEMA = "20261102_shared_identity"
MAIL_PRESENTATION_SCHEMA = "20261104_email_presentation"
IDENTITY_SCHEMAS = frozenset({IDENTITY_SCHEMA, MAIL_PRESENTATION_SCHEMA})
IDENTITY_CHECKS = frozenset(
    {
        "shared_identity_pkce",
        "shared_identity_mfa",
        "identity_cookie_isolation",
        "identity_local_mapping",
        "identity_fixture_preservation",
        "identity_sessions_retired",
    }
)
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


def identity_profile(binding, plan):
    """Validate nonsecret identity metadata from the installed, source-bound plan."""
    require(
        profiles.component(binding) in profiles.IDENTITY
        and plan.get("mode") == "identity",
        "EXPLICIT_SHARED_IDENTITY_PROFILE_REQUIRED",
    )
    identity = plan.get("identity")
    require(
        isinstance(identity, dict)
        and set(identity)
        == {
            "profile",
            "source_commit",
            "source_tree",
            "source_sha256",
            "credentials_sha256",
            "environments",
        }
        and identity["profile"] == "shared-identity-v1"
        and all(
            identity[key] == binding[field]
            for key, field in [
                ("source_commit", "candidate_commit"),
                ("source_tree", "source_tree"),
                ("source_sha256", "source_sha256"),
            ]
        )
        and isinstance(identity["credentials_sha256"], str)
        and re.fullmatch("[a-f0-9]{64}", identity["credentials_sha256"])
        and isinstance(identity["environments"], dict)
        and set(identity["environments"]) == set(ENV),
        "SOURCE_BOUND_IDENTITY_PROFILE_REQUIRED",
    )
    for environment, value in identity["environments"].items():
        require(
            isinstance(value, dict)
            and set(value)
            == {
                "issuer",
                "client_id",
                "client_secret_sha256",
                "encryption_key_sha256",
                "callback_url",
                "portal_bypass_sha256",
                "accounts",
            }
            and all(
                isinstance(value[key], str) and re.fullmatch("[a-f0-9]{64}", value[key])
                for key in [
                    "client_secret_sha256",
                    "encryption_key_sha256",
                    "portal_bypass_sha256",
                ]
            )
            and isinstance(value["client_id"], str)
            and re.fullmatch("[A-Za-z0-9_-]{16,128}", value["client_id"]),
            "BOUNDED_IDENTITY_ENVIRONMENT_PROFILE_REQUIRED",
        )
        issuer = urllib.parse.urlsplit(value["issuer"])
        callback = urllib.parse.urlsplit(value["callback_url"])
        require(
            issuer.scheme == callback.scheme == "https"
            and not any(
                (
                    issuer.username,
                    issuer.password,
                    issuer.query,
                    issuer.fragment,
                    callback.username,
                    callback.password,
                    callback.query,
                    callback.fragment,
                )
            )
            and issuer.port is None
            and callback.port is None
            and issuer.path == "/api/v1/identity"
            and callback.path == "/api/v1/auth/onesa/callback"
            and issuer.netloc == issuer.hostname
            and callback.netloc == callback.hostname,
            "FIXED_HTTPS_IDENTITY_ENDPOINTS_REQUIRED",
        )
        if environment == "production":
            require(
                issuer.hostname == "portal.onesa.eu"
                and callback.hostname == "platform.onesa.eu"
                and value["portal_bypass_sha256"] == hashlib.sha256(b"").hexdigest(),
                "CANONICAL_PRODUCTION_IDENTITY_ENDPOINTS_REQUIRED",
            )
        else:
            require(
                (
                    issuer.hostname == "portal-staging.onesa.eu"
                    or re.fullmatch(
                        r"onesa-company-portal-[a-z0-9-]+\.vercel\.app",
                        issuer.hostname or "",
                    )
                )
                and (
                    callback.hostname == "platform-staging.onesa.eu"
                    or re.fullmatch(
                        r"onesa-ai-[a-z0-9-]+\.vercel\.app", callback.hostname or ""
                    )
                ),
                "ISOLATED_STAGING_IDENTITY_ENDPOINTS_REQUIRED",
            )
        accounts = value["accounts"]
        require(
            isinstance(accounts, dict) and set(accounts) == {"primary", "foreign"},
            "TWO_OWNED_IDENTITY_FIXTURES_REQUIRED",
        )
        for account in accounts.values():
            require(
                isinstance(account, dict)
                and set(account) == {"subject", "email", "local_user_id"}
                and all(isinstance(account[key], str) for key in account)
                and str(UUID(account["subject"])) == account["subject"]
                and str(UUID(account["local_user_id"])) == account["local_user_id"]
                and len(account["email"]) <= 254
                and re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", account["email"]),
                "PINNED_SYNTHETIC_IDENTITY_METADATA_REQUIRED",
            )
        require(
            all(
                accounts["primary"][key] != accounts["foreign"][key]
                for key in ["subject", "email", "local_user_id"]
            ),
            "INDEPENDENT_IDENTITY_FIXTURE_OWNERS_REQUIRED",
        )
    return identity


def identity_runtime(binding, plan, environment, values, current):
    identity = identity_profile(binding, plan)
    expected = identity["environments"][environment]
    require(
        plan.get("migration_revision") == plan.get("expected_schema_revision")
        and plan.get("migration_revision") in IDENTITY_SCHEMAS
        and values.get("ONESA_IDENTITY_ENABLED") == "true"
        and values.get("ONESA_IDENTITY_ISSUER") == expected["issuer"]
        and values.get("ONESA_IDENTITY_CLIENT_ID") == expected["client_id"]
        and values.get("ONESA_IDENTITY_CALLBACK_URL") == expected["callback_url"]
        and expected["callback_url"]
        == values.get("ONESA_PUBLIC_ORIGIN", "") + "/api/v1/auth/onesa/callback"
        and isinstance(values.get("ONESA_IDENTITY_CLIENT_SECRET"), str)
        and len(values["ONESA_IDENTITY_CLIENT_SECRET"]) >= 48
        and hashlib.sha256(values["ONESA_IDENTITY_CLIENT_SECRET"].encode()).hexdigest()
        == expected["client_secret_sha256"]
        and isinstance(values.get("ONESA_IDENTITY_ENCRYPTION_KEY"), str)
        and hashlib.sha256(values["ONESA_IDENTITY_ENCRYPTION_KEY"].encode()).hexdigest()
        == expected["encryption_key_sha256"],
        "PINNED_SHARED_IDENTITY_RUNTIME_REQUIRED",
    )
    key = values["ONESA_IDENTITY_ENCRYPTION_KEY"]
    require(
        re.fullmatch(r"[A-Za-z0-9_-]{43}=", key)
        and len(base64.urlsafe_b64decode(key)) == 32,
        "VALID_IDENTITY_TOKEN_ENCRYPTION_KEY_REQUIRED",
    )
    require(
        current.get("ONESA_IDENTITY_ENABLED", "false") in {"false", "true"},
        "EXPLICIT_BASELINE_IDENTITY_FLAG_REQUIRED",
    )
    if current.get("ONESA_IDENTITY_ENABLED") == "true":
        require(
            all(current.get(key) == values[key] for key in IDENTITY_KEYS),
            "IDENTITY_PROFILE_CANNOT_ROTATE_EXISTING_CREDENTIALS",
        )
    allowed = IDENTITY_KEYS | (
        {"ONESA_PUBLIC_ORIGIN"} if environment == "staging" else set()
    )
    require(
        {key: value for key, value in current.items() if key not in allowed}
        == {key: value for key, value in values.items() if key not in allowed},
        "IDENTITY_PROFILE_MUST_PRESERVE_NATIVE_CONFIGURATION",
    )
    return expected


def identity_credentials_digest(value):
    """Pin every credential/scope byte; only the bounded time envelope may renew."""
    require(isinstance(value, dict), "IDENTITY_CREDENTIAL_PAYLOAD_REQUIRED")
    return hashlib.sha256(
        canonical(
            {
                key: item
                for key, item in value.items()
                if key not in {"created_at", "expires_at"}
            }
        )
    ).hexdigest()


def identity_unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "IDENTITY_CREDENTIAL_DUPLICATE_FIELD")
        value[key] = item
    return value


def identity_credentials(binding, plan, *, require_current=True):
    """Verify exact source/actors/secret payload and its independently renewable lease."""
    identity = identity_profile(binding, plan)
    source = private(IDENTITY_CREDENTIALS)
    raw = source.read_bytes()
    require(0 < len(raw) <= 32768, "IDENTITY_CREDENTIAL_CUSTODY_BOUND")
    value = json.loads(raw, object_pairs_hook=identity_unique)
    require(
        identity_credentials_digest(value) == identity["credentials_sha256"],
        "SOURCE_BOUND_IDENTITY_CREDENTIAL_CUSTODY_REQUIRED",
    )
    require(
        isinstance(value, dict)
        and set(value)
        == {
            "schema_version",
            "candidate_commit",
            "created_at",
            "expires_at",
            "scope",
            "environments",
        }
        and type(value["schema_version"]) is int
        and value["schema_version"] == 1
        and value["candidate_commit"] == binding["candidate_commit"]
        and value["scope"] == "existing-owned-synthetic-identities"
        and isinstance(value["environments"], dict)
        and set(value["environments"]) == set(ENV),
        "OWNED_SYNTHETIC_IDENTITY_CUSTODY_REQUIRED",
    )
    created, expires = (
        dt.datetime.fromisoformat(value[key]) for key in ["created_at", "expires_at"]
    )
    require(
        created.tzinfo is not None
        and expires.tzinfo is not None
        and dt.timedelta(0) < expires - created <= dt.timedelta(hours=1)
        and created <= now()
        and (not require_current or now() < expires),
        "FRESH_BOUNDED_IDENTITY_CUSTODY_REQUIRED",
    )
    for environment, custody in value["environments"].items():
        expected = identity["environments"][environment]
        require(
            isinstance(custody, dict)
            and set(custody) == {"accounts", "portal_bypass"}
            and isinstance(custody["portal_bypass"], str)
            and len(custody["portal_bypass"]) <= 2048
            and not any(ord(c) < 32 or ord(c) == 127 for c in custody["portal_bypass"])
            and hashlib.sha256(custody["portal_bypass"].encode()).hexdigest()
            == expected["portal_bypass_sha256"]
            and isinstance(custody["accounts"], dict)
            and set(custody["accounts"]) == {"primary", "foreign"},
            "PINNED_IDENTITY_CREDENTIAL_ENVIRONMENT_REQUIRED",
        )
        for role, account in custody["accounts"].items():
            require(
                isinstance(account, dict)
                and set(account)
                == {
                    "subject",
                    "email",
                    "local_user_id",
                    "password",
                    "local_password",
                    "totp_secret",
                }
                and {key: account[key] for key in expected["accounts"][role]}
                == expected["accounts"][role]
                and isinstance(account["password"], str)
                and 12 <= len(account["password"]) <= 256
                and isinstance(account["local_password"], str)
                and 12 <= len(account["local_password"]) <= 128
                and isinstance(account["totp_secret"], str)
                and re.fullmatch("[A-Z2-7]{16,128}", account["totp_secret"]),
                "PINNED_SYNTHETIC_IDENTITY_CREDENTIALS_REQUIRED",
            )
    return source


def renew_identity_credentials(binding, plan, context, phase):
    """Issue a fresh short lease only inside an already reserved owner operation.

    This does not issue authority, change a qualification, replace credentials,
    retry a provider operation or mutate runtime configuration. The host keeps
    the canonical payload pin; the probe receives a separately byte-pinned copy
    containing only its environment. An in-flight probe's lease never extends.
    """
    require(
        os.geteuid() == 0 and not os.getenv("GITHUB_ACTIONS"),
        "OWNER_IDENTITY_RENEWAL_ONLY",
    )
    require(
        phase in {"staging", "deploy"}, "IDENTITY_RENEWAL_MUTATING_OWNER_PHASE_REQUIRED"
    )
    records = verify_invocation(binding, context, phase, plan)
    signed_chain = canonical(records)
    chain_sha256 = hashlib.sha256(signed_chain).hexdigest()
    operation = context["context_id"] if phase == "staging" else context["operation_id"]
    require(
        any(row["id"] == operation and row["binding"] == binding for row in records),
        "IDENTITY_RENEWAL_SIGNED_CONTEXT_REQUIRED",
    )
    source = identity_credentials(binding, plan, require_current=False)
    lock = source.with_name("ai-identity-renewal.lock")
    if lock.exists():
        private(lock)
    descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        require(
            os.fstat(descriptor).st_uid == 0
            and os.fstat(descriptor).st_nlink == 1
            and not os.fstat(descriptor).st_mode & 0o077,
            "IDENTITY_RENEWAL_LOCK_CUSTODY",
        )
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        source = identity_credentials(binding, plan, require_current=False)
        raw = source.read_bytes()
        original_hash = hashlib.sha256(raw).hexdigest()
        value = json.loads(raw, object_pairs_hook=identity_unique)
        if profiles.kind(binding) == "frontend":
            import oracle_ai_frontend

            artifact = oracle_ai_frontend.artifact_folder(binding)
        else:
            artifact = artifact_folder(binding)
        folder = private(artifact, directory=True) / "identity-credential-leases"
        folder.mkdir(mode=0o700, exist_ok=True)
        private(folder, directory=True)
        sync_directory(artifact)
        receipt_path = folder / (operation + ".json")
        if receipt_path.exists():
            receipt = read(receipt_path)
            require(
                receipt["binding"] == binding
                and receipt["operation_id"] == operation
                and receipt["phase"] == phase
                and receipt["signed_chain_sha256"] == chain_sha256
                and receipt["payload_sha256"] == plan["identity"]["credentials_sha256"]
                and receipt["envelope_sha256"] == original_hash,
                "IDENTITY_RENEWAL_CONTEXT_ALREADY_USED",
            )
            return identity_credentials(binding, plan)
        intent_path = folder / (operation + "-intent.json")
        require(
            not intent_path.exists(), "IDENTITY_RENEWAL_INCOMPLETE_NO_AUTOMATIC_RETRY"
        )
        current = now()
        expires = min(
            [
                current + dt.timedelta(hours=1),
                *[dt.datetime.fromisoformat(row["expires_at"]) for row in records],
            ]
        )
        require(current < expires, "IDENTITY_RENEWAL_OWNER_CONTEXT_EXPIRED")
        value.update(created_at=current.isoformat(), expires_at=expires.isoformat())
        require(
            identity_credentials_digest(value)
            == plan["identity"]["credentials_sha256"],
            "IDENTITY_RENEWAL_PAYLOAD_CHANGED",
        )
        encoded = canonical(value)
        write(
            intent_path,
            {
                "binding": binding,
                "operation_id": operation,
                "phase": phase,
                "signed_chain_sha256": chain_sha256,
                "payload_sha256": plan["identity"]["credentials_sha256"],
                "previous_envelope_sha256": original_hash,
                "intended_envelope_sha256": hashlib.sha256(encoded).hexdigest(),
                "created_at": value["created_at"],
                "expires_at": value["expires_at"],
                "automatic_retry": False,
                "provider_requests": 0,
            },
        )
        file, temporary = tempfile.mkstemp(
            prefix=".ai-identity-lease-", dir=source.parent
        )
        try:
            with os.fdopen(file, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            require(
                canonical(verify_invocation(binding, context, phase, plan))
                == signed_chain,
                "IDENTITY_RENEWAL_SIGNED_CHAIN_CHANGED",
            )
            private(source)
            require(
                sha(source) == original_hash, "IDENTITY_CUSTODY_CHANGED_DURING_RENEWAL"
            )
            os.replace(temporary, source)
            sync_directory(source.parent)
        finally:
            Path(temporary).unlink(missing_ok=True)
        write(
            receipt_path,
            {
                "binding": binding,
                "operation_id": operation,
                "phase": phase,
                "signed_chain_sha256": chain_sha256,
                "payload_sha256": plan["identity"]["credentials_sha256"],
                "previous_envelope_sha256": original_hash,
                "envelope_sha256": hashlib.sha256(encoded).hexdigest(),
                "created_at": value["created_at"],
                "expires_at": value["expires_at"],
                "records_issued": 0,
                "provider_requests": 0,
                "runtime_configuration_changed": False,
            },
        )
        return identity_credentials(binding, plan)
    finally:
        os.close(descriptor)


def fixture_cleanup_complete(binding, receipt):
    if profiles.component(binding) in profiles.IDENTITY:
        return (
            receipt.get("fixture_identities_preserved") is True
            and receipt.get("fixture_identities_disabled") is False
            and receipt.get("identity_sessions_retired") is True
            and receipt.get("existing_records_preserved") is True
        )
    return (
        receipt.get("fixture_identities_disabled") is True
        and receipt.get("existing_records_preserved") is True
    )


def runtime_target(row):
    """Hash the exact inspected runtime using the cross-product receipt contract."""
    labels = row["Config"].get("Labels") or {}
    return {
        "container_id": row["Id"],
        "image_id": row["Image"],
        "source_commit": labels.get("org.onesa.source-commit")
        or labels.get("org.opencontainers.image.revision"),
        "configuration_sha256": hashlib.sha256(
            canonical(
                {
                    "Config": row["Config"],
                    "HostConfig": row["HostConfig"],
                    "Mounts": row["Mounts"],
                    "Networks": {
                        name: value["NetworkID"]
                        for name, value in row["NetworkSettings"]["Networks"].items()
                    },
                }
            )
        ).hexdigest(),
    }


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


class OwnedProbeSnapshot:
    """Identify only this runner's active client; never an authorization record.

    Docker writes the CID into a private control directory that is not mounted
    into the producer. No caller JSON or environment option can select a client.
    """

    def __init__(self, control, operation, image, environment, mounts, network, cpus):
        require(str(UUID(operation)) == operation, "OWNED_PROBE_OPERATION")
        self.control = private(Path(control), directory=True)
        self.cidfile = self.control / "container.cid"
        self.name = "onesa-ai-probe-" + operation
        self.operation = operation
        self.image = image
        self.environment = environment
        self.mounts = sorted((str(p), target, rw) for p, target, rw in mounts)
        self.network = network
        self.nano_cpus = int(float(cpus) * 1_000_000_000)
        self._identity = None
        require(
            all(
                Path(p) != self.control and Path(p) not in self.control.parents
                for p, _target, _rw in self.mounts
            ),
            "OWNED_PROBE_CONTROL_MUST_NOT_BE_MOUNTED",
        )

    def cid(self):
        path = private(self.cidfile)
        before = path.stat()
        require(before.st_nlink == 1, "OWNED_PROBE_CID_FILE")
        value = path.read_text().strip()
        require(re.fullmatch("[a-f0-9]{64}", value), "OWNED_PROBE_CID_FILE")
        after = path.stat()
        identity = (before.st_dev, before.st_ino, before.st_mtime_ns, value)
        require(
            (before.st_dev, before.st_ino, before.st_mtime_ns)
            == (after.st_dev, after.st_ino, after.st_mtime_ns)
            and (self._identity is None or self._identity == identity),
            "OWNED_PROBE_CID_CHANGED",
        )
        self._identity = identity
        return value

    def validate(self, observed, *, allow_exited=False):
        row = observed.get(self.name)
        require(row and row["Id"] == self.cid(), "OWNED_PROBE_NOT_RUNNING")
        config, host = row["Config"], row["HostConfig"]
        require(
            row["Name"] == "/" + self.name
            and row["Image"] == self.image
            and (
                row["State"]["Running"] is True
                or allow_exited is True
                and row["State"]["Running"] is False
            )
            and host["AutoRemove"] is True
            and host["Init"] is True
            and host["ReadonlyRootfs"] is True
            and host["Privileged"] is False
            and host.get("CapAdd") in [None, []]
            and host["CapDrop"] == ["ALL"]
            and host["SecurityOpt"] == ["no-new-privileges:true"]
            and host["NetworkMode"] == self.network
            and host["Memory"] == 2 * 1024**3
            and host["NanoCpus"] == self.nano_cpus
            and not host.get("PortBindings")
            and not host.get("PublishAllPorts")
            and config["Entrypoint"] == ["python3"]
            and config["Cmd"]
            == [
                "/opt/onesa-ai-platform/scripts/release/oracle_ai_probe.py",
                self.environment,
                "--stdin-request",
            ]
            and config["Labels"].get("org.onesa.probe-operation") == self.operation,
            "OWNED_PROBE_RUNTIME_IDENTITY",
        )
        actual = []
        for mount in row["Mounts"]:
            if mount["Type"] == "bind":
                actual.append((mount["Source"], mount["Destination"], mount["RW"]))
            else:
                require(
                    mount["Type"] == "tmpfs"
                    and mount["Destination"] == "/tmp"
                    and mount["RW"] is True,
                    "OWNED_PROBE_EXTRA_MOUNT",
                )
        require(sorted(actual) == self.mounts, "OWNED_PROBE_MOUNT_IDENTITY")
        require(
            host["Tmpfs"] == {"/tmp": "rw,mode=700,size=512m"},
            "OWNED_PROBE_TMPFS_IDENTITY",
        )
        return self.name


def finish_probe_client(process, owned_probe, output):
    """Stop only the proven client; retain private inputs if its exit is uncertain."""
    safe = False
    failure = None
    try:
        cid = owned_probe.cid()

        def present():
            found = (
                docker(
                    "ps",
                    "-a",
                    "--no-trunc",
                    "--filter",
                    "id=" + cid,
                    "--format",
                    "{{.ID}}",
                    timeout=5,
                )
                .decode()
                .splitlines()
            )
            require(found in [[], [cid]], "OWNED_PROBE_EXIT_IDENTITY")
            return bool(found)

        if present():
            rows = json.loads(docker("inspect", cid, timeout=5))
            require(len(rows) == 1, "OWNED_PROBE_EXIT_IDENTITY")
            owned_probe.validate(
                {rows[0]["Name"].removeprefix("/"): rows[0]}, allow_exited=True
            )
            if rows[0]["State"]["Running"] is True:
                # One normal stop request, never a retry or a broad container kill.
                docker("stop", "--time", "60", cid, timeout=75)
        # AutoRemove can finish after the client exits. Only poll for disappearance;
        # an already exited client is never stopped again or admitted to inventory.
        deadline = time.monotonic() + 10
        while present():
            require(time.monotonic() < deadline, "OWNED_PROBE_EXIT_UNCONFIRMED")
            time.sleep(0.1)
        safe = not present()
        require(safe, "OWNED_PROBE_EXIT_UNCONFIRMED")
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as error:
        failure = type(error).__name__
    finally:
        if process.poll() is None:
            # This is our Popen handle, not an inferred PID or another workload.
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        write(
            output / "client-cleanup.json",
            {
                "operation_id": owned_probe.operation,
                "client_exit_confirmed": safe,
                "private_inputs_retained": True,
                "failure_category": failure,
                "release_authority": False,
            },
        )
    return safe


def cleanup_probe_inputs(output, binding, operation, environment, exited):
    """Exited containers alone do not prove that fixture cleanup completed."""
    clean = False
    try:
        receipt = read(output / "receipt.json") if exited else {}
        clean = (
            receipt.get("binding") == binding
            and receipt.get("operation_id") == operation
            and receipt.get("environment") == environment
            and fixture_cleanup_complete(binding, receipt)
        )
    except (OSError, ValueError, KeyError, TypeError):
        pass  # Keep the private inputs for exact owner inspection/recovery.
    if clean:
        for name in ["private-runtime.env", "private-provider-observation.json"]:
            private(output / name).unlink()
        if (output / "private-identity.json").exists():
            private(output / "private-identity.json").unlink()
    write(
        output / "private-input-cleanup.json",
        {
            "operation_id": operation,
            "private_inputs_retained": not clean,
            "client_exit_confirmed": exited,
            "fixture_cleanup_confirmed": clean,
            "release_authority": False,
        },
    )
    return clean


def inventory(*, owned_probe=None):
    """Capture every workload only after temporary Docker clients finish."""
    require(
        owned_probe is None or type(owned_probe) is OwnedProbeSnapshot,
        "OWNED_PROBE_CONTROL_REQUIRED",
    )
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
            if owned_probe is not None:
                owned_name = owned_probe.validate(observed)
                observed = {k: v for k, v in observed.items() if k != owned_name}
            # Do not omit helpers or classify an unknown workload as safe. Wait
            # for automatic removal; a long-lived --rm workload blocks release.
            if not any(v["HostConfig"]["AutoRemove"] for v in observed.values()):
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
    if "mode" in plan or selected != profiles.LEGACY:
        profiles.validate_mode(plan["binding"], plan.get("mode"), policy)
    tool = policy["toolchain"]
    if profiles.is_canonical(plan.get("binding")):
        binding = plan["binding"]
        source = profiles.source_binding(binding)
        installation = read(private(VERIFIER.parent / "installation.json"))
        require(
            policy.get("schema_version") == 2
            and tool.get("source_binding") == source
            and tool.get("source_commit") == binding["candidate_commit"]
            and tool.get("source_tree") == binding["source_tree"]
            and tool.get("source_sha256") == binding["source_sha256"]
            and installation.get("source_binding") == source
            and installation.get("state") == "INSTALLED_NOT_COMMISSIONED"
            and installation.get("policy_sha256") == trust["policy_sha256"],
            "CANONICAL_AI_SOURCE_NOT_COMMISSIONED",
        )
        for name, pin in installation["files"].items():
            require(
                sha(private(VERIFIER.parent / name)) == pin,
                "INSTALLED_EXECUTABLE_CHANGED",
            )
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
        binding.get("repository")
        in {profiles.REPOSITORY, profiles.CANONICAL_REPOSITORY}
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
        plan.get("mode") in profiles.MODES,
        "EXPLICIT_API_RELEASE_MODE",
    )
    profiles.bound_mode(binding, plan["mode"])
    if plan["mode"] == "identity":
        identity_profile(binding, plan)
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
        if plan["mode"] == "identity":
            allowed = set(IDENTITY_KEYS)
        generation_change = generation_transition(plan, current, values, env)
        if generation_change:
            # This opt-in cannot also activate a feature, change a credential,
            # migrate embeddings or select another model/provider.
            allowed = {"ONESA_MODEL_NAME"}
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
        if plan["mode"] == "identity":
            identity_runtime(binding, plan, env, values, current)
        elif plan["mode"] == "foundation":
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
                    if k
                    not in (
                        {"ONESA_CYBERSECURITY_ENABLED", "ONESA_PUBLIC_ORIGIN"}
                        | ({"ONESA_MODEL_NAME"} if generation_change else set())
                    )
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
    if plan["mode"] == "identity":
        urls = [
            urllib.parse.urlsplit(
                runtime_values(candidate_environment(binding, env))[
                    "ONESA_DATABASE_URL"
                ]
            )
            for env in ENV
        ]
        require(
            (urls[0].hostname, urls[0].port or 5432, urls[0].path)
            != (urls[1].hostname, urls[1].port or 5432, urls[1].path),
            "IDENTITY_DATABASE_TARGETS_NOT_ISOLATED",
        )
        require(
            all(
                runtime_values(candidate_environment(binding, "staging"))[key]
                != runtime_values(candidate_environment(binding, "production"))[key]
                for key in [
                    "ONESA_IDENTITY_CLIENT_ID",
                    "ONESA_IDENTITY_CLIENT_SECRET",
                    "ONESA_IDENTITY_ENCRYPTION_KEY",
                ]
            ),
            "IDENTITY_ENVIRONMENT_CREDENTIALS_MUST_BE_DISTINCT",
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


GENERATION_TRANSITION = "cloudflare-qwen3-to-gemma4"
PREVIOUS_GENERATION = "@cf/qwen/qwen3-30b-a3b-fp8"
CURRENT_GENERATION = "@cf/google/gemma-4-26b-a4b-it"
PREVIOUS_GENERATION_RETIREMENT = dt.datetime(2026, 11, 20, tzinfo=dt.timezone.utc)


def generation_transition(plan, current, prepared, environment):
    """A fixed source/config pair, never a general model or feature allowance."""
    transition = plan.get("generation_transition")
    if transition is None:
        return False
    binding = plan["binding"]
    require(
        transition == GENERATION_TRANSITION
        and profiles.is_canonical(binding)
        and profiles.kind(binding) == "api"
        and plan["mode"] in {"foundation", "twins", "cybersecurity"}
        and environment in ENV,
        "FIXED_CANONICAL_GENERATION_TRANSITION_REQUIRED",
    )
    require(
        current.get("ONESA_MODEL_BACKEND")
        == prepared.get("ONESA_MODEL_BACKEND")
        == "cloudflare"
        and current.get("ONESA_MODEL_NAME") in {PREVIOUS_GENERATION, CURRENT_GENERATION}
        and prepared.get("ONESA_MODEL_NAME") == CURRENT_GENERATION,
        "GENERATION_SOURCE_CONFIGURATION_PAIR_REQUIRED",
    )
    retained = plan["rollback"]["binding"]
    require(
        profiles.same_product(binding, retained)
        and profiles.kind(retained) == "api"
        and retained["target_environment"] == "production",
        "GENERATION_ACCEPTED_ROLLBACK_SOURCE_REQUIRED",
    )
    original = private(candidate_environment(retained, environment))
    require(
        sha(original) == retained["configuration_sha256"][environment],
        "GENERATION_ROLLBACK_CONFIGURATION_CHANGED",
    )
    rollback = runtime_values(original)
    excluded = {"ONESA_MODEL_NAME"} | (
        {"ONESA_PUBLIC_ORIGIN"} if environment == "staging" else set()
    )
    require(
        {k: v for k, v in current.items() if k not in excluded}
        == {k: v for k, v in prepared.items() if k not in excluded}
        == {k: v for k, v in rollback.items() if k not in excluded}
        and rollback.get("ONESA_MODEL_NAME")
        in {PREVIOUS_GENERATION, CURRENT_GENERATION},
        "GENERATION_ONLY_CONFIGURATION_AND_ROLLBACK_REQUIRED",
    )
    if rollback["ONESA_MODEL_NAME"] == PREVIOUS_GENERATION:
        # Existing owner records have at most 24 hours of authority. Do not
        # qualify a Qwen rollback whose remaining catalog lifetime is shorter.
        # This deadline is not proof of current provider availability.
        require(
            now() + dt.timedelta(hours=24) <= PREVIOUS_GENERATION_RETIREMENT,
            "SUPPORTED_ROLLBACK_REQUIRED_BEFORE_MODEL_RETIREMENT",
        )
    return True


def verify_retained_dependency(consumer_binding, retained, plan):
    """Read an original accepted chain; never invoke its controller or renew it."""
    binding = retained["binding"]
    require(
        profiles.same_product(consumer_binding, binding)
        and binding["target_environment"] == "production",
        "RETAINED_AI_PRODUCT_SOURCE_REQUIRED",
    )
    verifier_path = retained.get("verifier_path")
    if profiles.is_canonical(consumer_binding):
        # The original root-owned file is pinned by its original commissioned
        # anchor. A new source verifier must not impersonate that installation.
        require(isinstance(verifier_path, str), "ORIGINAL_RETAINED_VERIFIER_REQUIRED")
    else:
        require(verifier_path is None, "LEGACY_INVOCATION_PIN_UNCHANGED")
    return verify_invocation(
        binding,
        {"operation_id": retained["operation_id"], "read_only": True},
        "production",
        {
            "verifier_store": (
                retained["verifier_store"]
                if "verifier_store" in retained
                else plan["verifier_store"]
            )
        },
        dependency=True,
        **(
            {"retained_verifier": verifier_path, "consumer_binding": consumer_binding}
            if verifier_path is not None
            else {}
        ),
    )


def verify_invocation(
    binding,
    context,
    phase,
    plan,
    *,
    dependency=False,
    retained_verifier=None,
    consumer_binding=None,
):
    verifier = VERIFIER
    if retained_verifier is not None or consumer_binding is not None:
        require(
            dependency
            and phase == "production"
            and profiles.is_canonical(consumer_binding)
            and profiles.same_product(consumer_binding, binding)
            and binding["target_environment"] == "production"
            and context.get("read_only") is True
            and isinstance(retained_verifier, str),
            "RETAINED_VERIFIER_READ_ONLY_DEPENDENCY_REQUIRED",
        )
        verifier = private(Path(retained_verifier))
        require(
            0 < verifier.stat().st_size <= 2 * 1024 * 1024,
            "RETAINED_VERIFIER_BYTE_BOUND",
        )
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
        and sha(verifier) == trust["verifier_sha256"],
        "ISSUER_CUSTODY_PIN_CHANGED",
    )
    require(sha(OPENSSL) == trust["openssl_sha256"], "SIGNATURE_TOOL_CHANGED")
    db = sqlite3.connect(
        "file:" + str(store / "records.sqlite") + "?mode=ro", uri=True, timeout=20
    )

    records = []
    visited = set()

    def signed_record(identifier, kind=None, historical=False):
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
            prefix=".runner-signature-", dir=None if dependency else store
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
        return r

    def record(identifier, kind=None, historical=False):
        r = signed_record(identifier, kind, historical)
        parent = record(r["parent"], historical=historical) if r["parent"] else None
        if dependency and r["kind"] == "authorization":
            details = r["details"]
            require(
                parent
                and parent["kind"] == "qualification"
                and isinstance(details, dict)
                and details.get("decision") == "approve"
                and details.get("physical_hardware_authorized") is False
                and isinstance(details.get("attempt_id"), str),
                "RETAINED_AUTHORIZATION_COMPANION_REQUIRED",
            )
            # The attempt is a signed sibling of this authorization, not an
            # ancestor. Read it under the same original custody and revocation
            # checks, then bind it to the already verified qualification. Do not
            # traverse that shared parent again or execute the old issuer.
            attempt = signed_record(
                details["attempt_id"], "authorization-attempt", historical
            )
            require(
                attempt["parent"] == parent["id"]
                and isinstance(attempt["details"], dict)
                and attempt["details"].get("decision") == "PENDING",
                "RETAINED_AUTHORIZATION_COMPANION_MISMATCH",
            )
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

    expected_tree = (
        profiles.source_binding(binding)["product_source_tree"]
        if profiles.is_canonical(binding)
        else binding["source_tree"]
    )
    require(
        git_tree(tree).hex() == expected_tree,
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
    if plan.get("mode") == "identity":
        require(
            all(
                "scripts/release/" + name in expected
                for name in [
                    "oracle_ai_identity_browser.mjs",
                    "oracle_ai_identity_probe.py",
                    "oracle_ai_identity_context.cjs",
                ]
            ),
            "COMMISSIONED_IDENTITY_PROBE_CLOSURE_REQUIRED",
        )
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
        plan["migration_revision"]
        in (
            IDENTITY_SCHEMAS
            if plan["mode"] == "identity"
            else ["20261025_twins", "20261026_cybersecurity"]
        )
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
    if plan["mode"] == "identity":
        identity_credentials(binding, plan, require_current=False)
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
        profiles.same_product(plan["binding"], binding)
        and binding["target_environment"] == "production"
        and profiles.kind(binding) == "api"
        and binding["artifact_digest"] == old["image"]
        and (
            binding["candidate_commit"] != plan["binding"]["candidate_commit"]
            or (
                plan["mode"] == "identity"
                and profiles.component(binding) in profiles.SCOPED
                and binding["artifact_digest"] == plan["binding"]["artifact_digest"]
                and all(
                    binding["configuration_sha256"][env]
                    != plan["binding"]["configuration_sha256"][env]
                    for env in ENV
                )
            )
        ),
        "ROLLBACK_SOURCE_BINDING",
    )
    chain = verify_retained_dependency(plan["binding"], old, plan)
    context = next(record["id"] for record in chain if record["kind"] == "context")
    if plan["mode"] == "identity":
        output = (
            Path(plan["artifact_folder"])
            / "observations"
            / plan["qualification_context_id"]
        )
        proof = read(output / "identity-rollback-receipt.json")
        require(
            proof.get("binding") == plan["binding"]
            and proof.get("operation_id") == plan["qualification_context_id"]
            and proof.get("candidate_image") == plan["binding"]["artifact_digest"]
            and proof.get("rollback_image") == old["image"]
            and proof.get("retained_source") == binding["candidate_commit"]
            and proof.get("status") == "PASS"
            and proof.get("schema_revision") == plan["expected_schema_revision"]
            and plan["expected_schema_revision"] in IDENTITY_SCHEMAS
            and proof.get("synthetic_database_restore") == "PASS"
            and type(proof.get("production_writes")) is int
            and proof["production_writes"] == 0
            and isinstance(proof.get("environments"), dict)
            and set(proof["environments"]) == set(ENV),
            "FRESH_IDENTITY_SCHEMA_ROLLBACK_PROOF_REQUIRED",
        )
        for environment, value in proof["environments"].items():
            enabled = profiles.enabled_features(
                runtime_values(candidate_environment(plan["binding"], environment)),
                "identity",
            )
            require(
                isinstance(value, dict)
                and value.get("enabled_features") == sorted(enabled)
                and value.get("identity_enabled") is False
                and isinstance(value.get("checks"), dict)
                and all(
                    value["checks"].get(key) == "PASS"
                    for key in [
                        "core_readiness",
                        "local_authentication",
                        "ordinary_workflows",
                        "native_features",
                    ]
                ),
                "IDENTITY_ROLLBACK_MUST_PRESERVE_NATIVE_FEATURES",
            )
        return sha(output / "identity-rollback-receipt.json")
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
    if plan["mode"] == "identity":
        return identity_operational_observations(binding, plan, metrics, backup)
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
        generation_rollback = (
            accepted_rollback_proof(plan)
            if plan.get("generation_transition") is not None
            else None
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
            **(
                {"accepted_generation_rollback_sha256": generation_rollback}
                if generation_rollback is not None
                else {}
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


def identity_operational_observations(binding, plan, metrics, backup):
    """Reuse native restore evidence and require fresh retained-image compatibility."""
    enabled = profiles.enabled_features(
        runtime_values(candidate_environment(binding, "staging")), "identity"
    )
    workflow = profiles.workflow_mode("identity", enabled)
    output = (
        Path(plan["artifact_folder"])
        / "observations"
        / plan["qualification_context_id"]
    )
    name = (
        "forward-check-receipt.json"
        if workflow == "foundation"
        else "restore-receipt.json"
    )
    restored, replacement, hosted = (
        read(output / name),
        read(output / "replacement-ok.json"),
        read(output / "receipt.json"),
    )
    require(
        restored.get("binding") == binding
        and restored.get("operation_id") == plan["qualification_context_id"]
        and restored.get("status") == "PASS"
        and restored.get("schema_revision") == plan["expected_schema_revision"]
        and plan["expected_schema_revision"] in IDENTITY_SCHEMAS
        and type(restored.get("production_writes")) is int
        and restored["production_writes"] == 0,
        "IDENTITY_NATIVE_RESTORE_BINDING_REQUIRED",
    )
    if workflow == "foundation":
        require(
            restored.get("candidate_image") == binding["artifact_digest"]
            and restored.get("synthetic_database_restore") == "PASS"
            and restored.get("twins_disabled") is True
            and restored.get("cybersecurity_disabled") is True,
            "IDENTITY_FOUNDATION_RESTORE_REQUIRED",
        )
    else:
        require(
            restored.get("profile") == workflow
            and restored.get("database_manifest_matches") is True
            and restored.get("encrypted_fixture_recovery") == "PASS"
            and restored.get("fixture_owners") == 2
            and (workflow != "twins" or restored.get("file_hashes_match") is True),
            "IDENTITY_NATIVE_RESTORE_OR_FILE_PROOF_MISSING",
        )
    require(
        replacement.get("restore_receipt_sha256") == sha(output / name)
        and hosted.get("controlled_replacement") == replacement
        and hosted.get("binding") == binding
        and hosted.get("operation_id") == plan["qualification_context_id"]
        and hosted.get("environment") == "staging"
        and hosted.get("status") == "PASS"
        and fixture_cleanup_complete(binding, hosted)
        and hosted.get("enabled_features") == sorted(enabled)
        and all(
            hosted.get("checks", {}).get(key) == "PASS"
            for key in require_probe_policy(binding, "staging", plan, enabled)
        ),
        "IDENTITY_HOSTED_NATIVE_RESTORE_CHAIN_REQUIRED",
    )
    old = plan["rollback"]
    retained = json.loads(docker("image", "inspect", old["image"]))[0]
    require(
        retained["Id"] == old["image"]
        and retained["Architecture"] == "arm64"
        and retained["Config"]
        .get("Labels", {})
        .get("org.opencontainers.image.revision")
        == old["binding"]["candidate_commit"]
        and old["compatible_schema_revision"] == plan["expected_schema_revision"]
        and old["retain_additive_schema_and_files"] is True,
        "RETAINED_IDENTITY_ROLLBACK_IMAGE_REQUIRED",
    )
    rollback = accepted_rollback_proof(plan)
    production_features = profiles.enabled_features(
        runtime_values(candidate_environment(binding, "production")), "identity"
    )
    observed = inspect_database_backup(backup, plan)
    coordinated = (
        coordinated_backup_observation(binding, plan)
        if "twins" in production_features
        else None
    )
    return {
        "checks": {key: "PASS" for key in CHECKS["operations"]},
        "mode": "identity",
        "native_workflow": workflow,
        "enabled_features": sorted(production_features),
        "backup_readback": observed,
        "coordinated_backup": coordinated,
        "restore_receipt_sha256": sha(output / name),
        "accepted_rollback_proof_sha256": rollback,
        "metrics_checked_at": metrics["checked_at"],
        "backup_verified_at": backup["verified_at"],
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
identity_targets=['20261102_shared_identity','20261104_email_presentation']
assert target in ['20261025_twins','20261026_cybersecurity']+identity_targets
role=urlsplit(request['runtime']).username
assert re.fullmatch('[a-z_][a-z0-9_]{0,62}',role)
owner=make_url(request['owner']).set(drivername='postgresql+psycopg')
runtime=make_url(request['runtime'])
if target in identity_targets:
 assert owner.username != runtime.username
 assert (owner.host.replace('-pooler.','.'),owner.port or 5432,owner.database)==(runtime.host.replace('-pooler.','.'),runtime.port or 5432,runtime.database)
engine=create_engine(owner,connect_args={'connect_timeout':10,'sslmode':'verify-full','sslrootcert':'/etc/ssl/cert.pem','channel_binding':'require'})
with engine.begin() as connection:
 if target in identity_targets:
  connection.execute(text('SELECT pg_advisory_xact_lock(896075103)'))
  assert connection.scalar(text('SELECT NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls) FROM pg_roles WHERE rolname=:role'),{'role':role}) is True
 revision=connection.scalar(text('SELECT version_num FROM alembic_version'))
 revisions=['20261010_capacity','20261021_industrial','20261025_twins','20261026_cybersecurity']+identity_targets
 assert revision in revisions and revisions.index(target)>=revisions.index(revision)
 assert connection.scalar(text("SELECT has_schema_privilege(current_user,'public','CREATE') AND pg_has_role(current_user,c.relowner,'USAGE') FROM pg_class c WHERE c.oid='alembic_version'::regclass"))
 config=Config('alembic.ini');config.attributes['connection']=connection
 # env.py requires the URL even when the already verified connection is supplied.
 # This stays inside this short-lived process; it is not a Docker argument/env-file.
 os.environ['ONESA_DATABASE_URL']=owner.render_as_string(hide_password=False)
 command.upgrade(config,target)
 tables=['industrial_investigations','twin_files','twin_templates','twin_assets','twin_models','twin_notes','twin_sources','twin_readings','twin_events']
 if target in ['20261026_cybersecurity']+identity_targets:tables+=['cyber_assets','cyber_sources','cyber_mappings','cyber_policies','cyber_baselines','cyber_events','cyber_findings','cyber_results','cyber_investigations','cyber_actions','cyber_reports','cyber_summaries']
 if target in identity_targets:tables+=['identity_sessions','identity_transactions','shared_identities']
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
            "runtime_new_tables_DML_granted": (
                24
                if plan["migration_revision"] in IDENTITY_SCHEMAS
                else 21
                if plan["migration_revision"] == "20261026_cybersecurity"
                else 9
            ),
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
    require(mode in profiles.MODES, "UNKNOWN_PROBE_MODE")
    profiles.bound_mode(binding, mode)
    require(env in {"staging", "production"}, "UNKNOWN_PROBE_ENVIRONMENT")
    require(
        mode != "identity" or enabled_features is not None,
        "IDENTITY_ACTUAL_ENABLED_FEATURE_SCOPE_REQUIRED",
    )
    features = (
        (frozenset() if mode == "foundation" else frozenset({mode}))
        if enabled_features is None
        else frozenset(enabled_features)
    )
    require(
        features <= {"twins", "cybersecurity"}
        and (
            mode == "identity"
            or (not features if mode == "foundation" else mode in features)
        ),
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
    if profiles.workflow_mode(mode, features) == "foundation":
        mandatory |= {"twins_disabled", "cybersecurity_disabled", "ordinary_workflows"}
    if mode == "identity":
        mandatory |= IDENTITY_CHECKS
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
    if plan["mode"] == "identity":
        require(
            installed_plan.get("identity") == plan.get("identity"),
            "IDENTITY_PROBE_PLAN_CHANGED",
        )
        identity_custody = identity_credentials(binding, plan)
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
    workflow = profiles.workflow_mode(plan["mode"], enabled)
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
    if plan["mode"] == "identity":
        raw_custody = private(identity_custody).read_bytes()
        custody = json.loads(raw_custody, object_pairs_hook=identity_unique)
        require(
            identity_credentials_digest(custody)
            == plan["identity"]["credentials_sha256"],
            "IDENTITY_CUSTODY_CHANGED_BEFORE_PROBE",
        )
        custody["environments"] = {env: custody["environments"][env]}
        custody["source_custody_sha256"] = plan["identity"]["credentials_sha256"]
        identity_custody = output / "private-identity.json"
        write(identity_custody, custody)
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
        if plan["mode"] == "identity":
            for key in [
                "ONESA_IDENTITY_ENABLED",
                "ONESA_IDENTITY_ISSUER",
                "ONESA_IDENTITY_CLIENT_ID",
                "ONESA_IDENTITY_CALLBACK_URL",
            ]:
                f.write(key + "=" + values[key] + "\n")
    # This immutable, credential-free-built probe image contains the reviewed
    # existing hosted API/UI harnesses and the owned Twins journey. It observes the
    # actual provider and application; no caller PASS or stored Actions artifact is read.
    controls = folder / "probe-clients"
    controls.mkdir(mode=0o700, exist_ok=True)
    private(controls, directory=True)
    control = controls / operation
    control.mkdir(mode=0o700, exist_ok=False)
    mounts = [
        (plan_file, "/private/plan.json", False),
        (narrowed, "/private/runtime.env", False),
        (output / "private-provider-observation.json", "/private/vercel.json", False),
        (Path(plan["preview_receipt_path"]), "/private/frontend-preview.json", False),
        *(
            [(identity_custody, "/private/identity.json", False)]
            if plan["mode"] == "identity"
            else []
        ),
        *(
            [(output / "reference", "/private/reference", False)]
            if "twins" in enabled
            else []
        ),
        (output, "/private/output", True),
    ]
    owned_probe = OwnedProbeSnapshot(
        control, operation, plan["probe_image"], env, mounts, network, cpus
    )
    args = [
        "/usr/bin/docker",
        "run",
        "--rm",
        "--init",
        "--name",
        owned_probe.name,
        "--cidfile",
        str(owned_probe.cidfile),
        "--label",
        "org.onesa.probe-operation=" + operation,
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
        *[
            arg
            for path, target, rw in mounts
            for arg in ["-v", str(path) + ":" + target + (":rw" if rw else ":ro")]
        ],
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
            **(
                {"identity_custody_sha256": sha(identity_custody)}
                if plan["mode"] == "identity"
                else {}
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
            umask=0o077,
        )
        deadline = time.monotonic() + 1800
        handled = False
        try:
            process.stdin.write(data)
            process.stdin.close()
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

                    if workflow in ["twins", "cybersecurity"]:
                        if workflow == "twins":
                            oracle_twin_restore.capture_fixture_files(
                                output, binding, operation, plan["storage"][env]
                            )
                        oracle_twin_restore.restore(output, binding, operation)
                    else:
                        import oracle_forward_check

                        oracle_forward_check.check(output, binding, operation)
                    before = inventory(owned_probe=owned_probe)
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
                    after = inventory(owned_probe=owned_probe)
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
                                    if workflow != "foundation"
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
            failed = sys.exc_info()[0] is not None
            try:
                safe = finish_probe_client(process, owned_probe, output)
            except (
                OSError,
                ValueError,
                KeyError,
                TypeError,
                subprocess.SubprocessError,
            ):
                # The runner's original diagnostic must survive cleanup failure.
                safe = False
            try:
                cleanup_probe_inputs(output, binding, operation, env, safe)
            except (OSError, ValueError, KeyError, TypeError):
                if not failed:
                    raise Refused("PRIVATE_PROBE_CLEANUP_FAILED_INSPECT_ONLY") from None
            if not failed:
                require(safe, "OWNED_PROBE_EXIT_UNCONFIRMED_INSPECT_ONLY")
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
        fixture_cleanup_complete(binding, observed),
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
        "backend_runtime": runtime_target(actual),
        "deployment_id": (
            metadata["provider"]["deployment_id"]
            if profiles.kind(binding) == "frontend"
            else actual["Id"]
        ),
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
        and fixture_cleanup_complete(binding, observed),
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
        "backend_runtime": runtime_target(actual),
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
            binding["repository"]
            in {profiles.REPOSITORY, profiles.CANONICAL_REPOSITORY}
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


def ci_reference(binding, ci):
    workflow = (
        ".github/workflows/verify.yml" if profiles.is_canonical(binding) else "ci.yml"
    )
    candidates = [
        row
        for row in ci
        if row.get("workflow") == workflow
        and type(row.get("run_id")) is int
        and row["run_id"] > 0
    ]
    require(len(candidates) == 1, "SIGNED_GENUINE_CI_REFERENCE_MISSING")
    if profiles.is_canonical(binding):
        row = candidates[0]
        require(
            row.get("source") == profiles.source_binding(binding)
            and row.get("verification_only") is True
            and row.get("release_authorized") is False
            and type(row.get("run_attempt")) is int
            and row["run_attempt"] == 1,
            "SIGNED_CANONICAL_SOURCE_REFERENCE_MISMATCH",
        )
    return candidates[0]["run_id"]


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
    require(ci, "SIGNED_GENUINE_CI_REFERENCE_MISSING")
    observed_ci_run_id = ci_reference(binding, ci)
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
    plan["observed_ci_run_id"] = observed_ci_run_id
    migration_prerequisites(plan)
    if plan["mode"] == "identity" and phase in {"staging", "deploy"}:
        renew_identity_credentials(binding, plan, context, phase)
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
