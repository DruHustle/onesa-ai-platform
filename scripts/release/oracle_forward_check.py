"""Prove forward-schema rollback compatibility using a new offline synthetic DB.

No live URL, credential or existing database is accepted. The candidate runs with
Twins off and mock inference over a private Unix socket to a tmpfs PostgreSQL
container. This is an infrastructure check, not equipment/provider acceptance.
"""

import json
import os
import secrets
import shutil
import sys
import time
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oracle_ai_runner as r
from oracle_twin_restore import PG

PROGRAM = r"""import json,os,secrets
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings
settings=Settings(environment='test',database_url=os.environ['ONESA_DATABASE_URL'],model_backend='mock',embedding_backend='lexical',digital_twins_enabled=False,cybersecurity_enabled=False,cybersecurity_demo_enabled=False,cybersecurity_ai_enabled=False,industrial_demo_enabled=False,secure_cookies=False,registration_mode='open',public_origin='http://localhost:3100')
with TestClient(create_app(settings),base_url="http://localhost:3100") as client:
 assert client.get('/core-ready').status_code==200
 password=secrets.token_urlsafe(32)
 response=client.post('/api/v1/auth/register',json={'email':'forward-'+secrets.token_hex(12)+'@example.com','password':password,'display_name':'Isolated forward rollback proof'},headers={'Origin':'http://localhost:3100'})
 assert response.status_code==201
 headers={'Origin':'http://localhost:3100','X-CSRF-Token':client.cookies.get('onesa_csrf')}
 created=client.post('/api/v1/conversations',json={'title':'Synthetic forward rollback proof'},headers=headers)
 assert created.status_code==201
 assert client.get('/api/v1/conversations/'+created.json()['id']).status_code==200
 assert client.get('/api/v1/twins/readiness').status_code==404
 assert client.get('/api/v1/cybersecurity/readiness').status_code==404
 assert client.get('/api/v1/cybersecurity/workspace').status_code==404
 print(json.dumps({'core_ready':'PASS','authentication':'PASS','owned_conversation_persistence':'PASS','twins_disabled':'PASS','cybersecurity_disabled':'PASS','model_backend':'mock'}))
"""


def check(folder, binding, operation):
    r.require(str(UUID(operation)) == operation, "FORWARD_CHECK_OPERATION")
    name = "onesa-forward-check-" + UUID(operation).hex
    socket = folder / "forward-check-socket"
    socket.mkdir(mode=0o700)
    os.chown(socket, 999, 999)
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
        "ONESA_DATABASE_URL=postgresql+psycopg://onesa_restore:synthetic@localhost/onesa_forward_test",
        "--entrypoint",
        "alembic",
        binding["artifact_digest"],
        "upgrade",
        "20261026_cybersecurity",
        "--sql",
        timeout=60,
    )
    r.require(
        sql.startswith(b"BEGIN;") and len(sql) <= 2 * 1024 * 1024,
        "FORWARD_SCHEMA_OUTPUT_BOUND",
    )
    r.write(
        folder / "forward-check-intent.json",
        {
            "binding": binding,
            "operation_id": operation,
            "container": name,
            "network": "none",
            "production_writes": 0,
        },
    )
    started = False

    def query(database, statement):
        r.require(
            database in ["onesa_forward_test", "onesa_forward_restore_test"],
            "ISOLATED_FORWARD_DATABASE_ONLY",
        )
        return (
            r.docker(
                "exec",
                "-i",
                name,
                "psql",
                "-XqAt",
                "-U",
                "onesa_restore",
                "-d",
                database,
                "-v",
                "ON_ERROR_STOP=1",
                data=statement.encode(),
                timeout=45,
            )
            .decode()
            .strip()
        )

    try:
        r.docker(
            "run",
            "-d",
            "--pull=never",
            "--name",
            name,
            "--label",
            "org.onesa.release-operation=" + operation,
            "--network",
            "none",
            "--user",
            "999:999",
            "--tmpfs",
            "/var/lib/postgresql/data:rw,mode=700,uid=999,gid=999,size=512m",
            "-v",
            str(socket) + ":/var/run/postgresql:rw",
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
            "POSTGRES_DB=onesa_forward_test",
            "-e",
            "POSTGRES_PASSWORD=" + secrets.token_urlsafe(32),
            PG,
            timeout=30,
        )
        started = True
        deadline = time.monotonic() + 60
        while True:
            try:
                query("onesa_forward_test", "SELECT 1;")
                break
            except r.Refused:
                r.require(time.monotonic() < deadline, "FORWARD_DATABASE_STARTUP")
                time.sleep(0.25)
        query("onesa_forward_test", sql.decode())
        response = r.docker(
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--user",
            "999:999",
            "--tmpfs",
            "/tmp:rw,mode=1777",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "-e",
            "HOME=/tmp",
            "-e",
            "ONESA_DATABASE_URL=postgresql+psycopg://onesa_restore@/onesa_forward_test?host=/var/run/postgresql",
            "-v",
            str(socket) + ":/var/run/postgresql:ro",
            "--entrypoint",
            "python",
            binding["artifact_digest"],
            "-c",
            PROGRAM,
            timeout=90,
        )
        checks = json.loads(response)
        r.require(
            all(
                checks.get(k) == "PASS"
                for k in [
                    "core_ready",
                    "authentication",
                    "owned_conversation_persistence",
                    "twins_disabled",
                    "cybersecurity_disabled",
                ]
            ),
            "FUTURE_SCHEMA_ROLLBACK_NOT_COMPATIBLE",
        )
        dump = r.docker(
            "exec",
            name,
            "pg_dump",
            "-U",
            "onesa_restore",
            "-d",
            "onesa_forward_test",
            "-Fc",
            "--no-owner",
            "--no-acl",
            timeout=60,
        )
        r.docker(
            "exec",
            name,
            "createdb",
            "-U",
            "onesa_restore",
            "onesa_forward_restore_test",
            timeout=20,
        )
        r.docker(
            "exec",
            "-i",
            name,
            "pg_restore",
            "-U",
            "onesa_restore",
            "-d",
            "onesa_forward_restore_test",
            "--no-owner",
            "--no-acl",
            "--exit-on-error",
            data=dump,
            timeout=60,
        )
        manifest = {}
        for table in ["users", "conversations", "messages"]:
            statement = (
                "SELECT encode(sha256(convert_to(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),''),'UTF8')),'hex') FROM "
                + table
                + " t;"
            )
            before = query("onesa_forward_test", statement)
            after = query("onesa_forward_restore_test", statement)
            r.require(before == after, "FORWARD_SYNTHETIC_RESTORE_CONTENT_DIFFERS")
            manifest[table] = after
        result = {
            "status": "PASS",
            "binding": binding,
            "operation_id": operation,
            "schema_revision": "20261026_cybersecurity",
            "candidate_image": binding["artifact_digest"],
            "twins_disabled": True,
            "cybersecurity_disabled": True,
            "checks": checks,
            "synthetic_database_restore": "PASS",
            "restored_tables": manifest,
            "production_writes": 0,
            "scope": "offline synthetic forward-schema rollback compatibility; no production data or inference",
        }
        r.write(folder / "forward-check-receipt.json", result)
        return result
    finally:
        if started:
            row = json.loads(r.docker("inspect", name))[0]
            r.require(
                row["Config"]["Labels"].get("org.onesa.release-operation") == operation
                and row["HostConfig"]["NetworkMode"] == "none",
                "FORWARD_CLEANUP_SCOPE",
            )
            r.docker("rm", "-f", name, timeout=30)
        shutil.rmtree(socket)
