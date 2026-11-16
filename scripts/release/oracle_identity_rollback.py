"""Rehearse the exact retained AI image against the additive identity schema.

Only new synthetic databases in one isolated, operation-labelled container are
used. No production database, Portal credential or live account is passed to an
application image. The original native feature flags are tested independently
for staging and production; shared identity remains disabled during rollback.
"""

import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oracle_ai_runner as r
from oracle_twin_restore import CYBER_TABLES, PG, TABLES

CHECKS = {
    "core_readiness",
    "local_authentication",
    "ordinary_workflows",
    "native_features",
}
DATABASES = {"onesa_identity_rollback_test", "onesa_identity_restored_test"}
LABEL = "org.onesa.release-operation"


def inventory(expression):
    """Only a successful bounded daemon inventory can establish absence."""
    rows = (
        r.docker(
            "container",
            "ls",
            "--all",
            "--no-trunc",
            "--filter",
            expression,
            "--format",
            "{{.ID}}",
            timeout=10,
        )
        .decode()
        .splitlines()
    )
    r.require(
        len(rows) <= 6
        and len(rows) == len(set(rows))
        and all(re.fullmatch(r"[a-f0-9]{64}", row) for row in rows),
        "IDENTITY_ROLLBACK_INVENTORY_CHANGED",
    )
    return set(rows)


