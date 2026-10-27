"""Install two AI-only migration-owner bindings after bounded read-only validation.

New owner-operated command. It does not run a migration, rotate a credential,
change a database role, issue release records or grant application DDL rights.
Secrets enter a hidden terminal prompt or private stdin, never arguments/output.
"""

import argparse
import getpass
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

PLAN = Path("/etc/onesa/oracle-ai-migration-custody.json")
PARENT = Path("/etc/onesa/backends")
RECEIPTS = Path("/var/lib/onesa/release-verification/ai-api")


class Refused(ValueError):
    pass


def require(value, code):
    if not value:
        raise Refused(code)


def private(path, directory=False):
    path = Path(path)
    require(
        path.is_absolute() and not any(p.is_symlink() for p in [path, *path.parents]),
        "CUSTODY_ALIAS",
    )
    s = path.stat()
    require(
        s.st_uid == 0
        and s.st_mode & 0o077 == 0
        and (path.is_dir() if directory else path.is_file() and s.st_nlink == 1),
        "PRIVATE_ROOT_CUSTODY_REQUIRED",
    )
    require(
        all(
            p.stat().st_uid == 0 and p.stat().st_mode & 0o022 == 0 for p in path.parents
        ),
        "UNTRUSTED_CUSTODY_ANCESTOR",
    )
    return path


def values(path):
    rows = private(path).read_text().splitlines()
    result = dict(line.split("=", 1) for line in rows if line)
    require(
        len(result) == len([line for line in rows if line]),
        "DUPLICATE_CONFIGURATION_KEY",
    )
    return result


def target(uri, *, runtime_reference=False):
    require(
        isinstance(uri, str)
        and len(uri) < 4096
        and not any(c in uri for c in "\r\n\x00"),
        "DATABASE_URI_SHAPE",
    )
    u = urlsplit(uri)
    require(
        u.scheme in ["postgresql", "postgresql+psycopg"]
        and u.hostname
        and u.password
        and u.username
        and u.path == "/neondb"
        and not u.fragment,
        "DATABASE_URI_PROFILE",
    )
    options = parse_qsl(u.query, strict_parsing=True)
    require(
        len(dict(options)) == len(options)
        and {k for k, v in options}
        <= {"sslmode", "channel_binding", "connect_timeout", "sslrootcert"}
        and dict(options).get("sslrootcert", "/etc/ssl/cert.pem")
        in (
            {"/etc/ssl/cert.pem", "system"}
            if runtime_reference
            else {"/etc/ssl/cert.pem"}
        ),
        "DATABASE_URI_OPTIONS_REFUSED",
    )
    return (u.hostname, u.port or 5432, u.path), u.username


def hardened(uri):
    target(uri)
    u = urlsplit(uri)
    return urlunsplit(
        (
            "postgresql+psycopg",
            u.netloc,
            u.path,
            urlencode(
                {
                    "sslmode": "verify-full",
                    "channel_binding": "require",
                    "sslrootcert": "/etc/ssl/cert.pem",
                    "connect_timeout": "10",
                }
            ),
            "",
        )
    )


def validate_target(candidate, runtime):
    proposed, owner = target(candidate)
    # The existing root-owned runtime may use libpq's system trust selection.
    # It is an identity reference, never the supplied migration connection.
    # Owner inputs and hardened() retain the explicit pinned CA restriction.
    actual, user = target(runtime, runtime_reference=True)
    # Neon owner migrations use the direct endpoint for the same database; the
    # application's pooler and direct endpoint are not different environments.
    direct = (actual[0].replace("-pooler.", "."), actual[1], actual[2])
    require(
        proposed == direct and owner != user, "AI_TARGET_OR_SEPARATE_OWNER_MISMATCH"
    )
    return hashlib.sha256(
        json.dumps(direct, separators=(",", ":")).encode()
    ).hexdigest()


PROBE = """import json,sys,psycopg
request=json.load(sys.stdin)
uri=request['uri'].replace('postgresql+psycopg://','postgresql://')
with psycopg.connect(uri,connect_timeout=10,sslmode='verify-full',sslrootcert='/etc/ssl/cert.pem',channel_binding='require') as db:
 with db.cursor() as q:
  q.execute('BEGIN READ ONLY');q.execute(\"SET LOCAL statement_timeout='5s'\")
  q.execute(\"SELECT current_database(),has_schema_privilege(current_user,'public','CREATE'),pg_has_role(current_user,c.relowner,'USAGE') FROM pg_class c WHERE c.oid='alembic_version'::regclass\")
  row=q.fetchone();q.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()');tls=q.fetchone()[0]
  q.execute('SELECT version_num FROM alembic_version');schema=q.fetchone()[0]
  print(json.dumps({'database_matches':row[0]=='neondb','schema_create':row[1],'migration_table_owner':row[2],'tls':tls,'schema':schema,'SQL_writes':0}))
"""


