"""Restore only two newly created release fixtures into a disposable offline DB.

No production URL is accepted. PostgreSQL has no network or published port. Both
databases exist only inside a new operation-labelled container on tmpfs. Raw
fixture files are removed afterward; original application data is never altered.
"""

import hashlib
import json
import os
import re
import secrets
import shutil
import sys
import time
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oracle_ai_runner as r

PG = "pgvector/pgvector:pg16@sha256:7b822b0aac60967beb1ea5e576b8602c94c300a157d187f385ae3e0da199b90a"
TABLES = [
    "users",
    "twin_files",
    "twin_templates",
    "twin_assets",
    "twin_models",
    "twin_notes",
    "twin_sources",
    "twin_readings",
    "twin_events",
]


def validate(bundle, binding, operation):
    r.require(
        bundle["binding"] == binding
        and bundle["operation_id"] == operation
        and bundle["scope"] == "new-owned-release-fixtures-only",
        "RESTORE_FIXTURE_BINDING",
    )
    r.require(
        set(bundle["tables"]) == set(TABLES) and len(bundle["tables"]["users"]) == 2,
        "RESTORE_FIXTURE_TABLE_SCOPE",
    )
    users = bundle["tables"]["users"]
    owners = {row["id"] for row in users}
    r.require(
        len(owners) == 2
        and all(
            str(UUID(row["id"])) == row["id"]
            and re.fullmatch(
                "release-audit-[0-9]+-[a-f0-9]{24}@example.com", row["email"]
            )
            for row in users
        ),
        "RESTORE_IDENTITY_SCOPE",
    )
    assets = {row["id"] for row in bundle["tables"]["twin_assets"]}
    for name, rows in bundle["tables"].items():
        r.require(len(rows) <= 1000, "RESTORE_ROW_BOUND")
        if name == "users":
            continue
        for row in rows:
            r.require(
                row.get("user_id") in owners
                if name not in ["twin_readings", "twin_events"]
                else row.get("asset_id") in assets,
                "FOREIGN_RECORD_IN_RESTORE_FIXTURE",
            )
    refs = bundle["tables"]["twin_files"]
    r.require(
        refs
        and len(refs) <= 10
        and all(
            re.fullmatch("[a-f0-9]{64}", f["sha256"])
            and type(f["size"]) is int
            and 0 < f["size"] <= 4194304
            for f in refs
        ),
        "RESTORE_FILE_BOUND",
    )
    return refs


def query(container, database, sql):
    r.require(
        re.fullmatch("onesa-twin-restore-[a-f0-9]{32}", container)
        and database in ["onesa_fixture_test", "onesa_fixture_test_restore"],
        "DISPOSABLE_RESTORE_TARGET_ONLY",
    )
    return (
        r.docker(
            "exec",
            "-i",
            container,
            "psql",
            "-XqAt",
            "-U",
            "onesa_restore",
            "-d",
            database,
            "-v",
            "ON_ERROR_STOP=1",
            data=sql.encode(),
            timeout=60,
        )
        .decode()
        .strip()
    )


def manifest(container, database):
    result = {}
    for table in TABLES:
        sql = (
            "SELECT json_build_object('count',count(*),'sha256',encode(sha256(convert_to(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),''),'UTF8')),'hex')) FROM public."
            + table
            + " t;"
        )
        result[table] = json.loads(query(container, database, sql))
    return result