class OwnedContainer:
    """One fresh, named container; no retry or removal by mutable name."""

    def __init__(
        self,
        folder,
        operation,
        role,
        image,
        *,
        binds=(),
        tmpfs=None,
        memory=768,
        pids=128,
    ):
        r.require(
            str(UUID(operation)) == operation
            and re.fullmatch(r"[a-z-]+", role)
            and re.fullmatch(r"sha256:[a-f0-9]{64}", image),
            "IDENTITY_ROLLBACK_CONTAINER_SCOPE",
        )
        self.name = "onesa-identity-rollback-" + UUID(operation).hex + "-" + role
        self.cidfile = folder / ("identity-rollback-" + role + ".cid")
        self.operation, self.role, self.image = operation, role, image
        self.binds = sorted((str(source), target, rw) for source, target, rw in binds)
        self.tmpfs = tmpfs or {"/tmp": "rw,mode=1777,size=256m"}
        self.memory, self.pids = memory, pids
        self.cid = None
        self.file_identity = None
        self.attempted = False
        self.entrypoint = None
        self.arguments = None
        self.environment = None

    def descriptor(self):
        return {
            "name": self.name,
            "cidfile": self.cidfile.name,
            "image_id": self.image,
            "operation_id": self.operation,
            "role": self.role,
            "network": "none",
            "binds": self.binds,
            "tmpfs": self.tmpfs,
            "user": "999:999",
            "memory": self.memory * 1024**2,
            "pids": self.pids,
        }

    def read_cid(self):
        if not self.cidfile.exists():
            r.require(
                not self.cidfile.is_symlink() and self.file_identity is None,
                "IDENTITY_ROLLBACK_CID_CHANGED",
            )
            return None
        path = r.private(self.cidfile)
        before = path.stat()
        r.require(before.st_size in {64, 65}, "IDENTITY_ROLLBACK_CID_FILE")
        value = path.read_text().strip()
        after = path.stat()
        observed = (before.st_dev, before.st_ino, before.st_mtime_ns, value)
        r.require(
            re.fullmatch(r"[a-f0-9]{64}", value)
            and (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_size)
            == (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_size)
            and (self.file_identity is None or self.file_identity == observed)
            and (self.cid is None or self.cid == value),
            "IDENTITY_ROLLBACK_CID_CHANGED",
        )
        self.file_identity, self.cid = observed, value
        return value

    def inspect_owned(self, cid):
        rows = json.loads(r.docker("inspect", cid, timeout=10))
        r.require(
            isinstance(rows, list) and len(rows) == 1,
            "IDENTITY_ROLLBACK_CONTAINER_CHANGED",
        )
        row = rows[0]
        host, config = row["HostConfig"], row["Config"]
        actual_binds = []
        destinations = []
        for mount in row["Mounts"]:
            destinations.append(mount["Destination"])
            if mount["Type"] == "bind":
                actual_binds.append(
                    (mount["Source"], mount["Destination"], mount["RW"])
                )
            else:
                r.require(
                    mount["Type"] == "tmpfs"
                    and mount["Destination"] in self.tmpfs
                    and mount["RW"] is True,
                    "IDENTITY_ROLLBACK_CONTAINER_MOUNT_CHANGED",
                )
        binds = [
            source + ":" + target + (":rw" if rw else ":ro")
            for source, target, rw in self.binds
        ]
        r.require(
            row["Id"] == cid
            and row["Name"] == "/" + self.name
            and row["Image"] == self.image
            and config.get("Labels", {}).get(LABEL) == self.operation
            and config.get("Labels", {}).get("org.onesa.rollback-role") == self.role
            and config["User"] == "999:999"
            and config["Entrypoint"] == [self.entrypoint]
            and config["Cmd"] == self.arguments
            and set(self.environment).issubset(config["Env"])
            and host["NetworkMode"] == "none"
            and set(row["NetworkSettings"].get("Networks", {})) <= {"none"}
            and not host.get("PortBindings")
            and not host.get("PublishAllPorts")
            and host["AutoRemove"] is False
            and host["ReadonlyRootfs"] is True
            and host["Privileged"] is False
            and host.get("CapAdd") in [None, []]
            and host["CapDrop"] == ["ALL"]
            and host["SecurityOpt"] == ["no-new-privileges:true"]
            and host["Memory"] == self.memory * 1024**2
            and host["NanoCpus"] == 1_000_000_000
            and host["PidsLimit"] == self.pids
            and host.get("Tmpfs", {}) == self.tmpfs
            and sorted(host.get("Binds") or []) == binds
            and sorted(actual_binds) == self.binds
            and len(destinations) == len(set(destinations))
            and type(row["State"]["Running"]) is bool,
            "IDENTITY_ROLLBACK_CONTAINER_CHANGED",
        )
        return row

    def observe(self):
        """Reconcile a CID file with exact name inventory after any CLI outcome."""
        self.read_cid()
        named = inventory("name=^/" + self.name + "$")
        r.require(len(named) <= 1, "IDENTITY_ROLLBACK_NAME_CHANGED")
        if not self.attempted:
            r.require(
                not named and self.cid is None,
                "IDENTITY_ROLLBACK_UNEXPECTED_CONTAINER",
            )
            return None
        if self.cid is None and named:
            recovered = next(iter(named))
            self.inspect_owned(recovered)
            self.cid = recovered
        if self.cid is None:
            # A timed-out create may still be pending at the daemon. An absent
            # CID file plus an empty inventory does not resolve that ambiguity.
            r.require(not self.attempted, "IDENTITY_ROLLBACK_CREATE_UNCONFIRMED")
            return None
        identified = inventory("id=" + self.cid)
        r.require(
            identified in [set(), {self.cid}] and named == identified,
            "IDENTITY_ROLLBACK_NAME_CID_MISMATCH",
        )
        return self.inspect_owned(self.cid) if identified else None

    def run(
        self,
        entrypoint,
        arguments,
        *,
        environment=(),
        data=None,
        detached=False,
        timeout=120,
    ):
        r.require(not self.attempted, "IDENTITY_ROLLBACK_CREATE_MUST_NOT_RETRY")
        self.entrypoint, self.arguments = entrypoint, list(arguments)
        self.environment = list(environment)
        r.write(
            self.cidfile.with_suffix(".intent.json"),
            {
                **self.descriptor(),
                "entrypoint": entrypoint,
                "command_sha256": hashlib.sha256(
                    r.canonical(self.arguments)
                ).hexdigest(),
                "input_sha256": hashlib.sha256(data or b"").hexdigest(),
                "automatic_retry": False,
            },
        )
        args = [
            "run",
            "-d" if detached else "-i",
            "--pull=never",
            "--name",
            self.name,
            "--cidfile",
            str(self.cidfile),
            "--label",
            LABEL + "=" + self.operation,
            "--label",
            "org.onesa.rollback-role=" + self.role,
            "--network",
            "none",
            "--read-only",
            "--no-healthcheck",
            "--user",
            "999:999",
            "--memory",
            str(self.memory) + "m",
            "--cpus",
            "1",
            "--pids-limit",
            str(self.pids),
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
        ]
        for destination, options in self.tmpfs.items():
            args.extend(["--tmpfs", destination + ":" + options])
        for source, target, rw in self.binds:
            args.extend(["-v", source + ":" + target + (":rw" if rw else ":ro")])
        for value in environment:
            args.extend(["-e", value])
        args.extend(["--entrypoint", entrypoint, self.image, *arguments])
        self.attempted = True
        previous = os.umask(0o077)
        try:
            response = r.docker(*args, data=data, timeout=timeout)
        finally:
            os.umask(previous)
        r.require(self.read_cid() is not None, "IDENTITY_ROLLBACK_CID_FILE_MISSING")
        observed = self.observe()
        r.require(
            observed is not None
            and observed["State"]["Running"] is detached
            and (detached or observed["State"]["ExitCode"] == 0)
            and (not detached or response.decode().strip() == self.cid),
            "IDENTITY_ROLLBACK_CONTAINER_EXECUTION_UNCONFIRMED",
        )
        return response


