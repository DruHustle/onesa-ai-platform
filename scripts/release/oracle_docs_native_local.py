"""Pinned owner-native observer; it has no arbitrary-message signing interface.

A private installation config selects a closed qualified source/runtime closure.
A generated key is untrusted until the Oracle owner explicitly commissions its
registration. A caller JSON file cannot grant release authority.
"""

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oracle_docs_build as builds
import oracle_docs_checks as checks
import oracle_docs_contract as contract
import oracle_owner as owner

DOMAIN = "onesa-docs-native-attestation/v1"


def private(path, *, directory=False):
    path = Path(path).absolute()
    owner.private(path, directory=directory, uid=os.getuid())
    return path


def read(path, maximum=4 * 1024 * 1024):
    path = private(path)
    owner.require(path.stat().st_size <= maximum, "LOCAL_PRIVATE_INPUT_BOUND")
    return json.loads(path.read_bytes(), object_pairs_hook=unique)


def unique(pairs):
    result = {}
    for key, value in pairs:
        owner.require(key not in result, "DUPLICATE_LOCAL_JSON_FIELD")
        result[key] = value
    return result


def installed(path):
    cfg = read(path)
    owner.require(
        set(cfg)
        == {
            "schema_version",
            "binding",
            "issuer",
            "producer",
            "checkout",
            "runtime",
            "source_pins",
            "runtime_pins",
            "journal",
        }
        and type(cfg["schema_version"]) is int
        and cfg["schema_version"] == 1,
        "EXPLICIT_NATIVE_INSTALLATION_REQUIRED",
    )
    checkout = private(cfg["checkout"], directory=True)
    owner.require(
        checkout.name == "onesa-ai-platform"
        and cfg["binding"]["repository"] == builds.REPOSITORY
        and cfg["binding"]["component"] == "docs-public",
        "ISOLATED_PUBLIC_DOCS_INSTALLATION_ONLY",
    )
    owner.require(
        cfg["source_pins"].keys() == contract.SOURCE_CLOSURE,
        "CLOSED_SOURCE_SET_REQUIRED",
    )
    for relative, pin in cfg["source_pins"].items():
        source = private(checkout / relative)
        owner.require(
            owner.file_digest(source) == pin, "QUALIFIED_NATIVE_SOURCE_CHANGED"
        )
    owner.require(
        Path(__file__).resolve()
        == (checkout / "scripts/release/oracle_docs_native_local.py").resolve(),
        "RUN_ONLY_THE_INSTALLED_NATIVE_OBSERVER",
    )
    runtime = cfg["runtime"]
    owner.require(
        set(runtime) == contract.RUNTIME_PINS, "EXACT_NATIVE_RUNTIME_PATHS_REQUIRED"
    )
    for name, runtime_path in runtime.items():
        p = private(runtime_path)
        owner.require(
            owner.file_digest(p) == cfg["runtime_pins"][name],
            "PINNED_NATIVE_RUNTIME_CHANGED",
        )
    manifest = read(runtime["browser_packages"])
    owner.require(
        set(manifest) == {"root", "files"}
        and isinstance(manifest["files"], dict)
        and manifest["files"],
        "BOUNDED_BROWSER_RUNTIME_MANIFEST_REQUIRED",
    )
    modules = private(manifest["root"], directory=True)
    actual = {}
    for file in sorted(modules.rglob("*")):
        relative = file.relative_to(modules).as_posix()
        if (
            relative == ".bin"
            or relative.startswith(".bin/")
            or relative == ".package-lock.json"
        ):
            continue
        owner.require(not file.is_symlink(), "NATIVE_RUNTIME_SYMLINK_REFUSED")
        if file.is_file():
            actual[relative] = owner.file_digest(file)
    owner.require(actual == manifest["files"], "NATIVE_RUNTIME_FILE_CLOSURE_CHANGED")
    expected_modules = checkout / "onesa-ai-platform-frontend/apps/docs/node_modules"
    owner.require(
        expected_modules == modules,
        "BROWSER_RUNTIME_MUST_BELONG_TO_THE_INSTALLED_CHECKOUT",
    )
    producer = contract.producer_digest(cfg["source_pins"], cfg["runtime_pins"])
    owner.require(
        set(cfg["producer"]) == {"sha256", "public_key", "private_key"}
        and producer == cfg["producer"]["sha256"],
        "NATIVE_PRODUCER_CLOSURE_CHANGED",
    )
    private(cfg["journal"], directory=True)
    issuer = cfg["issuer"]
    owner.require(
        set(issuer) == {"public_key", "key_id", "installation_id", "verifier_sha256"},
        "EXPLICIT_COMMISSIONED_ISSUER_PIN_REQUIRED",
    )
    owner.require(
        owner.file_digest(private(issuer["public_key"])) == issuer["key_id"],
        "COMMISSIONED_ISSUER_KEY_CHANGED",
    )
    owner.require(not os.getenv("GITHUB_ACTIONS"), "NATIVE_OWNER_INFRASTRUCTURE_ONLY")
    return cfg


