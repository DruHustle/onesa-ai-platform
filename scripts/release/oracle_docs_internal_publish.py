"""Existing Pages CLI publication behind a durable, one-dispatch owner boundary.

Only reviewed static bytes and the reviewed Access worker reach the existing
project. Provider credentials supply transport, never qualification or authority.
"""

import fcntl
import hashlib
import json
import os
import re
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

import oracle_ai_runner as system
import oracle_docs_internal_provider as provider
import oracle_docs_internal_runner as docs
import oracle_owner as owner

CLI = "/opt/onesa-cloudflare-tool/node_modules/wrangler/wrangler-dist/cli.js"
# The only input is root-owned existing publisher custody. No credential value
# occurs in arguments, host environment, output or durable operation metadata.
BOOTSTRAP = r"""
const fs=require('node:fs');
const p='/private/credentials/publisher.json',s=fs.lstatSync(p);
if(!s.isFile()||s.isSymbolicLink()||(s.mode&0o077)||s.size>32768)throw Error('PRIVATE_EXISTING_PUBLISHER_REQUIRED');
const c=JSON.parse(fs.readFileSync(p,'utf8'));
const cfg=JSON.parse(fs.readFileSync('/private/operation/guard.json','utf8'));
if(c.purpose!=='existing-cloudflare-pages-publisher'||c.account_id!==cfg.account_id||c.release_authority!==false||!Number.isFinite(Date.parse(c.expires_at))||Date.parse(c.expires_at)-Date.now()<300000||!/^[!-~]{20,16384}$/.test(c.token))throw Error('PURPOSE_ACCOUNT_AND_CURRENT_CUSTODY_REQUIRED');
process.env.CLOUDFLARE_API_TOKEN=c.token;
process.env.CLOUDFLARE_ACCOUNT_ID=c.account_id;
process.env.WRANGLER_SEND_METRICS='false';process.env.WRANGLER_WRITE_LOGS='false';
process.env.NO_UPDATE_NOTIFIER='1';process.env.HOME='/tmp';
process.env.GIT_CEILING_DIRECTORIES='/workspace';process.env.GIT_CONFIG_NOSYSTEM='1';process.env.GIT_CONFIG_GLOBAL='/dev/null';
process.env.NODE_PATH='/opt/onesa-cloudflare-tool/node_modules';
process.env.ONESA_CF_GUARD_CONFIG='/private/operation/guard.json';
process.env.ONESA_CF_GUARD_SHA256=require('node:crypto').createHash('sha256').update(fs.readFileSync(process.env.ONESA_CF_GUARD_CONFIG)).digest('hex');
require('/private/guard.cjs');
const args=process.argv.slice(1);if(args[0]!=='/opt/onesa-cloudflare-tool/node_modules/wrangler/wrangler-dist/cli.js')throw Error('PINNED_PRIVATE_PUBLISHER_ENTRYPOINT_REQUIRED');process.argv=[process.execPath,args[0],...args.slice(1)];require('node:module')._load(args[0],null,true);
"""


@contextmanager
def component_lock():
    owner.private(docs.ROOT, directory=True)
    fd = os.open(
        docs.ROOT / "publication.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600
    )
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def durable(path, value):
    docs.common.durable(
        path, value if isinstance(value, bytes) else owner.canonical(value)
    )


def toolchain(store):
    tool = store.policy["toolchain"]
    image = tool["cli_image"]
    owner.require(
        re.fullmatch("sha256:[a-f0-9]{64}", image),
        "LITERAL_PRIVATE_PUBLISHER_IMAGE_REQUIRED",
    )
    actual = json.loads(system.docker("image", "inspect", image))[0]
    owner.require(
        actual["Id"] == image
        and actual["Architecture"] == "arm64"
        and actual["Config"]["Labels"].get("org.onesa.wrangler-cli") == "4.153.0",
        "REVIEWED_PRIVATE_PUBLISHER_IMAGE_REQUIRED",
    )
    system.image_security(
        docs.read(Path(tool["cli_image_security_path"]), store), image
    )
    guard = Path(__file__).with_name("oracle_cloudflare_transport_guard.cjs")
    owner.private(guard)
    owner.require(
        owner.file_digest(guard) == tool["transport_guard_sha256"],
        "REVIEWED_PRIVATE_DISPATCH_GUARD_REQUIRED",
    )
    # Validate the patched distribution actually contained in the pinned image.
    observed = system.command(
        [
            "/usr/bin/docker",
            "run",
            "--rm",
            "--pull=never",
            "--network",
            "none",
            "--read-only",
            "--memory",
            "128m",
            "--cpus",
            "1",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--entrypoint",
            "node",
            image,
            "-e",
            "const fs=require('node:fs'),c=require('node:crypto');process.stdout.write(c.createHash('sha256').update(fs.readFileSync(process.argv[1])).digest('hex'));",
            CLI,
        ],
        timeout=30,
    ).decode()
    owner.require(
        observed == tool["cli_distribution_sha256"],
        "PRIVATE_SINGLE_SUBMIT_CLIENT_BYTES_CHANGED",
    )
    return image, guard