def cleanup_owned(containers, operation):
    """Validate every ownership boundary before any single-CID removal."""
    observed = {}
    for container in containers:
        row = container.observe()
        if row is not None:
            r.require(container.attempted, "IDENTITY_ROLLBACK_UNEXPECTED_CONTAINER")
            observed[container.cid] = container
    r.require(
        inventory("label=" + LABEL + "=" + operation) == set(observed),
        "IDENTITY_ROLLBACK_OPERATION_INVENTORY_CHANGED",
    )
    errors = []
    for cid, container in reversed(list(observed.items())):
        # Never remove by name, nor retry a timed-out remove. If that one request
        # fails, still perform read-only observations and preserve its failure.
        container.inspect_owned(cid)
        try:
            r.docker("rm", "-f", cid, timeout=30)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            errors.append(error)
        r.require(
            container.observe() is None,
            "IDENTITY_ROLLBACK_CONTAINER_REMOVAL_UNCONFIRMED",
        )
    r.require(
        not inventory("label=" + LABEL + "=" + operation)
        and all(container.observe() is None for container in containers),
        "IDENTITY_ROLLBACK_FINAL_ABSENCE_UNCONFIRMED",
    )
    if errors:
        raise errors[0]


WORKFLOWS = r"""import secrets
from uuid import UUID,uuid4
from fastapi.testclient import TestClient
def exercise(settings,request):
 features=request['enabled_features']
 assert features==sorted(set(features)) and set(features)<={'twins','cybersecurity'}
 assert settings.digital_twins_enabled==('twins' in features) and settings.cybersecurity_enabled==('cybersecurity' in features) and not getattr(settings,'identity_enabled',False)
 origin=settings.public_origin
 app=create_app(settings)
 fixture=request['fixture']
 if request['phase']=='seed':
  assert fixture is None
  fixture={'primary':{'email':'rollback-'+secrets.token_hex(16)+'@example.com','password':secrets.token_urlsafe(32)},'foreign':{'email':'rollback-'+secrets.token_hex(16)+'@example.com','password':secrets.token_urlsafe(32)}}
 else:
  assert isinstance(fixture,dict) and all(key in fixture for key in ['primary','foreign','conversation'])
 for role in ['primary','foreign']:
  account=fixture[role]
  assert account['email'].startswith('rollback-') and account['email'].endswith('@example.com') and 32<=len(account['password'])<=64
 with TestClient(app,base_url=origin) as client,TestClient(app,base_url=origin) as foreign:
  assert client.get('/core-ready').status_code==200
  for role,current in [('primary',client),('foreign',foreign)]:
   account=fixture[role]
   current.headers['Origin']=origin
   if request['phase']=='seed':
    registered=current.post('/api/v1/auth/register',json={**account,'display_name':'Isolated rollback fixture'})
    assert registered.status_code==201
    account['id']=registered.json()['id']
   logged=current.post('/api/v1/auth/login',json={'email':account['email'],'password':account['password']})
   assert logged.status_code==200 and logged.json()['id']==account['id'] and str(UUID(account['id']))==account['id']
   current.headers['X-CSRF-Token']=current.cookies['onesa_csrf']
  if request['phase']=='seed':
   created=client.post('/api/v1/conversations',json={'title':'Synthetic retained-image rollback'})
   assert created.status_code==201
   fixture['conversation']=created.json()['id']
  assert client.get('/api/v1/conversations/'+fixture['conversation']).status_code==200
  assert foreign.get('/api/v1/conversations/'+fixture['conversation']).status_code==404
  denied=client.post('/api/v1/conversations',json={'title':'Must require CSRF'},headers={'X-CSRF-Token':''})
  assert denied.status_code==403
  if 'twins' in features:
   ready=client.get('/api/v1/twins/readiness')
   assert ready.status_code==200 and ready.json()['ready'] is True
   if request['phase']=='seed':
    template=client.post('/api/v1/twins/templates',json={'name':'Synthetic rollback template','kind':'fixture','components':[{'id':str(uuid4()),'name':'Synthetic component'}]})
    assert template.status_code==201
    created=client.post('/api/v1/twins/assets',json={'template_id':template.json()['id'],'name':'Synthetic rollback asset','serial':'rollback-fixture'})
    assert created.status_code==201
    fixture['twin_asset']=created.json()['id']
   assert client.get('/api/v1/twins/assets/'+fixture['twin_asset']).status_code==200
   assert foreign.get('/api/v1/twins/assets/'+fixture['twin_asset']).status_code==404
   assert any(row['id']==fixture['twin_asset'] for row in client.get('/api/v1/twins/catalog').json()['assets'])
  else:
   assert client.get('/api/v1/twins/readiness').status_code==404
   assert client.get('/api/v1/twins/catalog').status_code==404
  if 'cybersecurity' in features:
   ready=client.get('/api/v1/cybersecurity/readiness')
   assert ready.status_code==200 and ready.json()['enabled'] is True and ready.json()['ai_enabled'] is False
   if request['phase']=='seed':
    created=client.post('/api/v1/cybersecurity/assets',json={'name':'Synthetic rollback security asset','identity':'rollback-'+secrets.token_hex(12),'zone':'Isolated fixture','criticality':'unknown','review_note':'Synthetic local rollback fixture only'})
    assert created.status_code==201
    fixture['cyber_asset']=created.json()['id']
   assert client.get('/api/v1/cybersecurity/assets/'+fixture['cyber_asset']).status_code==200
   assert foreign.get('/api/v1/cybersecurity/assets/'+fixture['cyber_asset']).status_code==404
   assert client.get('/api/v1/cybersecurity/workspace').status_code==200
  else:
   assert client.get('/api/v1/cybersecurity/readiness').status_code==404
   assert client.get('/api/v1/cybersecurity/workspace').status_code==404
  for current in [client,foreign]:
   assert current.post('/api/v1/auth/logout').status_code in {200,204}
   assert current.get('/api/v1/auth/me').status_code==401
 result={'enabled_features':features,'identity_enabled':False,'checks':{key:'PASS' for key in ['core_readiness','local_authentication','ordinary_workflows','native_features']}}
 if request['phase']=='seed':result['fixture']=fixture
 return result
"""