def verified(cfg, envelope, *, kinds):
    owner.require(
        isinstance(envelope, dict) and set(envelope) == {"record", "signature"},
        "GENUINE_SIGNED_OWNER_ENVELOPE_REQUIRED",
    )
    record, signature = envelope["record"], envelope["signature"]
    issuer = cfg["issuer"]
    owner.require(
        set(signature) == {"algorithm", "key_id", "value"}
        and signature["algorithm"] == "Ed25519"
        and signature["key_id"] == issuer["key_id"],
        "CURRENT_COMMISSIONED_ISSUER_REQUIRED",
    )
    raw = base64.b64decode(signature["value"], validate=True)
    owner.require(len(raw) == 64, "EXACT_OWNER_SIGNATURE_REQUIRED")
    original = owner.OPENSSL
    owner.OPENSSL = cfg["runtime"]["openssl"]
    try:
        owner.signed_bytes(
            None, private(issuer["public_key"]), owner.canonical(record), raw
        )
    finally:
        owner.OPENSSL = original
    owner.require(
        type(record["schema_version"]) is int
        and record["schema_version"] == 1
        and record["kind"] in kinds
        and record["binding"] == cfg["binding"]
        and type(record["workflow_run_id"]) is int
        and record["workflow_run_id"] == 0,
        "EXACT_OWNER_SOURCE_AND_RECORD_PURPOSE_REQUIRED",
    )
    owner.identifier(record["id"])
    provenance = record["owner_provenance"]
    owner.require(
        provenance
        == {
            "mechanism": "commissioned-pinned-OpenSSH-and-authenticated-owner",
            "owner": owner.OWNER,
            "installation_id": issuer["installation_id"],
            "verifier_sha256": issuer["verifier_sha256"],
        },
        "OWNER_RUN_PROVENANCE_REQUIRED_NOT_ACTIONS",
    )
    now = datetime.now(timezone.utc)
    issued = datetime.fromisoformat(record["issued_at"])
    expiry = datetime.fromisoformat(record["expires_at"])
    owner.require(
        issued.utcoffset() == timedelta()
        and expiry.utcoffset() == timedelta()
        and issued <= now < expiry
        and timedelta() < expiry - issued <= timedelta(days=1),
        "OWNER_RECORD_EXPIRED_OR_FUTURE",
    )
    return record


def write(path, raw):
    with os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb"
    ) as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())


def assets(raw, descriptor, source):
    observed = builds.archive_identity(
        raw,
        {
            "id": descriptor["artifact_id"],
            "name": descriptor["name"],
            "digest": "sha256:" + descriptor["archive_sha256"],
        },
        source,
    )
    owner.require(observed == descriptor, "ROOT_BOUND_NATIVE_ARTIFACT_CHANGED")
    mimes = {
        ".html": ["text/html"],
        ".json": ["application/json"],
        ".js": ["application/javascript", "text/javascript"],
        ".css": ["text/css"],
        ".svg": ["image/svg+xml"],
        ".png": ["image/png"],
        ".ico": ["image/x-icon", "image/vnd.microsoft.icon"],
        ".pdf": ["application/pdf"],
        ".xml": ["application/xml", "text/xml"],
        ".txt": ["text/plain"],
        ".mmd": [
            "text/plain",
            "application/octet-stream",
            "application/vnd.chipnuts.karaoke-mmd",
        ],
        ".woff": ["font/woff", "application/font-woff"],
        ".woff2": ["font/woff2"],
        ".jpg": ["image/jpeg"],
        ".jpeg": ["image/jpeg"],
    }
    import io

    result = []
    routes = set()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for item in archive.infolist():
            if item.is_dir():
                continue
            route = "/" + item.filename
            if route == "/index.html":
                route = "/"
            elif route.endswith("/index.html"):
                route = route[:-10]
            elif route.endswith(".html"):
                route = route[:-5]
            canonical = route.rstrip("/") or "/"
            owner.require(
                canonical not in routes and not any(char in route for char in "?#\\"),
                "NATIVE_ASSET_ROUTE_COLLISION_OR_ESCAPE",
            )
            routes.add(canonical)
            body = archive.read(item)
            result.append(
                {
                    "route": route,
                    "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "mimes": mimes.get(
                        Path(item.filename).suffix, ["application/octet-stream"]
                    ),
                }
            )
    return result