def unpack(store, binding, spec, workspace):
    environment = spec["environment"]
    value = docs.plan(store, binding)
    archive = Path(value["archives"][environment]["path"])
    owner.private(archive)
    raw = archive.read_bytes()
    owner.require(
        hashlib.sha256(raw).hexdigest() == spec["artifact"]["archive_sha256"],
        "PRIVATE_PUBLICATION_ARCHIVE_CHANGED",
    )
    files = docs.builds.archive_files(raw)
    owner.require(
        {name: hashlib.sha256(body).hexdigest() for name, body in files.items()}
        == spec["artifact"]["files"],
        "PRIVATE_PUBLICATION_FILE_BYTES_CHANGED",
    )
    for name, body in files.items():
        target = workspace / name
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        durable(target, body)


def inspect_retained(store):
    observations = []
    journals = sorted((docs.ROOT / "artifacts").glob("*/operations/*/intent.json"))
    owner.require(len(journals) <= 1000, "BOUNDED_PRIVATE_PUBLICATION_JOURNAL_REQUIRED")
    for path in journals:
        value = docs.read(path, store)
        operation_id = path.parent.name
        owner.identifier(operation_id)
        original = Path(value["verifier_store"])
        owner.private(original, directory=True)
        prior = owner.Store(original, store.github)
        try:
            kind = (
                "deployment-intent"
                if value["prepared"]["environment"] == "production"
                else "documentation-preview-intent"
            )
            operation = prior.get(operation_id, kind, historical=True)["record"]
            owner.require(
                operation["binding"] == value["binding"],
                "RETAINED_PRIVATE_OPERATION_SOURCE_CHANGED",
            )
            rows = docs.operation_matches(store, operation_id)
            owner.require(
                len(rows) == 1,
                "RETAINED_PRIVATE_OUTCOME_UNCERTAIN_INSPECT_WITHOUT_CREATE",
            )
            row = rows[0]
            state = row["latest_stage"]["status"]
            owner.require(
                state in {"success", "failure", "canceled"},
                "RETAINED_PRIVATE_PUBLICATION_STILL_ACTIVE",
            )
            if kind == "deployment-intent" and state == "success":
                accepted = prior.db.execute(
                    "SELECT state FROM deployments WHERE id=?", (operation_id,)
                ).fetchone()
                owner.require(
                    accepted and accepted[0] == "accepted",
                    "RETAINED_PRIVATE_PRODUCTION_REQUIRES_OBSERVATION_FIRST",
                )
            observations.append(
                {
                    "operation_id": operation_id,
                    "deployment_id": row["id"],
                    "state": state,
                    "provider_writes": 0,
                }
            )
        finally:
            prior.db.close()
    return observations