PROGRAM = (
    r"""import json,os,secrets,sys,tempfile
from uuid import UUID,uuid4
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from app.main import create_app
from app.config import Settings
request=json.loads(sys.stdin.buffer.read(65537))
assert set(request)=={'phase','enabled_features','fixture'}
assert request['phase'] in {'seed','verify'}
features=request['enabled_features']
assert isinstance(features,list) and features==sorted(set(features)) and set(features)<={'twins','cybersecurity'}
uri=make_url(os.environ['ONESA_DATABASE_URL'])
assert uri.username=='onesa_restore' and uri.host is None and uri.database in {'onesa_identity_rollback_test','onesa_identity_restored_test'} and str(uri.query.get('host','')).startswith('/')
settings=Settings(environment='test',database_url=os.environ['ONESA_DATABASE_URL'],model_backend='mock',embedding_backend='lexical',identity_enabled=False,digital_twins_enabled='twins' in features,cybersecurity_enabled='cybersecurity' in features,digital_twins_demo_enabled=False,cybersecurity_demo_enabled=False,cybersecurity_ai_enabled=False,industrial_demo_enabled=False,secure_cookies=False,registration_mode='open',public_origin='http://localhost:3100',digital_twins_storage_directory=tempfile.mkdtemp(prefix='onesa-rollback-twins-'),auth_rate_limit=100)
assert not getattr(settings,'identity_enabled',False)
"""
    + WORKFLOWS
    + "\nprint(json.dumps(exercise(settings,request),separators=(',',':')))\n"
)


