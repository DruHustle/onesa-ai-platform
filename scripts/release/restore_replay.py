"""Replay a reviewed erasure ledger only inside a labeled network-isolated restore.

A replay receipt never authorizes service activation or proves the ledger is current.
"""

import datetime
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from uuid import UUID

KINDS = {
    "deleted_users": "users",
    "deleted_conversations": "conversations",
    "deleted_documents": "documents",
    "deleted_trips": "trips",
    "deleted_agent_runs": "agent_runs",
}


def ledger(path):
    path = Path(path)
    info = path.lstat()
    if (
        path.is_symlink()
        or not path.is_file()
        or info.st_uid != os.getuid()
        or info.st_mode & 0o077
        or info.st_size > 256 * 1024
    ):
        raise ValueError("Private owned ledger required")
    raw = path.read_bytes()
    value = json.loads(raw)
    required = {
        "schema",
        "product",
        "source_backup_sha256",
        "backup_created_at",
        "reconciled_through",
        "events",
        "legal_holds",
    }
    if (
        set(value) != required
        or value["schema"] != 1
        or value["product"] != "ai"
        or not re.fullmatch("[a-f0-9]{64}", value["source_backup_sha256"])
    ):
        raise ValueError("Invalid replay ledger")
    start = datetime.datetime.fromisoformat(value["backup_created_at"])
    end = datetime.datetime.fromisoformat(value["reconciled_through"])
    if (
        start.tzinfo is None
        or end.tzinfo is None
        or not start <= end <= datetime.datetime.now(datetime.timezone.utc)
    ):
        raise ValueError("Invalid replay watermark")
    if set(value["events"]) != set(KINDS) or set(value["legal_holds"]) != set(KINDS):
        raise ValueError("Incomplete replay event categories")
    for ids in [*value["events"].values(), *value["legal_holds"].values()]:
        if not isinstance(ids, list) or len(ids) > 1000:
            raise ValueError("Replay event bound exceeded")
        for identifier in ids:
            if not isinstance(identifier, str) or str(UUID(identifier)) != identifier:
                raise ValueError("Invalid erased record identity")
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate erased record identity")
    if any(
        set(value["events"][kind]) & set(value["legal_holds"][kind]) for kind in KINDS
    ):
        raise ValueError("An erasure event conflicts with a legal hold")
    return value, hashlib.sha256(raw).hexdigest()


def isolated_target(container, database, inspection, value):
    if not re.fullmatch(
        "onesa-isolated-ai-restore-[a-f0-9]{12,32}", container
    ) or not re.fullmatch("onesa_[a-z0-9_]{1,48}_restore", database):
        raise ValueError("Only isolated named restore targets are supported")
    if len(inspection) != 1:
        raise ValueError("Ambiguous restore target")
    item = inspection[0]
    if not re.fullmatch("[a-f0-9]{64}", item.get("Id", "")):
        raise ValueError("Immutable restore container identity required")
    labels = item.get("Config", {}).get("Labels", {})
    if (
        item.get("Name") != "/" + container
        or item.get("HostConfig", {}).get("NetworkMode") != "none"
        or labels.get("org.onesa.restore-scope") != "isolated"
        or labels.get("org.onesa.product") != "ai"
        or labels.get("org.onesa.restore-snapshot-sha256")
        != value["source_backup_sha256"]
        or not item.get("State", {}).get("Running")
        or item.get("State", {}).get("OOMKilled")
        or item.get("HostConfig", {}).get("PortBindings")
        or any(m.get("Type") != "tmpfs" for m in item.get("Mounts", []))
    ):
        raise ValueError("Restore isolation or snapshot binding rejected")
    return item["Id"]


