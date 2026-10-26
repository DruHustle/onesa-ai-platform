"""Coordinate existing AI database snapshots with private immutable model blobs.

Owner infrastructure only. Uses the already installed/pinned read-only snapshot
and encrypted database-v1 transport. New file envelopes use the same recovery
public key and existing AI prefix/cumulative 64 MiB cap, with no deletion. An
interrupted conditional upload is inspected by ciphertext identity, never retried.
"""

import argparse
import base64
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oracle_ai_runner as custody

CONFIG = Path("/etc/onesa/ai-twin-backup-registration.json")
STATE = Path("/var/lib/onesa/operations/ai-twin-backups")
MAX = 64 * 1024 * 1024
PG = "postgres@sha256:89f747171c4b0af0eacf5984550060be79786dbe286eb60cfa691d79d1e8b23f"


def require(value, code):
    custody.require(value, code)


def references(sql):
    """Read only pg_restore's bounded twin_files COPY; execute no dump SQL."""
    require(len(sql) <= MAX, "COPY_OUTPUT_BOUND")
    rows, columns, active, seen = [], None, False, False
    for line in sql.decode("utf-8").splitlines():
        if line.startswith("COPY public.twin_files ("):
            require(not seen and line.endswith(") FROM stdin;"), "COPY_HEADER")
            seen = active = True
            columns = line[
                len("COPY public.twin_files (") : -len(") FROM stdin;")
            ].split(", ")
            require(
                len(columns) == len(set(columns))
                and {"user_id", "sha256", "size"} <= set(columns),
                "COPY_COLUMNS",
            )
        elif active and line == "\\.":
            active = False
        elif active:
            values = line.split("\t")
            require(len(values) == len(columns), "COPY_ROW")
            item = dict(zip(columns, values, strict=True))
            owner, digest = item["user_id"], item["sha256"]
            require(
                str(UUID(owner)) == owner and re.fullmatch("[a-f0-9]{64}", digest),
                "FILE_REFERENCE_IDENTITY",
            )
            require(
                item["size"].isdecimal() and 0 < int(item["size"]) <= 4 * 1024 * 1024,
                "FILE_REFERENCE_BOUND",
            )
            rows.append({"owner": owner, "sha256": digest, "size": int(item["size"])})
            require(len(rows) <= 1000, "FILE_REFERENCE_COUNT")
    require(
        seen
        and not active
        and len({(r["owner"], r["sha256"]) for r in rows}) == len(rows),
        "INCOMPLETE_OR_DUPLICATE_COPY",
    )
    return rows


def copy_candidates(root, destination, *, uid=10001):
    custody.private(root, uid=uid, directory=True)
    result = {}
    total = 0
    for owner in root.iterdir():
        require(str(UUID(owner.name)) == owner.name, "STORAGE_OWNER_DIRECTORY")
        custody.private(owner, uid=uid, directory=True)
        for source in owner.iterdir():
            require(re.fullmatch("[a-f0-9]{64}", source.name), "STORAGE_OBJECT_NAME")
            custody.private(source, uid=uid)
            with os.fdopen(os.open(source, os.O_RDONLY | os.O_NOFOLLOW), "rb") as f:
                data = f.read(4 * 1024 * 1024 + 1)
            require(
                0 < len(data) <= 4 * 1024 * 1024
                and hashlib.sha256(data).hexdigest() == source.name,
                "STORAGE_OBJECT_CORRUPT",
            )
            result[(owner.name, source.name)] = {
                "owner": owner.name,
                "sha256": source.name,
                "size": len(data),
            }
            target = destination / source.name
            if not target.exists():
                total += len(data)
                require(total <= MAX, "LOCAL_SNAPSHOT_CAP")
                with os.fdopen(
                    os.open(
                        target,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o600,
                    ),
                    "wb",
                ) as f:
                    f.write(data)
            require(len(result) <= 1000, "STORAGE_OBJECT_COUNT")
    return result


def select_files(refs, candidates, folder):
    for row in refs:
        require(
            candidates.get((row["owner"], row["sha256"])) == row,
            "SNAPSHOT_REFERENCES_UNCOPIED_FILE_RETRY_NEXT_SCHEDULE",
        )
    keep = {r["sha256"] for r in refs}
    for file in folder.iterdir():
        if file.name not in keep:
            file.unlink()
    return sorted(
        {
            r["sha256"]: {"sha256": r["sha256"], "size": r["size"]} for r in refs
        }.values(),
        key=lambda r: r["sha256"],
    )