def bound_environments(binding, plan):
    r.identity_profile(binding, plan)
    old = plan["rollback"]
    retained = old["binding"]
    r.require(
        plan.get("binding") == binding
        and plan.get("expected_schema_revision")
        == plan.get("migration_revision")
        == old.get("compatible_schema_revision")
        == r.IDENTITY_SCHEMA
        and old.get("retain_additive_schema_and_files") is True
        and r.profiles.same_product(binding, retained)
        and r.profiles.kind(retained) == "api"
        and retained.get("target_environment") == "production"
        and retained.get("artifact_digest") == old["image"]
        and re.fullmatch(r"sha256:[a-f0-9]{64}", old["image"])
        and re.fullmatch(r"sha256:[a-f0-9]{64}", binding["artifact_digest"]),
        "EXACT_IDENTITY_ROLLBACK_BINDING_REQUIRED",
    )
    # The old accepted source is authority for this dependency. A new unsigned
    # compatibility report or a matching mutable image tag cannot replace it.
    r.verify_retained_dependency(binding, old, plan)
    environments = {}
    for environment in r.ENV:
        current_path = r.candidate_environment(binding, environment)
        prior_path = r.candidate_environment(retained, environment)
        r.require(
            r.sha(r.private(current_path))
            == binding["configuration_sha256"][environment]
            and r.sha(r.private(prior_path))
            == retained["configuration_sha256"][environment],
            "IDENTITY_ROLLBACK_CONFIGURATION_BINDING_CHANGED",
        )
        current, prior = r.runtime_values(current_path), r.runtime_values(prior_path)
        enabled = r.profiles.enabled_features(current, "identity")
        allowed = r.IDENTITY_KEYS | (
            {"ONESA_PUBLIC_ORIGIN"} if environment == "staging" else set()
        )
        r.require(
            current.get("ONESA_IDENTITY_ENABLED") == "true"
            and prior.get("ONESA_IDENTITY_ENABLED", "false") == "false"
            and r.profiles.enabled_features(prior, "identity") == enabled
            and {key: value for key, value in current.items() if key not in allowed}
            == {key: value for key, value in prior.items() if key not in allowed},
            "IDENTITY_ROLLBACK_MUST_PRESERVE_ACCEPTED_NATIVE_FLAGS",
        )
        environments[environment] = {
            "enabled_features": sorted(enabled),
            "identity_enabled": False,
            "retained_configuration_sha256": retained["configuration_sha256"][
                environment
            ],
        }
    return environments