def observe(cfg, record, archive, *, probe=False):
    target = record["details"]["target"]
    environment = record["details"]["environment"]
    provider = target["provider"]
    publication = target["publication"]
    owner.require(
        environment in {"staging", "production"}
        and publication["environment"] == environment
        and publication["source"]
        == {
            k: cfg["binding"][k]
            for k in ["repository", "candidate_commit", "source_tree"]
        }
        and provider["source_revision"] == cfg["binding"]["candidate_commit"],
        "NATIVE_TARGET_SOURCE_OR_ENVIRONMENT_CHANGED",
    )
    archive_path = private(archive)
    owner.require(
        0 < archive_path.stat().st_size <= 128 * 1024**2
        and archive_path.stat().st_size == publication["artifact"]["archive_bytes"],
        "ROOT_BOUND_ARTIFACT_SIZE_CHANGED",
    )
    raw = archive_path.read_bytes()
    expected = assets(raw, publication["artifact"], cfg["binding"]["candidate_commit"])
    owner.require(
        provider["asset_count"] == len(expected)
        and provider["artifact_manifest_sha256"]
        == publication["artifact"]["file_manifest_sha256"],
        "NATIVE_PROVIDER_ARTIFACT_BINDING_CHANGED",
    )
    journal = Path(cfg["journal"]) / record["id"]
    journal.mkdir(mode=0o700)  # Never repeat a full observation after interruption.
    request = {
        "checkout": cfg["checkout"],
        "origin": provider["origin"],
        "revision": cfg["binding"]["candidate_commit"],
        "environment": environment,
        "mode": "preflight" if probe else "observe",
        "assets": expected,
    }
    encoded = owner.canonical(request)
    file = journal / "input.json"
    write(file, encoded)
    node = cfg["runtime"]["node"]
    program = Path(cfg["checkout"]) / "scripts/release/oracle_docs_native_probe.mjs"
    result = subprocess.run(
        [node, str(program), str(file), hashlib.sha256(encoded).hexdigest()],
        capture_output=True,
        timeout=900,
        check=False,
        env={
            "PATH": str(Path(node).parent) + ":/usr/bin:/bin",
            "LANG": "C.UTF-8",
            "TMPDIR": str(journal),
        },
    )
    write(journal / "observer.stdout", result.stdout)
    write(journal / "observer.stderr", result.stderr)
    owner.require(
        result.returncode == 0 and 0 < len(result.stdout) <= 1024 * 1024,
        "NATIVE_OBSERVATION_FAILED_NO_SIGNING_OR_RETRY",
    )
    response = json.loads(result.stdout, object_pairs_hook=unique)
    if probe:
        owner.require(
            response
            == {
                "state": "NATIVE_OWNER_SESSION_READY_NOT_QUALIFICATION",
                "providerWrites": 0,
                "sessionValuesRead": False,
            },
            "NATIVE_PREFLIGHT_NOT_READY",
        )
        return response
    owner.require(
        response["validation_channel"] == "native-owner"
        and response["provider_writes"] == 0
        and response["blocked_non_get_requests"] == 0
        and response["original_tabs_preserved"] is True
        and response["session_values_read"] is False
        and response["verified_public_asset_responses"] == len(expected),
        "ACTUAL_NATIVE_OBSERVER_OR_PRESERVATION_FAILED",
    )
    browser = response["browser"]
    owner.require(
        set(browser) == {"product", "reported_headless", "connection"}
        and isinstance(browser["product"], str)
        and re.fullmatch(r"Chrome/[0-9.]+", browser["product"])
        and browser["reported_headless"] is False
        and browser["connection"] == "existing-owner-native-cdp",
        "ACTUAL_HEADED_NATIVE_BROWSER_REQUIRED",
    )
    source = Path(cfg["checkout"])
    registry = json.loads(
        (
            source
            / "onesa-ai-platform-frontend/packages/onesa-design/onesa-applications.json"
        ).read_bytes()
    )
    icons = json.loads(
        (
            source
            / "onesa-ai-platform-frontend/apps/docs/static/brand/icons/v1/sources.json"
        ).read_bytes()
    )
    checks.validate(response["acceptance"], registry, icons, require=owner.require)
    owner.require(
        response["acceptance"]["result"] == "PASS"
        and response["acceptance"]["environment_context"] == environment,
        "ALL_NATIVE_WORKFLOWS_AND_CONTEXT_REQUIRED",
    )
    # Verify the root envelope again after the real observation, before key access.
    return {
        "provider": provider,
        "asset_manifest_sha256": publication["artifact"]["file_manifest_sha256"],
        "asset_count": len(expected),
        "acceptance": response["acceptance"],
        "source_revision": cfg["binding"]["candidate_commit"],
        "observation_mode": "existing-owner-browser-no-profile-export",
        "kind": "owner-native-public-docs-observation",
        "browser": browser,
    }