def load_legacy(config):
    # Established release infrastructure is a pinned dependency; no application
    # imports or sibling checkout is consulted at runtime.
    for entry in config["legacy_modules"].values():
        require(
            custody.pinned_public_file(Path(entry["path"]), entry["sha256"]),
            "EXISTING_BACKUP_MODULE_CHANGED",
        )
    for name in ["backup", "database_snapshots"]:
        p = config["legacy_modules"][name]["path"]
        spec = importlib.util.spec_from_file_location(name, p)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules["database_snapshots"]


def transport_values(config):
    source = custody.runtime_values(Path(config["existing_transport_env"]))
    keys = {
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "S3_ENDPOINT",
        "S3_REGION",
        "S3_BUCKET",
    }
    values = {k: v for k, v in source.items() if k in keys}
    require(keys - {"AWS_SESSION_TOKEN"} <= set(values), "EXISTING_S3_CUSTODY_MISSING")
    return values


def database_transport(config, payload, *, encrypt=False):
    profile = config["database_transport"]
    script = custody.pinned_public_file(Path(profile["path"]), profile["sha256"])
    mounts = ["-v", str(script) + ":/app/backup.mjs:ro"]
    if encrypt:
        crypto = custody.pinned_public_file(
            Path(profile["crypto_path"]), profile["crypto_sha256"]
        )
        custody.pinned_public_file(
            Path("/etc/onesa/recovery-public.pem"), config["recovery_public_sha256"]
        )
        mounts += [
            "-v",
            str(crypto) + ":/app/oracle_backup_payload.mjs:ro",
            "-v",
            "/etc/onesa/recovery-public.pem:/recovery/public.pem:ro",
        ]
    with tempfile.TemporaryDirectory(prefix=".database-transport-", dir=STATE) as tmp:
        env = Path(tmp) / "transport.env"
        custody.write_raw(
            env,
            "".join(
                k + "=" + v + "\n" for k, v in transport_values(config).items()
            ).encode(),
        )
        return custody.docker(
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
            *mounts,
            "--entrypoint",
            "node",
            config["transport_image"],
            "/app/backup.mjs",
            data=custody.canonical(payload),
            timeout=90,
        )


def transport(config, payload, folder, receipts):
    script = Path(__file__).with_name("oracle_twin_backup_transport.mjs")
    crypto = script.with_name("oracle_twin_backup_crypto.mjs")
    for p in [script, crypto]:
        require(
            custody.sha(custody.private(p)) == config["file_transport_sha256"][p.name],
            "FILE_TRANSPORT_CHANGED",
        )
    require(
        re.fullmatch("sha256:[a-f0-9]{64}", config["transport_image"]),
        "IMMUTABLE_BACKUP_TRANSPORT_REQUIRED",
    )
    # Narrow the established backup credential to its existing S3 transport only.
    values = transport_values(config)
    with tempfile.TemporaryDirectory(prefix=".transport-", dir=STATE) as tmp:
        env = Path(tmp) / "transport.env"
        with os.fdopen(
            os.open(env, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600),
            "w",
        ) as f:
            f.write("".join(k + "=" + v + "\n" for k, v in values.items()))
        raw = custody.docker(
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
            str(CONFIG) + ":/private/transport.json:ro",
            "-v",
            str(folder) + ":/private/files:ro",
            "-v",
            str(receipts) + ":/private/receipts:rw",
            "-v",
            "/etc/onesa/recovery-public.pem:/recovery/public.pem:ro",
            "-v",
            str(script) + ":/app/ai_backup.mjs:ro",
            "-v",
            str(crypto) + ":/app/oracle_twin_backup_crypto.mjs:ro",
            "--entrypoint",
            "node",
            config["transport_image"],
            "/app/ai_backup.mjs",
            data=custody.canonical(payload),
            timeout=120,
        )
    result = json.loads(raw)
    require(
        result["status"] == "PASS"
        and result["automatic_deletion"] is False
        and result["cap_bytes"] == MAX,
        "ENCRYPTED_FILES_NOT_VERIFIED",
    )
    return result