def application(image, socket, database, enabled, *, owned, fixture=None):
    r.require(database in DATABASES, "ISOLATED_IDENTITY_ROLLBACK_DATABASE_ONLY")
    r.require(
        owned.image == image
        and owned.binds == [(str(socket), "/var/run/postgresql", False)],
        "IDENTITY_ROLLBACK_APPLICATION_SCOPE",
    )
    payload = {
        "phase": "seed" if fixture is None else "verify",
        "enabled_features": enabled,
        "fixture": fixture,
    }
    raw = r.canonical(payload)
    r.require(len(raw) <= 65536, "IDENTITY_ROLLBACK_FIXTURE_BOUND")
    response = owned.run(
        "python",
        ["-c", PROGRAM],
        environment=[
            "HOME=/tmp",
            "ONESA_IDENTITY_ENABLED=false",
            "ONESA_DATABASE_URL=postgresql+psycopg://onesa_restore@/"
            + database
            + "?host=/var/run/postgresql",
        ],
        data=raw,
        timeout=120,
    )
    r.require(len(response) <= 65536, "IDENTITY_ROLLBACK_RESULT_BOUND")
    observed = json.loads(response)
    r.require(
        set(observed)
        == {"enabled_features", "identity_enabled", "checks"}
        | ({"fixture"} if fixture is None else set())
        and observed["enabled_features"] == enabled
        and observed["identity_enabled"] is False
        and set(observed["checks"]) == CHECKS
        and all(value == "PASS" for value in observed["checks"].values()),
        "RETAINED_IMAGE_CANNOT_SERVE_IDENTITY_SCHEMA",
    )
    return observed