def sign_observation(cfg, challenge, evidence, registration):
    owner.require(
        challenge["details"]["registration_id"] == registration["id"]
        and registration["details"]["producer_sha256"] == cfg["producer"]["sha256"]
        and registration["details"]["purpose"] == DOMAIN,
        "REGISTERED_SOURCE_BOUND_NATIVE_PRODUCER_REQUIRED",
    )
    public = private(cfg["producer"]["public_key"])
    owner.require(
        owner.file_digest(public) == registration["details"]["public_key_sha256"]
        and owner.file_digest(public) != cfg["issuer"]["key_id"],
        "NATIVE_PRODUCER_PUBLIC_KEY_CHANGED_OR_REPURPOSED",
    )
    payload = {
        "purpose": DOMAIN,
        "schema_version": 1,
        "receipt_id": str(uuid.uuid4()),
        "challenge_id": challenge["id"],
        "registration_id": registration["id"],
        "binding": cfg["binding"],
        "workflow_run_id": 0,
        "environment": challenge["details"]["environment"],
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "producer_sha256": cfg["producer"]["sha256"],
        "evidence": evidence,
    }
    key = private(cfg["producer"]["private_key"])
    original = owner.OPENSSL
    owner.OPENSSL = cfg["runtime"]["openssl"]
    try:
        signature = owner.signed_bytes(key, public, owner.canonical(payload))
    finally:
        owner.OPENSSL = original
    envelope = {"payload": payload, "signature": base64.b64encode(signature).decode()}
    path = Path(cfg["journal"]) / challenge["id"] / "native-envelope.json"
    write(path, owner.canonical(envelope))
    return path


def generate_key(cfg):
    """Create a new purpose-specific key; creation never registers or trusts it."""
    key = Path(cfg["producer"]["private_key"])
    public = Path(cfg["producer"]["public_key"])
    owner.require(
        key.is_absolute()
        and public.is_absolute()
        and key.parent == public.parent
        and key != public
        and not key.exists()
        and not public.exists(),
        "NEW_NATIVE_KEY_PATHS_REQUIRED_NO_OVERWRITE",
    )
    private(key.parent, directory=True)
    for destination, args in [
        (key, ["genpkey", "-algorithm", "ED25519"]),
        (public, ["pkey", "-in", str(key), "-pubout"]),
    ]:
        with os.fdopen(
            os.open(
                destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            ),
            "wb",
        ) as out:
            result = subprocess.run(
                [cfg["runtime"]["openssl"], *args],
                stdout=out,
                stderr=subprocess.PIPE,
                timeout=15,
                check=False,
            )
            out.flush()
            os.fsync(out.fileno())
        owner.require(
            result.returncode == 0,
            "NATIVE_KEY_GENERATION_INTERRUPTED_RETAIN_PARTIAL_STATE",
        )
    return {
        "state": "NEW_NATIVE_KEY_CREATED_UNREGISTERED_UNCOMMISSIONED",
        "public_key_path": str(public),
        "public_key_sha256": owner.file_digest(public),
        "production_deployment_authorized": False,
    }