def replay_sql(value, lockdown_sql):
    # UUIDs are validated above; use only fixed table names, never caller SQL.
    commands = [
        "BEGIN;",
        "SET LOCAL statement_timeout='20s';",
        "SET LOCAL lock_timeout='2s';",
    ]
    checks = []
    for kind, table in KINDS.items():
        ids = value["events"][kind]
        if not ids:
            continue
        literal = ",".join(
            "'" + str(UUID(identifier)) + "'::uuid" for identifier in ids
        )
        if kind == "deleted_documents":
            text_ids = ",".join("'" + str(UUID(identifier)) + "'" for identifier in ids)
            commands.append(
                f"DELETE FROM bounded_uploads WHERE result->>'id' IN ({text_ids});"
            )
            checks.append(
                f"IF EXISTS(SELECT 1 FROM bounded_uploads WHERE result->>'id' IN ({text_ids})) THEN RAISE EXCEPTION 'Restored document upload remains'; END IF;"
            )
        commands.append(f"DELETE FROM {table} WHERE id IN ({literal});")
        checks.append(
            f"IF EXISTS(SELECT 1 FROM {table} WHERE id IN ({literal})) THEN RAISE EXCEPTION 'Restore erasure replay incomplete'; END IF;"
        )
    body = lockdown_sql.split("BEGIN;\n", 1)[1].split("COMMIT;\n", 1)[0]
    commands.append(body)
    commands.extend(
        [
            "UPDATE conversations SET active_run_id=NULL,lease_until=NULL;",
            "UPDATE inference_runs SET status='failed' WHERE status='running';",
            "UPDATE agent_runs SET status='failed' WHERE status='running';",
        ]
    )
    checks.extend(
        [
            "IF EXISTS(SELECT 1 FROM auth_sessions WHERE revoked_at IS NULL AND expires_at>now()) THEN RAISE EXCEPTION 'Restored session active'; END IF;",
            "IF EXISTS(SELECT 1 FROM identity_tokens WHERE revoked_at IS NULL AND consumed_at IS NULL AND expires_at>now()) THEN RAISE EXCEPTION 'Restored token active'; END IF;",
            "IF EXISTS(SELECT 1 FROM access_grants WHERE expires_at>now()) THEN RAISE EXCEPTION 'Restored grant active'; END IF;",
            "IF EXISTS(SELECT 1 FROM identity_mail WHERE state IN ('queued','leased')) THEN RAISE EXCEPTION 'Restored mail active'; END IF;",
            "IF EXISTS(SELECT 1 FROM bounded_uploads WHERE expires_at>now()) THEN RAISE EXCEPTION 'Restored upload active'; END IF;",
            "IF EXISTS(SELECT 1 FROM model_leases WHERE expires_at>now()) THEN RAISE EXCEPTION 'Restored model lease active'; END IF;",
        ]
    )
    commands.append("DO $restore$ BEGIN " + " ".join(checks) + " END $restore$;")
    commands.extend(
        ["COMMIT;", "SELECT 'ERASURE_REPLAY_AND_CAPABILITY_LOCKDOWN_PASS';"]
    )
    return "\n".join(commands)


def run(container, database, path, apply, lockdown_sql):
    if not apply:
        raise ValueError("Explicit isolated replay switch required")
    value, digest = ledger(path)
    inspect = json.loads(
        subprocess.check_output(["docker", "inspect", container], timeout=10)
    )
    identity = isolated_target(container, database, inspect, value)
    # Address the immutable container ID after validation; a name cannot be swapped.
    result = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            identity,
            "psql",
            "-U",
            "postgres",
            "-d",
            database,
            "-XqAt",
            "-v",
            "ON_ERROR_STOP=1",
        ],
        input=replay_sql(value, lockdown_sql),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if (
        result.returncode
        or result.stdout.strip() != "ERASURE_REPLAY_AND_CAPABILITY_LOCKDOWN_PASS"
    ):
        raise ValueError("Isolated replay failed; no activation authorized")
    return {
        "result": "PASS",
        "scope": "isolated AI restored-copy erasure replay and capability lockdown",
        "ledger_sha256": digest,
        "reconciled_through": value["reconciled_through"],
        "source_backup_sha256": value["source_backup_sha256"],
        "erasure_events": {kind: len(ids) for kind, ids in value["events"].items()},
        "production_touched": False,
        "activation_authorized": False,
        "remaining": "Owner must establish complete authoritative post-snapshot ledger coverage through the required recovery watermark, restore integrity and release approval before any activation.",
    }