def prior_receipts():
    result = {}
    for p in sorted(STATE.glob("*/files/*.intent.json")):
        row = custody.read(p)
        key = (row["key_id"], row["sha256"])
        require(
            key not in result or result[key] == row,
            "CONFLICTING_BACKUP_CIPHERTEXT_INTENTS",
        )
        result[key] = row
    return result


def application_runtime():
    row = custody.inventory()[custody.TARGET["production"]]
    require(custody.healthy(row), "BACKUP_APPLICATION_UNHEALTHY")
    return {
        "source_commit": row["Config"]["Labels"]["org.onesa.source-commit"],
        "image": row["Image"],
        "container_id": row["Id"],
        "runtime_sha256": custody.sha(custody.private(custody.ENV["production"])),
    }


def receipt_binding(receipt, config):
    require(
        receipt["source_commit"] == config["source_commit"]
        and receipt["release_candidate_commit"] == config["release_candidate_commit"]
        and receipt["producer_sha256"] == config["producer_sha256"]
        and receipt["application_runtime"] == application_runtime(),
        "BACKUP_RECEIPT_SOURCE_OR_RUNNING_APPLICATION_CHANGED",
    )


def run(*, inspect=False):
    require(
        os.geteuid() == 0 and not os.getenv("GITHUB_ACTIONS"),
        "ROOT_BACKUP_INFRASTRUCTURE_ONLY",
    )
    config = custody.read(CONFIG)
    require(
        config["schema_version"] == 1
        and config["automatic_deletion"] is False
        and config["cap_bytes"] == MAX,
        "BACKUP_PROFILE",
    )
    require(
        custody.sha(custody.private(Path(__file__))) == config["producer_sha256"],
        "PINNED_BACKUP_PRODUCER_REQUIRED",
    )
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    custody.private(STATE, directory=True)
    # Share the established AI lock with the retained DB-only timer. Otherwise
    # two writers could independently pass the cumulative prefix cap check.
    lock_path = Path("/var/lib/onesa/operations/database-backup-ai.lock")
    if lock_path.exists():
        custody.private(lock_path)
    with os.fdopen(
        os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600), "a"
    ) as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if inspect:
            last = custody.read(STATE / "latest.json")
            folder = STATE / last["id"]
            receipt = custody.read(folder / "receipt.json")
            require(
                custody.sha(folder / "receipt.json") == last["sha256"]
                and receipt["source_commit"] == config["source_commit"],
                "BACKUP_RECEIPT_BINDING",
            )
            receipt_binding(receipt, config)
            files = [
                {"sha256": r["sha256"], "size": r["size"], "prior": r}
                for r in receipt["file_receipts"]
            ]
            file_observation = transport(
                config,
                {"action": "inspect", "files": files},
                folder / "staged",
                folder / "files",
            )
            raw = database_transport(
                config, {"action": "read", "key": receipt["database"]["object_key"]}
            )
            require(
                hashlib.sha256(raw).hexdigest()
                == receipt["database"]["ciphertext_sha256"],
                "DATABASE_CIPHERTEXT_CHANGED",
            )
            return {
                **receipt,
                "off_instance_readback": "PASS",
                "receipt_sha256": last["sha256"],
                "file_readback": file_observation,
            }
        runtime_before = application_runtime()
        operation = uuid4().hex
        folder = STATE / operation
        folder.mkdir(mode=0o700)
        staged = folder / "staged"
        staged.mkdir(mode=0o700)
        receipts = folder / "files"
        receipts.mkdir(mode=0o700)
        custody.write(
            folder / "intent.json",
            {
                "id": operation,
                "source_commit": config["source_commit"],
                "release_candidate_commit": config["release_candidate_commit"],
                "application_runtime": runtime_before,
                "producer_sha256": config["producer_sha256"],
                "provider_retry": False,
            },
        )
        try:
            candidates = copy_candidates(Path(config["storage_root"]), staged)
            legacy = load_legacy(config)
            settings, uri = legacy.settings_for(
                "ai", legacy.private_json(legacy.CONFIG)
            )
            require(
                settings["ONESA_DIGITAL_TWINS_STORAGE_DIRECTORY"]
                == "/var/lib/onesa/twins",
                "BACKUP_STORAGE_CONFIGURATION",
            )
            dump, manifest = legacy.pg_snapshot(uri)
            # pg_restore emits the exact twin_files rows from this same exported
            # database snapshot; it never connects to a target or executes SQL.
            rows = custody.docker(
                "run",
                "--rm",
                "-i",
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges:true",
                "--entrypoint",
                "pg_restore",
                PG,
                "--data-only",
                "--table=twin_files",
                "--file=-",
                data=dump,
                timeout=30,
            )
            refs = (
                references(rows)
                if any(row["table"] == "twin_files" for row in manifest)
                else []
            )
            require(
                bool(refs)
                or not candidates
                or any(row["table"] == "twin_files" for row in manifest),
                "FILES_EXIST_WITHOUT_REGISTERED_SCHEMA",
            )
            files = select_files(refs, candidates, staged)
            key_id = custody.sha(
                custody.pinned_public_file(
                    Path("/etc/onesa/recovery-public.pem"),
                    config["recovery_public_sha256"],
                )
            )
            prior = prior_receipts()
            for file in files:
                if (key_id, file["sha256"]) in prior:
                    file["prior"] = prior[(key_id, file["sha256"])]
            result = transport(
                config, {"action": "put", "files": files}, staged, receipts
            )
            payload = {
                "action": "database-backup",
                "product": "ai",
                "id": operation,
                "snapshot": base64.b64encode(dump).decode(),
                "manifest": manifest,
            }
            raw = database_transport(config, payload, encrypt=True)
            db = json.loads(raw)
            require(
                db["passed"] is True
                and db["id"] == operation
                and db["product"] == "ai"
                and db["snapshot_sha256"] == hashlib.sha256(dump).hexdigest()
                and db["key_id"] == key_id,
                "DATABASE_BACKUP_NOT_VERIFIED",
            )
            receipt = {
                "status": "PASS",
                "id": operation,
                "source_commit": config["source_commit"],
                "release_candidate_commit": config["release_candidate_commit"],
                "application_runtime": runtime_before,
                "producer_sha256": config["producer_sha256"],
                "verified_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "consistent_snapshot": True,
                "coordinated_snapshot": True,
                "encrypted": True,
                "automatic_deletion": False,
                "schema_revision": "20261025_twins"
                if any(row["table"] == "twin_files" for row in manifest)
                else "pre-twins-additive-schema",
                "database": db,
                "file_references": refs,
                "file_receipts": result["files"],
                "key_id": key_id,
            }
            receipt_binding(receipt, config)
            custody.write(folder / "receipt.json", receipt)
            temp = STATE / (operation + ".latest")
            custody.write(
                temp, {"id": operation, "sha256": custody.sha(folder / "receipt.json")}
            )
            os.replace(temp, STATE / "latest.json")
            success = Path("/var/lib/onesa/operations/database-backup-ai-success.json")
            temp = success.with_name(operation + ".success.tmp")
            custody.write(
                temp,
                {
                    **db,
                    "verified_at": receipt["verified_at"],
                    "consistent_snapshot": True,
                    "coordinated_snapshot": True,
                    "automatic_deletion": False,
                    "files": len(refs),
                    "coordinated_receipt_sha256": custody.sha(folder / "receipt.json"),
                },
            )
            os.replace(temp, success)
            Path("/var/lib/onesa/operations/database-backup-ai-failure.json").unlink(
                missing_ok=True
            )
            return receipt
        finally:
            # Transient raw copies only; no application file or encrypted archive
            # is deleted. Interrupted provider intents/receipts are retained.
            shutil.rmtree(staged)
            staged.mkdir(mode=0o700)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inspect", action="store_true")
    args = p.parse_args()
    try:
        print(json.dumps(run(inspect=args.inspect)))
    except Exception:  # noqa: BLE001 -- CLI boundary redacts private input and provider diagnostics.
        if os.geteuid() == 0 and not args.inspect:
            path = Path("/var/lib/onesa/operations/database-backup-ai-failure.json")
            temp = path.with_name(uuid4().hex + ".failure.tmp")
            custody.write(
                temp,
                {
                    "at": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "event": "database_backup_failed",
                    "product": "ai",
                    "coordinated_files": True,
                },
            )
            os.replace(temp, path)
        raise SystemExit(
            "Coordinated AI backup failed; inspect retained private intent; no data or credentials logged"
        ) from None