def capture_fixture_files(folder, binding, operation, storage):
    bundle = r.read(folder / "restore-fixtures.json")
    refs = validate(bundle, binding, operation)
    r.private(Path(storage), uid=10001, directory=True)
    root = folder / "restore-files"
    root.mkdir(mode=0o700)
    for row in refs:
        source = Path(storage) / row["user_id"] / row["sha256"]
        r.private(source, uid=10001)
        with os.fdopen(os.open(source, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
            data = stream.read(4 * 1024 * 1024 + 1)
        r.require(
            len(data) == row["size"]
            and hashlib.sha256(data).hexdigest() == row["sha256"],
            "OWNED_FIXTURE_FILE_CHANGED",
        )
        owner = root / row["user_id"]
        owner.mkdir(mode=0o700, exist_ok=True)
        target = owner / row["sha256"]
        if not target.exists():
            r.write_raw(target, data)


def recover_encrypted_file(data, tool_image):
    # Temporary recovery keys exist only in this network-isolated process.
    # Exercise the exact new envelope without requesting production private keys.
    script = r.private(Path(__file__).with_name("oracle_twin_backup_crypto.mjs"))
    program = "import crypto from 'node:crypto';import fs from 'node:fs';import {sealFile,openFile,sha} from '/private/crypto.mjs';const b=fs.readFileSync(0),k=crypto.generateKeyPairSync('rsa',{modulusLength:2048,publicKeyEncoding:{type:'spki',format:'pem'},privateKeyEncoding:{type:'pkcs8',format:'pem'}});const e=Buffer.from(JSON.stringify(sealFile(b,k.publicKey)));process.stdout.write(openFile(e,k.privateKey,{ciphertext_sha256:sha(e),sha256:sha(b),size:b.length}));"
    restored = r.docker(
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
        "--memory",
        "128m",
        "-v",
        str(script) + ":/private/crypto.mjs:ro",
        "--entrypoint",
        "node",
        tool_image,
        "--input-type=module",
        "-e",
        program,
        data=data,
        timeout=30,
    )
    r.require(restored == data, "ENCRYPTED_FIXTURE_RECOVERY_FAILED")
    return restored


def restore(folder, binding, operation):
    r.require(str(UUID(operation)) == operation, "RESTORE_OPERATION_UUID")
    bundle_path = folder / "restore-fixtures.json"
    r.require(bundle_path.stat().st_size <= 16 * 1024 * 1024, "RESTORE_BUNDLE_BOUND")
    bundle = r.read(bundle_path)
    refs = validate(bundle, binding, operation)
    tool = r.trusted_toolchain(r.read(r.PLAN))
    container = "onesa-twin-restore-" + UUID(operation).hex
    sql = r.docker(
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "-e",
        "ONESA_DATABASE_URL=postgresql+psycopg://onesa_restore:disposable@localhost/onesa_fixture_test",
        "--entrypoint",
        "alembic",
        binding["artifact_digest"],
        "upgrade",
        "20261025_twins",
        "--sql",
        timeout=60,
    )
    r.require(
        sql.startswith(b"BEGIN;") and len(sql) < 2 * 1024 * 1024, "OFFLINE_SCHEMA_BOUND"
    )
    # Persisted operation intent precedes the first disposable container request.
    r.write(
        folder / "restore-intent.json",
        {
            "operation_id": operation,
            "container": container,
            "binding": binding,
            "network": "none",
            "production_writes": 0,
        },
    )
    cleanup = False
    try:
        r.docker(
            "run",
            "-d",
            "--pull=never",
            "--name",
            container,
            "--label",
            "org.onesa.release-operation=" + operation,
            "--network",
            "none",
            "--user",
            "999:999",
            "--tmpfs",
            "/var/lib/postgresql/data:rw,uid=999,gid=999,mode=700,size=512m",
            "--tmpfs",
            "/var/run/postgresql:rw,uid=999,gid=999",
            "--memory",
            "512m",
            "--cpus",
            "1",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "-e",
            "POSTGRES_USER=onesa_restore",
            "-e",
            "POSTGRES_DB=onesa_fixture_test",
            "-e",
            "POSTGRES_PASSWORD=" + secrets.token_urlsafe(32),
            PG,
            timeout=30,
        )
        cleanup = True
        deadline = time.monotonic() + 60
        while True:
            try:
                query(container, "onesa_fixture_test", "SELECT 1;")
                break
            except r.Refused:
                r.require(time.monotonic() < deadline, "DISPOSABLE_DATABASE_STARTUP")
                time.sleep(0.5)
        query(container, "onesa_fixture_test", sql.decode())
        for table in TABLES:
            payload = json.dumps(bundle["tables"][table], allow_nan=False).replace(
                "'", "''"
            )
            query(
                container,
                "onesa_fixture_test",
                "INSERT INTO public."
                + table
                + " SELECT * FROM json_populate_recordset(NULL::public."
                + table
                + ", '"
                + payload
                + "'::json);",
            )
        before = manifest(container, "onesa_fixture_test")
        dump = r.docker(
            "exec",
            container,
            "pg_dump",
            "-U",
            "onesa_restore",
            "-d",
            "onesa_fixture_test",
            "-Fc",
            "--no-owner",
            "--no-acl",
            timeout=60,
        )
        r.require(
            dump.startswith(b"PGDMP") and len(dump) <= 16 * 1024 * 1024,
            "DISPOSABLE_DUMP_BOUND",
        )
        r.docker(
            "exec",
            container,
            "createdb",
            "-U",
            "onesa_restore",
            "onesa_fixture_test_restore",
            timeout=20,
        )
        r.docker(
            "exec",
            "-i",
            container,
            "pg_restore",
            "-U",
            "onesa_restore",
            "-d",
            "onesa_fixture_test_restore",
            "--no-owner",
            "--no-acl",
            "--exit-on-error",
            data=dump,
            timeout=60,
        )
        after = manifest(container, "onesa_fixture_test_restore")
        r.require(after == before, "RESTORED_DATABASE_MANIFEST_DIFFERS")
        restored = folder / "restored-fixture-files"
        restored.mkdir(mode=0o700)
        files = []
        for row in refs:
            source = folder / "restore-files" / row["user_id"] / row["sha256"]
            r.private(source)
            data = source.read_bytes()
            r.require(
                len(data) == row["size"]
                and hashlib.sha256(data).hexdigest() == row["sha256"],
                "FIXTURE_FILE_CORRUPT",
            )
            target = restored / row["user_id"]
            target.mkdir(mode=0o700, exist_ok=True)
            with os.fdopen(
                os.open(
                    target / row["sha256"],
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                ),
                "wb",
            ) as f:
                f.write(recover_encrypted_file(data, tool["cli_image"]))
            r.require(
                r.sha(target / row["sha256"]) == row["sha256"],
                "RESTORED_FILE_DIGEST_DIFFERS",
            )
            files.append({"sha256": row["sha256"], "size": row["size"]})
        result = {
            "status": "PASS",
            "binding": binding,
            "operation_id": operation,
            "schema_revision": "20261025_twins",
            "database_manifest_matches": True,
            "file_hashes_match": True,
            "encrypted_fixture_recovery": "PASS",
            "fixture_owners": len({u["id"] for u in bundle["tables"]["users"]}),
            "database_manifest": after,
            "file_manifest": files,
            "dump_sha256": hashlib.sha256(dump).hexdigest(),
            "production_writes": 0,
            "scope": "new owned fixtures only; offline PostgreSQL dump/restore plus encrypted private file recovery with ephemeral test keys; production archive decryption is not claimed",
        }
        r.write(folder / "restore-receipt.json", result)
        return result
    finally:
        if cleanup:
            actual = json.loads(r.docker("inspect", container))[0]
            r.require(
                actual["Config"]["Labels"].get("org.onesa.release-operation")
                == operation
                and actual["HostConfig"]["NetworkMode"] == "none"
                and not actual["HostConfig"].get("PortBindings"),
                "DISPOSABLE_CLEANUP_SCOPE_CHANGED",
            )
            r.docker("rm", "-f", container, timeout=30)
        bundle_path.unlink(missing_ok=True)
        for name in ["restore-files", "restored-fixture-files"]:
            p = folder / name
            if p.exists():
                shutil.rmtree(p)