def check(folder, binding, operation, plan):
    r.require(str(UUID(operation)) == operation, "IDENTITY_ROLLBACK_OPERATION_UUID")
    folder = r.private(folder, directory=True)
    environments = bound_environments(binding, plan)
    r.require(set(environments) == {"staging", "production"}, "ROLLBACK_ENVIRONMENTS")
    old = plan["rollback"]
    for selected in [binding, old["binding"]]:
        rows = json.loads(r.docker("image", "inspect", selected["artifact_digest"]))
        r.require(len(rows) == 1, "EXACT_IDENTITY_ROLLBACK_IMAGE_REQUIRED")
        row = rows[0]
        labels = row["Config"].get("Labels", {})
        r.require(
            row["Id"] == selected["artifact_digest"]
            and row["Architecture"] == "arm64"
            and row["Os"] == "linux"
            and not row["Config"].get("Volumes")
            and (
                labels.get("org.onesa.source-commit")
                or labels.get("org.opencontainers.image.revision")
            )
            == selected["candidate_commit"],
            "EXACT_IDENTITY_ROLLBACK_IMAGE_REQUIRED",
        )
    rows = json.loads(r.docker("image", "inspect", PG))
    r.require(
        isinstance(rows, list)
        and len(rows) == 1
        and re.fullmatch(r"sha256:[a-f0-9]{64}", rows[0]["Id"])
        and rows[0]["Architecture"] == "arm64"
        and rows[0]["Os"] == "linux"
        and set(rows[0]["Config"].get("Volumes") or {}) <= {"/var/lib/postgresql/data"},
        "EXACT_IDENTITY_ROLLBACK_DATABASE_IMAGE_REQUIRED",
    )
    socket = folder / "identity-rollback-socket"
    schema = OwnedContainer(
        folder, operation, "schema", binding["artifact_digest"], pids=64
    )
    database = OwnedContainer(
        folder,
        operation,
        "database",
        rows[0]["Id"],
        binds=[(socket, "/var/run/postgresql", True)],
        tmpfs={
            "/tmp": "rw,mode=1777,size=64m",
            "/var/lib/postgresql/data": "rw,mode=700,uid=999,gid=999,size=512m",
        },
        memory=512,
        pids=64,
    )
    applications = {
        (environment, phase): OwnedContainer(
            folder,
            operation,
            environment + "-" + phase,
            binding["artifact_digest"] if phase == "seed" else old["image"],
            binds=[(socket, "/var/run/postgresql", False)],
        )
        for environment in environments
        for phase in ["seed", "verify"]
    }
    containers = [schema, database, *applications.values()]
    intent = folder / "identity-rollback-intent.json"
    paths = [
        intent,
        socket,
        folder / "identity-rollback-cleanup.json",
        folder / "identity-rollback-receipt.json",
        *(container.cidfile for container in containers),
        *(container.cidfile.with_suffix(".intent.json") for container in containers),
    ]
    r.require(
        all(not path.exists() and not path.is_symlink() for path in paths)
        and not inventory("label=" + LABEL + "=" + operation)
        and all(
            not inventory("name=^/" + container.name + "$") for container in containers
        ),
        "IDENTITY_ROLLBACK_INTENT_OR_NAMESPACE_EXISTS_INSPECT_ONLY",
    )
    # O_EXCL and directory fsync in write() make an interrupted first attempt
    # durable. A second invocation cannot retry any container creation.
    r.write(
        intent,
        {
            "binding": binding,
            "operation_id": operation,
            "containers": [container.descriptor() for container in containers],
            "candidate_image": binding["artifact_digest"],
            "rollback_image": old["image"],
            "retained_source": old["binding"]["candidate_commit"],
            "schema_revision": r.IDENTITY_SCHEMA,
            "network": "none",
            "production_writes": 0,
            "automatic_retry": False,
        },
    )

    def query(selected, statement):
        r.require(selected in DATABASES, "ISOLATED_IDENTITY_ROLLBACK_DATABASE_ONLY")
        r.require(database.cid is not None, "IDENTITY_ROLLBACK_DATABASE_UNCONFIRMED")
        return (
            r.docker(
                "exec",
                "-i",
                database.cid,
                "psql",
                "-XqAt",
                "-U",
                "onesa_restore",
                "-d",
                selected,
                "-v",
                "ON_ERROR_STOP=1",
                data=statement.encode(),
                timeout=60,
            )
            .decode()
            .strip()
        )

    tables = sorted(
        {
            "users",
            "auth_sessions",
            "conversations",
            "messages",
            "shared_identities",
            "identity_sessions",
            "identity_transactions",
            *TABLES,
            *CYBER_TABLES,
        }
    )

    def manifest(database):
        return {
            table: query(
                database,
                "SELECT encode(sha256(convert_to(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),''),'UTF8')),'hex') FROM public."
                + table
                + " t;",
            )
            for table in tables
        }

    result = None
    socket_identity = None
    try:
        socket.mkdir(mode=0o700)
        socket_stat = socket.stat()
        socket_identity = (
            socket_stat.st_dev,
            socket_stat.st_ino,
            socket_stat.st_uid,
            socket_stat.st_gid,
        )
        os.chown(socket, 999, 999)
        socket_stat = socket.stat()
        socket_identity = (
            socket_stat.st_dev,
            socket_stat.st_ino,
            socket_stat.st_uid,
            socket_stat.st_gid,
        )
        r.sync_directory(folder)
        sql = schema.run(
            "alembic",
            ["upgrade", r.IDENTITY_SCHEMA, "--sql"],
            environment=[
                "HOME=/tmp",
                "ONESA_DATABASE_URL=postgresql+psycopg://onesa_restore:synthetic@localhost/onesa_identity_rollback_test",
            ],
            timeout=60,
        )
        r.require(
            sql.startswith(b"BEGIN;") and len(sql) <= 2 * 1024 * 1024,
            "IDENTITY_ROLLBACK_SCHEMA_BOUND",
        )
        database.run(
            "docker-entrypoint.sh",
            ["postgres"],
            environment=[
                "POSTGRES_USER=onesa_restore",
                "POSTGRES_DB=onesa_identity_rollback_test",
                "POSTGRES_PASSWORD=" + secrets.token_urlsafe(32),
                "PGDATA=/var/lib/postgresql/data",
            ],
            detached=True,
            timeout=30,
        )
        deadline = time.monotonic() + 60
        while True:
            try:
                query("onesa_identity_rollback_test", "SELECT 1;")
                break
            except r.Refused:
                r.require(
                    time.monotonic() < deadline, "IDENTITY_ROLLBACK_DATABASE_STARTUP"
                )
                time.sleep(0.25)
        query("onesa_identity_rollback_test", sql.decode())
        for environment, expected in environments.items():
            seeded = application(
                binding["artifact_digest"],
                socket,
                "onesa_identity_rollback_test",
                expected["enabled_features"],
                owned=applications[(environment, "seed")],
            )
            before = manifest("onesa_identity_rollback_test")
            dump = r.docker(
                "exec",
                database.cid,
                "pg_dump",
                "-U",
                "onesa_restore",
                "-d",
                "onesa_identity_rollback_test",
                "-Fc",
                "--no-owner",
                "--no-acl",
                timeout=60,
            )
            r.require(
                dump.startswith(b"PGDMP") and len(dump) <= 16 * 1024 * 1024,
                "IDENTITY_ROLLBACK_DUMP_BOUND",
            )
            r.docker(
                "exec",
                database.cid,
                "createdb",
                "-U",
                "onesa_restore",
                "onesa_identity_restored_test",
                timeout=20,
            )
            r.docker(
                "exec",
                "-i",
                database.cid,
                "pg_restore",
                "-U",
                "onesa_restore",
                "-d",
                "onesa_identity_restored_test",
                "--no-owner",
                "--no-acl",
                "--exit-on-error",
                data=dump,
                timeout=60,
            )
            r.require(
                manifest("onesa_identity_restored_test") == before,
                "IDENTITY_ROLLBACK_RESTORE_MANIFEST_DIFFERS",
            )
            # The exact retained image must authenticate the same synthetic local
            # owners and read the candidate's persisted records on the new schema.
            observed = application(
                old["image"],
                socket,
                "onesa_identity_restored_test",
                expected["enabled_features"],
                fixture=seeded["fixture"],
                owned=applications[(environment, "verify")],
            )
            environments[environment] = {
                **expected,
                "checks": observed["checks"],
                "restored_manifest_sha256": hashlib.sha256(
                    r.canonical(before)
                ).hexdigest(),
            }
            r.docker(
                "exec",
                database.cid,
                "dropdb",
                "-U",
                "onesa_restore",
                "onesa_identity_restored_test",
                timeout=20,
            )
        result = {
            "status": "PASS",
            "binding": binding,
            "operation_id": operation,
            "candidate_image": binding["artifact_digest"],
            "rollback_image": old["image"],
            "retained_source": old["binding"]["candidate_commit"],
            "schema_revision": r.IDENTITY_SCHEMA,
            "synthetic_database_restore": "PASS",
            "environments": environments,
            "production_writes": 0,
            "network": "none",
            "scope": "isolated synthetic retained-image compatibility; no hosted identity or production restore claim",
        }
    finally:
        cleaned = False
        try:
            cleanup_owned(containers, operation)
            if socket_identity is not None:
                r.private(folder, directory=True)
                observed = socket.lstat()
                r.require(
                    (observed.st_dev, observed.st_ino, observed.st_uid, observed.st_gid)
                    == socket_identity
                    and stat.S_ISDIR(observed.st_mode)
                    # PostgreSQL's entrypoint sets its socket directory to 03775.
                    # Its root-private parent is never mounted into any container.
                    and stat.S_IMODE(observed.st_mode) in {0o700, 0o3775},
                    "IDENTITY_ROLLBACK_SOCKET_CHANGED",
                )
                shutil.rmtree(socket)
                r.sync_directory(folder)
            r.require(
                not socket.exists() and not socket.is_symlink(),
                "IDENTITY_ROLLBACK_SOCKET_REMOVAL_UNCONFIRMED",
            )
            cleaned = True
        finally:
            r.write(
                folder / "identity-rollback-cleanup.json",
                {
                    "operation_id": operation,
                    "isolated_containers_removed": cleaned,
                    "private_inputs_retained": not cleaned,
                    "containers": {
                        container.name: container.cid
                        for container in containers
                        if container.attempted
                    },
                    "release_authority": False,
                },
            )
    # Failed or uncertain runtime checks/cleanup cannot leave a successful receipt.
    r.require(result is not None, "IDENTITY_ROLLBACK_NOT_OBSERVED")
    result.update(
        isolated_containers_removed=True,
        cleanup_receipt_sha256=r.sha(folder / "identity-rollback-cleanup.json"),
    )
    r.write(folder / "identity-rollback-receipt.json", result)
    return result