def observe(env, uri, plan):
    name = "onesa-ai-oracle-api-" + env + "-1"
    r = subprocess.run(
        ["/usr/bin/docker", "inspect", name],
        capture_output=True,
        timeout=15,
        check=False,
    )
    require(r.returncode == 0, "CURRENT_AI_RUNTIME_UNAVAILABLE")
    row = json.loads(r.stdout)[0]
    require(
        row["Image"] == plan["baseline"][env]["image"]
        and row["Config"]["Labels"].get("org.onesa.source-commit")
        == plan["baseline"][env]["source"],
        "CURRENT_RUNTIME_DIFFERS_FROM_REVIEWED_BASELINE",
    )
    args = [
        "/usr/bin/docker",
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
        row["Image"],
        "-c",
        PROBE,
    ]
    r = subprocess.run(
        args,
        input=json.dumps({"uri": uri}).encode(),
        capture_output=True,
        timeout=25,
        check=False,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
    )
    require(
        r.returncode == 0 and len(r.stdout) < 4096,
        "OWNER_DATABASE_READONLY_PROBE_FAILED",
    )
    result = json.loads(r.stdout)
    require(
        all(
            result.get(k) is True
            for k in [
                "database_matches",
                "schema_create",
                "migration_table_owner",
                "tls",
            ]
        )
        and result.get("SQL_writes") == 0
        and result.get("schema")
        in [
            "20261010_capacity",
            "20261021_industrial",
            "20261025_twins",
            "20261026_cybersecurity",
        ],
        "OWNER_MIGRATION_PRIVILEGES_OR_SCHEMA_MISMATCH",
    )
    return result


def install(uris):
    require(
        os.geteuid() == 0
        and os.getenv("SUDO_USER") == "ubuntu"
        and not os.getenv("GITHUB_ACTIONS"),
        "EXISTING_OWNER_SSH_SUDO_REQUIRED",
    )
    require(set(uris) == {"staging", "production"}, "TWO_AI_ENVIRONMENTS_REQUIRED")
    plan = json.loads(private(PLAN).read_text())
    private(PARENT, directory=True)
    private(RECEIPTS, directory=True)
    prepared = {}
    observations = {}
    for env in ["staging", "production"]:
        path = PARENT / ("ai-" + env + "-migration.env")
        require(
            not path.exists() and not path.is_symlink(),
            "EXISTING_MIGRATION_CUSTODY_PRESERVED_INSPECT_ONLY",
        )
        current = values(PARENT / ("ai-" + env + ".env"))
        identity = validate_target(uris[env], current["ONESA_DATABASE_URL"])
        observation = observe(env, uris[env], plan)
        data = ("ONESA_DATABASE_URL=" + hardened(uris[env]) + "\n").encode()
        prepared[env] = (path, data)
        observations[env] = {
            "target_sha256": identity,
            "binding_sha256": hashlib.sha256(data).hexdigest(),
            "privileges": observation,
        }
    require(
        target(uris["staging"])[0] != target(uris["production"])[0],
        "DATABASE_ENVIRONMENTS_NOT_ISOLATED",
    )
    operation = str(uuid4())
    intent = RECEIPTS / ("migration-custody-" + operation + ".json")

    def write(path, value):
        with os.fdopen(
            os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600),
            "wb",
        ) as f:
            f.write(value)
            f.flush()
            os.fsync(f.fileno())

    write(
        intent,
        json.dumps(
            {
                "state": "CUSTODY_INSTALL_INTENT",
                "operation_id": operation,
                "environments": observations,
                "SQL_writes": 0,
                "release_authority_issued": False,
            }
        ).encode(),
    )
    for path, data in prepared.values():
        write(path, data)
    fd = os.open(PARENT, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    result = {
        "state": "MIGRATION_CUSTODY_READY_NOT_MIGRATED",
        "operation_id": operation,
        "environments": observations,
        "SQL_writes": 0,
        "release_authority_issued": False,
    }
    receipt = RECEIPTS / ("migration-custody-" + operation + "-ready.json")
    write(receipt, json.dumps(result).encode())
    fd = os.open(RECEIPTS, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return {**result, "receipt": str(receipt)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-stdin-json", action="store_true")
    args = p.parse_args()
    if args.private_stdin_json:
        raw = sys.stdin.buffer.read(16385)
        require(len(raw) <= 16384, "PRIVATE_INPUT_BOUND")
        uris = json.loads(raw)
    else:
        uris = {
            env: getpass.getpass(
                "AI " + env + " migration-owner PostgreSQL URI (hidden): "
            )
            for env in ["staging", "production"]
        }
    try:
        result = install(uris)
    finally:
        uris.clear()
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Refused as error:
        raise SystemExit("Migration custody prerequisite: " + str(error)) from None
    except Exception:  # noqa: BLE001 -- CLI boundary redacts private input and provider diagnostics.
        raise SystemExit(
            "Migration custody validation failed; no private values logged; inspect retained intent before retry"
        ) from None