def sign_possession(cfg, registration):
    """Sign only the fixed, issuer-signed registration possession contract."""
    details = registration["details"]
    public = private(cfg["producer"]["public_key"])
    owner.require(
        details["purpose"] == DOMAIN
        and details["state"] == "PENDING_EXPLICIT_OWNER_COMMISSION"
        and details["producer_sha256"] == cfg["producer"]["sha256"]
        and details["public_key_sha256"] == owner.file_digest(public)
        and owner.file_digest(public) != cfg["issuer"]["key_id"],
        "EXACT_NEW_NATIVE_REGISTRATION_REQUIRED",
    )
    raw = owner.canonical(
        {
            "purpose": DOMAIN + "/key-possession",
            "registration_id": registration["id"],
            "binding": cfg["binding"],
            "producer_sha256": cfg["producer"]["sha256"],
        }
    )
    original = owner.OPENSSL
    owner.OPENSSL = cfg["runtime"]["openssl"]
    try:
        signature = owner.signed_bytes(
            private(cfg["producer"]["private_key"]), public, raw
        )
    finally:
        owner.OPENSSL = original
    path = Path(cfg["journal"]) / (registration["id"] + "-possession.json")
    result = {
        "state": "NATIVE_KEY_POSSESSION_NOT_COMMISSION_OR_AUTHORIZATION",
        "registration_id": registration["id"],
        "possession_signature": base64.b64encode(signature).decode(),
    }
    write(path, owner.canonical(result))
    return {
        "state": result["state"],
        "possession_path": str(path),
        "registration_id": registration["id"],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["keygen", "possession", "probe", "observe"])
    p.add_argument("--installation", type=Path, required=True)
    p.add_argument("--record", type=Path)
    p.add_argument("--registration", type=Path)
    p.add_argument("--artifact", type=Path)
    args = p.parse_args()
    cfg = installed(args.installation)
    if args.action == "keygen":
        owner.require(
            not any([args.record, args.registration, args.artifact]),
            "NATIVE_KEY_GENERATION_ONLY",
        )
        print(json.dumps(generate_key(cfg)))
        return
    owner.require(args.record is not None, "SIGNED_OWNER_RECORD_REQUIRED")
    if args.action == "possession":
        owner.require(
            not any([args.registration, args.artifact]), "NATIVE_POSSESSION_ONLY"
        )
        registration = verified(
            cfg, read(args.record), kinds={"native-producer-registration"}
        )
        print(json.dumps(sign_possession(cfg, registration)))
        return
    owner.require(args.artifact is not None, "EXACT_SOURCE_BOUND_ARTIFACT_REQUIRED")
    envelope = read(args.record)
    record = verified(
        cfg,
        envelope,
        kinds={"native-preflight-target"}
        if args.action == "probe"
        else {"native-observation-challenge"},
    )
    if args.action == "probe":
        result = observe(cfg, record, args.artifact, probe=True)
    else:
        owner.require(
            args.registration is not None, "SIGNED_CURRENT_NATIVE_REGISTRATION_REQUIRED"
        )
        registration = verified(
            cfg, read(args.registration), kinds={"native-producer-registration"}
        )
        evidence = observe(cfg, record, args.artifact)
        owner.require(
            installed(args.installation) == cfg,
            "NATIVE_SOURCE_OR_RUNTIME_CHANGED_DURING_OBSERVATION",
        )
        verified(cfg, envelope, kinds={"native-observation-challenge"})
        verified(cfg, read(args.registration), kinds={"native-producer-registration"})
        path = sign_observation(cfg, record, evidence, registration)
        result = {
            "state": "NATIVE_OBSERVATION_SIGNED_NOT_AUTHORIZATION",
            "envelope_path": str(path),
            "challenge_id": record["id"],
            "provider_writes": 0,
        }
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 -- never export private provider or signing inputs
        raise SystemExit(
            "NATIVE_OWNER_OPERATION_REFUSED_INSPECT_PRIVATE_JOURNAL_NO_RETRY"
        ) from None