def create(store, operation, *, production):
    binding = operation["binding"]
    docs.scoped(store, binding)
    kind = "deployment-intent" if production else "documentation-preview-intent"
    store.get(operation["id"], kind, binding)
    with component_lock():
        inspect_retained(store)
        spec = docs.publication_spec(store, binding, production=production)
        folder = docs.operation_folder(binding, operation["id"])
        owner.require(
            not folder.exists() and not folder.is_symlink(),
            "PRIVATE_PUBLICATION_EXISTS_INSPECT_WITHOUT_CREATE",
        )
        owner.require(
            not docs.operation_matches(store, operation["id"]),
            "PRIVATE_PROVIDER_OPERATION_EXISTS_INSPECT_ONLY",
        )
        image, guard = toolchain(store)
        token = provider.custody(provider.PUBLISHER, spec["account_id"])
        del token
        custody_pin = owner.file_digest(provider.PUBLISHER)
        if production:
            authorization = store.get(operation["parent"], "authorization", binding)[
                "record"
            ]
            store.get(authorization["parent"], "qualification", binding)
            latest = store.db.execute(
                "SELECT id FROM records WHERE scope=? AND kind='authorization-attempt' ORDER BY sequence DESC LIMIT 1",
                (binding["repository"] + ":docs-internal",),
            ).fetchone()
            owner.require(
                latest and latest[0] == authorization["details"]["attempt_id"],
                "PRIVATE_OWNER_AUTHORIZATION_SUPERSEDED",
            )
        folder.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        folder.mkdir(mode=0o700)
        workspace = folder / "static"
        workspace.mkdir(mode=0o700)
        unpack(store, binding, spec, workspace)
        # The vendor bundles workers in a separate ephemeral directory. The
        # reviewed static tree stays read-only and cannot be rewritten by the CLI.
        (workspace / ".wrangler").mkdir(mode=0o700)
        transport = folder / "transport"
        transport.mkdir(mode=0o700)
        configuration = {
            "schema_version": 1,
            "account_id": spec["account_id"],
            "project": "onesa-engineering-docs",
            "operation_id": operation["id"],
            "source_commit": binding["candidate_commit"],
            "artifact_manifest_sha256": spec["artifact"]["file_manifest_sha256"],
            "environment": spec["environment"],
            "create_intent": "/private/operation/create-dispatch.intent.json",
        }
        durable(transport / "guard.json", configuration)
        durable(
            folder / "intent.json",
            {
                "binding": binding,
                "operation_id": operation["id"],
                "verifier_store": str(store.root),
                "prepared": spec,
                "provider_create_budget": 1,
                "automatic_retry": False,
                "recorded_at": owner.timestamp().isoformat(),
            },
        )
        message = (
            "onesa-oracle:"
            + operation["id"]
            + ":"
            + spec["artifact"]["file_manifest_sha256"]
        )
        command = [
            "/usr/bin/docker",
            "run",
            "--rm",
            "--pull=never",
            "--name",
            "onesa-private-docs-" + operation["id"],
            "--read-only",
            "--tmpfs",
            "/tmp:rw,mode=700,size=512m",
            "--tmpfs",
            "/workspace/.wrangler:rw,noexec,mode=700,size=256m",
            "--memory",
            "768m",
            "--cpus",
            "1",
            "--pids-limit",
            "256",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "-v",
            str(workspace) + ":/workspace:ro",
            "-v",
            str(provider.PUBLISHER) + ":/private/credentials/publisher.json:ro",
            "-v",
            str(guard) + ":/private/guard.cjs:ro",
            "-v",
            str(transport) + ":/private/operation:rw",
            "-e",
            "NODE_PATH=/opt/onesa-cloudflare-tool/node_modules",
            "--entrypoint",
            "node",
            "-w",
            "/workspace",
            image,
            "-e",
            BOOTSTRAP,
            "--",
            CLI,
            "pages",
            "deploy",
            "/workspace",
            "--project-name",
            "onesa-engineering-docs",
            "--branch",
            "main"
            if production
            else "onesa-oracle-" + binding["candidate_commit"][:12],
            "--commit-hash",
            binding["candidate_commit"],
            "--commit-message",
            message,
            "--commit-dirty=false",
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
                    env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                    timeout=900,
                    check=False,
                )
                exit_code = result.returncode
            except subprocess.TimeoutExpired:
                exit_code = None
        durable(
            folder / "cli-result.json",
            {
                "exit_code": exit_code,
                "automatic_retry": False,
                "provider_outcome": "READ_ONLY_RECONCILIATION_REQUIRED",
            },
        )
        owner.require(
            owner.file_digest(provider.PUBLISHER) == custody_pin,
            "PRIVATE_PUBLISHER_CUSTODY_CHANGED_DURING_OPERATION",
        )
        deadline = time.monotonic() + 120
        while not docs.operation_matches(store, operation["id"]):
            owner.require(
                time.monotonic() < deadline,
                "PRIVATE_OUTCOME_UNCERTAIN_INSPECT_WITHOUT_CREATE",
            )
            time.sleep(2)
        owner.private(transport / "create-dispatch.intent.json")
        dispatch = docs.read(transport / "create-dispatch.intent.json", store)
        owner.require(
            dispatch["operation_id"] == operation["id"]
            and dispatch["source_commit"] == binding["candidate_commit"]
            and dispatch["artifact_manifest_sha256"]
            == spec["artifact"]["file_manifest_sha256"]
            and dispatch["environment"] == spec["environment"]
            and dispatch["provider_create_budget"] == 1
            and dispatch["automatic_retry"] is False,
            "ACTUAL_PRIVATE_SINGLE_DISPATCH_REQUIRED",
        )
        observed = docs.deployment_for(
            store,
            operation,
            production=production,
            require_ready=False,
            require_canonical=False,
        )
        durable(folder / "provider-receipt-immediate.json", observed)
        deadline = time.monotonic() + 600
        while observed["state"] not in {"success", "failure", "canceled"}:
            owner.require(
                time.monotonic() < deadline,
                "PRIVATE_PROVIDER_NOT_READY_INSPECT_WITHOUT_CREATE",
            )
            time.sleep(2)
            observed = docs.deployment_for(
                store,
                operation,
                production=production,
                require_ready=False,
                require_canonical=False,
            )
        owner.require(
            observed["state"] == "success", "PRIVATE_PROVIDER_FAILED_PRESERVE_RECEIPT"
        )
        observed = docs.deployment_for(store, operation, production=production)
        docs.project(store, docs.plan(store, binding))
        durable(folder / "provider-receipt-ready.json", observed)
        return observed
