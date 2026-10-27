"""Pinned Vercel prebuilt operations for the same app's owner-run release bridge.

Preview and production are separate artifacts/configurations. API dependencies
are inspected as technical prerequisites, never relabelled as frontend approval.
One durable operation precedes each create; inspection never resubmits it.
"""

import json
import os
import posixpath
import re
import sqlite3
import subprocess
import sys
import tarfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oracle_ai_runner as r

PLAN = Path("/etc/onesa/oracle-ai-frontend-release.json")
ROOT = Path("/var/lib/onesa/release-verification/ai-frontend")
PROVIDER = Path("/etc/onesa/oracle-ai-vercel-observer.json")
CLI_AUTH = Path("/etc/onesa/oracle-vercel-cli")
APP_ROOT = "onesa-ai-platform-frontend/apps/chat"
API_ORIGINS = {
    "staging": "https://platform-api-staging.onesa.eu",
    "production": "https://platform-api.onesa.eu",
}

# The pinned CLI atomically updates preferences and its cache during startup.
# Keep owner custody read-only; all CLI writes belong to this container's tmpfs.
CLI_BOOTSTRAP = r"""
const fs=require('node:fs'),{spawn}=require('node:child_process');
const target='/tmp/onesa-vercel-cli';
try {
 fs.mkdirSync(target,{mode:0o700});
 for(const name of ['auth.json','config.json']) {
  const source='/private/creds/'+name,stat=fs.lstatSync(source);
  if(!stat.isFile()||stat.isSymbolicLink()||(stat.mode&0o077)||stat.size>131072)throw Error();
  JSON.parse(fs.readFileSync(source,'utf8'));
  fs.copyFileSync(source,target+'/'+name,fs.constants.COPYFILE_EXCL);
  fs.chmodSync(target+'/'+name,0o600);
 }
 const child=spawn(process.execPath,process.argv.slice(1),{
  stdio:'inherit',env:{...process.env,HOME:'/tmp',VERCEL_TELEMETRY_DISABLED:'1'}
 });
 child.once('error',()=>process.exit(71));
 child.once('exit',code=>process.exit(code??1));
} catch {
 process.stderr.write('Oracle CLI private runtime configuration unavailable; no deployment allowed.\n');
 process.exit(71);
}
"""


def provider(path, *, data=None):
    cfg = r.read(PROVIDER)
    r.require(path.startswith("/") and "://" not in path, "PROVIDER_METADATA_PATH")
    url = (
        "https://api.vercel.com"
        + path
        + ("&" if "?" in path else "?")
        + urllib.parse.urlencode({"teamId": cfg["team_id"]})
    )
    request = urllib.request.Request(
        url,
        data=None if data is None else r.canonical(data),
        headers={
            "Authorization": "Bearer " + cfg["token"],
            "Content-Type": "application/json",
            "User-Agent": "OnesaOwnerOracleRelease/1.0",
        },
    )

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_args, **_kwargs):
            return None

    with urllib.request.build_opener(NoRedirect()).open(
        request, timeout=30
    ) as response:
        raw = response.read(4 * 1024 * 1024 + 1)
        r.require(len(raw) <= 4 * 1024 * 1024, "PROVIDER_RESPONSE_BOUND")
        return json.loads(raw)


def protection(plan):
    cfg = r.read(PROVIDER)
    project = provider("/v9/projects/" + cfg["project_id"])
    fields = {
        k: project.get(k)
        for k in [
            "ssoProtection",
            "protectionBypass",
            "passwordProtection",
            "trustedIps",
        ]
    }
    import hashlib

    r.require(
        project["id"] == plan["project_id"]
        and hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()
        == plan["vercel_protection_sha256"],
        "EXISTING_PROVIDER_PROTECTION_CHANGED",
    )
    # Manual prebuilt deployments have no Git source. Commit metadata does not
    # select branch-scoped variables, so verify the intended existing values and
    # pass the single nonsecret route explicitly for this deployment.
    for env, target in [("staging", "preview"), ("production", "production")]:
        identifier = plan["vercel_api_url_variable_ids"][env]
        r.require(
            re.fullmatch("[A-Za-z0-9_-]{8,128}", identifier),
            "NAMED_ROUTING_VARIABLE_ID",
        )
        variable = provider("/v1/projects/" + cfg["project_id"] + "/env/" + identifier)
        r.require(
            variable.get("id") == identifier
            and variable.get("key") == "ONESA_API_URL"
            and target in variable.get("target", [])
            and variable.get("value") == API_ORIGINS[env]
            and variable.get("gitBranch")
            in ([None, "staging"] if env == "staging" else [None]),
            "ACTUAL_FRONTEND_API_ROUTING_CHANGED",
        )
    return project


def validate(binding):
    r.require(
        binding.get("repository") == "DruHustle/onesa-ai-platform"
        and binding.get("component") == "frontend"
        and binding.get("target_environment") == "production",
        "FRONTEND_COMPONENT_SCOPE",
    )
    plan = r.read(PLAN)
    r.require(
        plan["binding"] == binding and plan["schema_version"] == 1,
        "OWNER_FRONTEND_PLAN_BINDING",
    )
    folder = r.private(ROOT / "artifacts" / binding["candidate_commit"], directory=True)
    r.require(
        r.sha(r.private(folder / "source.tar")) == binding["source_sha256"],
        "FRONTEND_SOURCE_ARCHIVE",
    )
    r.source_inventory(folder / "source.tar", binding)
    for env in ["staging", "production"]:
        config = Path(plan["configuration_paths"][env])
        r.require(
            r.sha(r.private(config)) == binding["configuration_sha256"][env],
            "FRONTEND_CONFIGURATION_CHANGED",
        )
        value = r.read(config)
        r.require(
            value.get("candidate_commit") == binding["candidate_commit"]
            and value.get("project_id") == plan["project_id"]
            and value.get("target_environment") == env
            and value.get("api_origin") == API_ORIGINS[env]
            and value.get("api_routing_variable_id")
            == plan["vercel_api_url_variable_ids"][env],
            "SOURCE_BOUND_FRONTEND_ROUTING_CONFIGURATION_REQUIRED",
        )
        build = plan["builds"][env]
        receipt = r.read(folder / build["receipt"])
        r.require(
            r.sha(folder / build["receipt"]) == build["receipt_sha256"]
            and receipt["binding"]["candidate_commit"] == binding["candidate_commit"]
            and receipt["binding"]["source_tree"] == binding["source_tree"]
            and receipt["binding"]["source_sha256"] == binding["source_sha256"]
            and receipt["environment"] == env
            and receipt["source_tree_verified"] is True
            and receipt["provider_credentials_mounted"] is False
            and receipt["builder_sha256"] == plan["builder_sha256"]
            and receipt["tool_image"] == r.trusted_toolchain(plan)["builder_image"],
            "OBSERVED_CREDENTIAL_FREE_BUILD_REQUIRED",
        )
        r.require(
            r.sha(r.private(folder / build["archive"]))
            == receipt["artifact_sha256"]
            == build["archive_sha256"],
            "IMMUTABLE_PREBUILT_ARCHIVE_CHANGED",
        )
    r.require(
        binding["build_sha256"]
        == r.sha(folder / plan["builds"]["production"]["receipt"])
        and binding["artifact_digest"]
        == "sha256:" + plan["builds"]["production"]["archive_sha256"],
        "AUTHORIZED_FRONTEND_ARTIFACT_BINDING",
    )
    commissioned = r.trusted_toolchain(plan)
    r.require(
        plan["cli_image"] == commissioned["cli_image"]
        and plan["builder_sha256"] == commissioned["builder_sha256"],
        "CANDIDATE_CANNOT_SELECT_RELEASE_TOOL",
    )
    tool = json.loads(r.docker("image", "inspect", plan["cli_image"]))[0]
    r.require(
        tool["Id"] == plan["cli_image"]
        and tool["Architecture"] == "arm64"
        and tool["Config"]["Labels"].get("org.onesa.vercel-cli") == "65.2.0",
        "PINNED_CLI_TOOL_REQUIRED",
    )
    scan = r.read(folder / "cli-scan.json")
    r.image_security(scan, tool["Id"])
    r.require(
        plan["physical_hardware_authorized"] is False
        and plan["processing_scope"] == "owned-synthetic-release-verification",
        "FRONTEND_PROCESSING_SCOPE",
    )
    r.verify_probe_bytes(folder, binding, plan)
    protection(plan)
    return folder, plan


def unpack(folder, build, destination):
    receipt = r.read(folder / build["receipt"])
    expected = receipt["files"]
    seen = {}
    links = {}
    total = 0
    metadata_files = {}
    entries = set()
    with tarfile.open(r.private(folder / build["archive"])) as archive:
        members = archive.getmembers()
        r.require(len(members) <= 25000, "PREBUILT_ENTRY_BOUND")
        for member in members:
            path = Path(member.name)
            r.require(member.name not in entries, "DUPLICATE_PREBUILT_PATH")
            entries.add(member.name)
            r.require(
                not path.is_absolute()
                and ".." not in path.parts
                and (member.isfile() or member.isdir() or member.issym())
                and (str(path).startswith(".vercel/") or str(path) == "vercel.json"),
                "PREBUILT_PATH_OR_TYPE",
            )
            if member.issym():
                target = posixpath.normpath(str(path.parent / member.linkname))
                r.require(
                    str(path).startswith(".vercel/output/functions/")
                    and str(path).endswith(".func")
                    and not Path(member.linkname).is_absolute()
                    and target.startswith(".vercel/output/functions/")
                    and target.endswith(".func"),
                    "PREBUILT_ALIAS_ESCAPE",
                )
                name = member.name[len(".vercel/output/") :]
                r.require(name not in links, "DUPLICATE_PREBUILT_ALIAS")
                links[name] = member.linkname
            if member.isfile():
                total += member.size
                r.require(
                    total <= 256 * 1024 * 1024 and member.size <= 32 * 1024 * 1024,
                    "PREBUILT_BYTE_BOUND",
                )
                if member.name in [".vercel/project.json", "vercel.json"]:
                    import hashlib

                    metadata_files[member.name] = hashlib.sha256(
                        archive.extractfile(member).read()
                    ).hexdigest()
                if member.name.startswith(".vercel/output/"):
                    name = member.name[len(".vercel/output/") :]
                    import hashlib

                    r.require(name not in seen, "PREBUILT_DUPLICATE_ENTRY")
                    seen[name] = hashlib.sha256(
                        archive.extractfile(member).read()
                    ).hexdigest()
        r.require(
            metadata_files == receipt["deployment_metadata_files"],
            "PREBUILT_DEPLOYMENT_METADATA_CHANGED",
        )
        r.require(
            not any(
                any(
                    entry.startswith(".vercel/output/" + link + "/")
                    for entry in entries
                )
                for link in links
            ),
            "PREBUILT_ALIAS_HAS_CHILDREN",
        )
        r.require(seen == expected, "PREBUILT_CONTENT_DIFFERS_FROM_OBSERVED_BUILD")
        r.require(
            links == receipt.get("links", {}),
            "PREBUILT_ALIASES_DIFFER_FROM_OBSERVED_BUILD",
        )
        for name, target in links.items():
            visited = {name}
            current = posixpath.normpath(
                posixpath.join(posixpath.dirname(name), target)
            )
            while current in links:
                r.require(
                    current not in visited and len(visited) < 32, "PREBUILT_ALIAS_CYCLE"
                )
                visited.add(current)
                current = posixpath.normpath(
                    posixpath.join(posixpath.dirname(current), links[current])
                )
            r.require(
                any(key.startswith(current + "/") for key in seen),
                "PREBUILT_ALIAS_TARGET_MISSING",
            )
        archive.extractall(destination, filter="data")
    project = json.loads((destination / ".vercel/project.json").read_bytes())
    cfg = r.read(PROVIDER)
    r.require(
        project["projectId"] == cfg["project_id"]
        and project["orgId"] == cfg["team_id"],
        "PREBUILT_PROJECT_SCOPE",
    )
    r.require(
        project.get("settings", {}).get("rootDirectory") == APP_ROOT,
        "PREBUILT_APPLICATION_ROOT_SCOPE",
    )
    # The CLI resolves the provider's monorepo root even for --prebuilt.
    # Only its empty directory is needed; candidate source is never executed.
    (destination / APP_ROOT).mkdir(mode=0o700, parents=True, exist_ok=False)


def deployments_for(operation, plan):
    response = provider(
        "/v6/deployments?"
        + urllib.parse.urlencode({"projectId": plan["project_id"], "limit": 100})
    )
    matches = [
        d
        for d in response["deployments"]
        if d.get("meta", {}).get("onesaOracleOperation") == operation
    ]
    r.require(len(matches) <= 1, "DUPLICATE_PROVIDER_OPERATIONS_INSPECT_ONLY")
    return matches


def check_deployment(identifier, binding, env, plan):
    row = provider("/v13/deployments/" + identifier)
    source = row.get("meta", {}).get("githubCommitSha") or row.get("gitSource", {}).get(
        "sha"
    )
    r.require(
        row["id"] == identifier
        and row["projectId"] == plan["project_id"]
        and source == binding["candidate_commit"]
        and row.get("target") == ("production" if env == "production" else None),
        "ACTUAL_FRONTEND_DEPLOYMENT_BINDING",
    )
    return row


def observe_provider(binding, env, plan, operation):
    # Provider custody remains in the pinned host process. The browser tool gets
    # only bounded metadata plus the existing Preview protection bypass, never
    # a provider API token or deployment credential.
    cfg = r.read(PROVIDER)
    project = protection(plan)
    if env == "staging":
        preview = r.read(Path(plan["preview_receipt_path"]))
        r.require(
            preview["environment"] == "staging"
            and all(
                preview["binding"][k] == binding[k]
                for k in [
                    "repository",
                    "candidate_commit",
                    "source_tree",
                    "source_sha256",
                ]
            ),
            "CURRENT_SOURCE_PREVIEW_REQUIRED",
        )
        identifier = preview["deployment_id"]
        source = binding["candidate_commit"]
        origin = cfg["staging_origin"]
    else:
        identifier = (
            plan.get("current_frontend_deployment_id")
            if binding["component"] == "frontend"
            else cfg["production_deployment_id"]
        )
        source = (
            binding["candidate_commit"]
            if binding["component"] == "frontend"
            else plan["retained_frontend"]["source"]
        )
        origin = "https://platform.onesa.eu"
    dep = provider("/v13/deployments/" + identifier)
    actual = dep.get("meta", {}).get("githubCommitSha") or dep.get("gitSource", {}).get(
        "sha"
    )
    r.require(
        dep["id"] == identifier
        and dep["projectId"] == cfg["project_id"]
        and actual == source
        and dep["readyState"] == "READY"
        and dep.get("target") == ("production" if env == "production" else None),
        "ACTUAL_PROVIDER_READBACK_MISMATCH",
    )
    alias = provider("/v4/aliases/" + origin.removeprefix("https://"))
    r.require(
        alias["deployment"]["id"] == identifier
        and alias["projectId"] == cfg["project_id"],
        "ACTUAL_ALIAS_READBACK_MISMATCH",
    )
    bypass = None
    if env == "staging":
        keys = [
            k
            for k, v in project.get("protectionBypass", {}).items()
            if v.get("scope") == "automation-bypass"
        ]
        r.require(len(keys) == 1, "EXISTING_PREVIEW_PROTECTION_CUSTODY")
        bypass = keys[0]
    return {
        "schema_version": 1,
        "binding": binding,
        "operation_id": operation,
        "environment": env,
        "observed_at": r.now().isoformat(),
        "origin": origin,
        "bypass": bypass,
        "project_id": cfg["project_id"],
        "provider": {
            "deployment_id": identifier,
            "project_id": cfg["project_id"],
            "source": source,
            "target": dep.get("target"),
        },
        "provider_token_included": False,
    }


def create(binding, env, operation, folder, plan):
    r.require(str(UUID(operation)) == operation, "CANONICAL_PROVIDER_OPERATION")
    op = folder / "operations" / operation
    op.mkdir(mode=0o700, exist_ok=False)
    r.require(
        not deployments_for(operation, plan), "EXISTING_PROVIDER_OPERATION_INSPECT_ONLY"
    )
    workspace = op / "prebuilt"
    workspace.mkdir(mode=0o700)
    unpack(folder, plan["builds"][env], workspace)
    before = protection(plan)
    r.private(CLI_AUTH, directory=True)
    r.private(CLI_AUTH / "auth.json")
    r.private(CLI_AUTH / "config.json")
    r.write(
        op / "intent.json",
        {
            "binding": binding,
            "operation_id": operation,
            "environment": env,
            "artifact_sha256": plan["builds"][env]["archive_sha256"],
            "provider_create_budget": 1,
            "automatic_retry": False,
        },
    )
    guard = r.private(Path(__file__).with_name("oracle_vercel_transport_guard.cjs"))
    r.require(
        r.sha(guard) == r.trusted_toolchain(plan)["transport_guard_sha256"],
        "PINNED_DEPLOYMENT_TRANSPORT_REQUIRED",
    )
    transport = op / "transport"
    transport.mkdir(mode=0o700)
    r.write(
        transport / "scope.json",
        {
            "repository": binding["repository"],
            "component": "frontend",
            "candidate_commit": binding["candidate_commit"],
            "environment": env,
            "operation_id": operation,
            "request_budget": 1,
        },
    )
    command = [
        "/usr/bin/docker",
        "run",
        "--rm",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,mode=700,size=256m",
        "--memory",
        "512m",
        "--cpus",
        "1",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "-v",
        str(workspace) + ":/workspace:ro",
        "-v",
        str(CLI_AUTH) + ":/private/creds:ro",
        "-v",
        str(guard) + ":/private/guard.cjs:ro",
        "-v",
        str(transport) + ":/private/transport:rw",
        "-e",
        "ONESA_ORACLE_VERIFIER_PRELOAD=1",
        "--entrypoint",
        "node",
        "-w",
        "/workspace",
        plan["cli_image"],
        "-e",
        CLI_BOOTSTRAP,
        "--",
        "--require",
        "/private/guard.cjs",
        "/opt/onesa-vercel-tool/node_modules/vercel/dist/index.js",
        "deploy",
        "--prebuilt",
        "--yes",
        "--no-wait",
        "--json",
        "--global-config",
        "/tmp/onesa-vercel-cli",
        "--project",
        plan["project_id"],
        "--env",
        "ONESA_API_URL=" + API_ORIGINS[env],
        "--meta",
        "githubCommitRef=" + ("main" if env == "production" else "staging"),
        "--meta",
        "githubCommitSha=" + binding["candidate_commit"],
        "--meta",
        "onesaOracleOperation=" + operation,
        *(["--prod"] if env == "production" else []),
    ]
    with (op / "cli.stdout").open("xb") as out, (op / "cli.stderr").open("xb") as err:
        os.chmod(out.name, 0o600)
        os.chmod(err.name, 0o600)
        try:
            result = subprocess.run(
                command,
                stdout=out,
                stderr=err,
                timeout=600,
                check=False,
                env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
            )
            exit_code = result.returncode
        except subprocess.TimeoutExpired:
            exit_code = None
    # Never repeat create after an ambiguous response. Reconcile by operation UUID.
    deadline = time.monotonic() + 120
    matches = []
    while not matches:
        matches = deployments_for(operation, plan)
        if matches:
            break
        r.require(
            time.monotonic() < deadline,
            "PROVIDER_REQUEST_UNCERTAIN_INSPECT_WITHOUT_CREATE",
        )
        time.sleep(2)
    r.require(
        (transport / "create-request.json").is_file(),
        "SDK_TRANSPORT_NOT_OBSERVED_INSPECT_ONLY",
    )
    identifier = matches[0]["uid"]
    dep = check_deployment(identifier, binding, env, plan)
    receipt = {
        "binding": binding,
        "operation_id": operation,
        "environment": env,
        "deployment_id": identifier,
        "cli_exit": exit_code,
        "provider_state": dep["readyState"],
        "artifact_sha256": plan["builds"][env]["archive_sha256"],
        "transport_receipts": {
            name: r.sha(r.private(transport / name))
            for name in [
                "create-request.json",
                "missing-files-response.json",
                "create-continuation-request.json",
            ]
            if (transport / name).exists()
        },
        "observed_at": r.now().isoformat(),
    }
    r.write(op / "provider-receipt.json", receipt)
    protection(plan)
    r.require(before["id"] == plan["project_id"], "PROJECT_PRESERVATION")
    deadline = time.monotonic() + 600
    while dep["readyState"] not in ["READY", "ERROR", "CANCELED"]:
        r.require(time.monotonic() < deadline, "DEPLOYMENT_NOT_READY_INSPECT_ONLY")
        time.sleep(2)
        dep = check_deployment(identifier, binding, env, plan)
    r.require(dep["readyState"] == "READY", "PROVIDER_DEPLOYMENT_FAILED_RETAIN_RECEIPT")
    if env == "staging":
        alias = r.read(PROVIDER)["staging_origin"].removeprefix("https://")
        r.require(
            re.fullmatch("onesa-ai-platform-git-staging-[a-z0-9-]+.vercel.app", alias),
            "EXISTING_STAGE_ALIAS_ONLY",
        )
        r.write(
            op / "alias-intent.json",
            {
                "deployment_id": identifier,
                "alias": alias,
                "operation_id": operation,
                "request_budget": 1,
            },
        )
        provider("/v2/deployments/" + identifier + "/aliases", data={"alias": alias})
        observed = provider("/v4/aliases/" + alias)
        r.require(
            observed["deployment"]["id"] == identifier
            and observed["projectId"] == plan["project_id"],
            "STAGE_ALIAS_READBACK_FAILED",
        )
    return receipt, op / "provider-receipt.json"


def prepare_preview(api_binding, context):
    plan = r.read(PLAN)
    binding = plan["binding"]
    folder, plan = validate(binding)
    r.require(
        all(
            binding[k] == api_binding[k]
            for k in ["repository", "candidate_commit", "source_tree", "source_sha256"]
        ),
        "PREVIEW_DEPENDENCY_CHANGED_SOURCE",
    )
    # Called only by the pinned API staging runner after its context reservation.
    operation = context["context_id"]
    create(binding, "staging", operation, folder, plan)
    return folder / "operations" / operation / "provider-receipt.json"


def select_preview(binding, api_binding, chain, phase, folder, plan):
    if any(
        binding[key] != api_binding[key]
        for key in ["candidate_commit", "source_tree", "source_sha256"]
    ):
        qualification_context = next(
            row["id"] for row in chain if row["kind"] == "context"
        )
        plan["preview_receipt_path"] = str(
            folder / "operations" / qualification_context / "provider-receipt.json"
        )
        if phase == "staging":
            create(binding, "staging", qualification_context, folder, plan)
    return plan["preview_receipt_path"]


def main():
    r.require(
        os.geteuid() == 0 and not os.getenv("GITHUB_ACTIONS"),
        "OWNER_FRONTEND_RUNNER_ONLY",
    )
    phase = sys.argv[1]
    raw = sys.stdin.buffer.read(131073)
    r.require(len(raw) <= 131072, "FRONTEND_REQUEST_BOUND")
    request = json.loads(raw)
    binding = request["binding"]
    context = request["context"]
    folder, plan = validate(binding)
    api_plan = r.read(r.PLAN)
    api_binding = api_plan["binding"]
    r.require(
        api_plan["mode"] in ["twins", "cybersecurity"],
        "API_DEPENDENCY_FEATURE_NOT_QUALIFIED",
    )
    store = r.private(Path(api_plan["verifier_store"]), directory=True)
    db = sqlite3.connect("file:" + str(store / "records.sqlite") + "?mode=ro", uri=True)
    try:
        latest = db.execute(
            "SELECT d.id FROM deployments d JOIN records r ON r.id=d.id WHERE d.state='accepted' AND r.scope=? ORDER BY r.sequence DESC LIMIT 1",
            (api_binding["repository"] + ":api",),
        ).fetchone()
    finally:
        db.close()
    r.require(latest, "API_DEPENDENCY_PRODUCTION_NOT_ACCEPTED")
    api_operation = latest[0]
    api_chain = r.verify_invocation(
        api_binding,
        {"operation_id": api_operation, "read_only": True},
        "production",
        api_plan,
        dependency=True,
    )
    api_context = next(row["id"] for row in api_chain if row["kind"] == "context")
    api_plan["artifact_folder"] = str(
        r.ROOT / "artifacts" / api_binding["candidate_commit"]
    )
    api_plan["qualification_context_id"] = api_context
    actual = r.observe_production(
        api_binding, api_operation, Path(api_plan["artifact_folder"]), api_plan
    )
    plan["api_binding"] = api_binding
    if api_plan["mode"] == "twins":
        plan["storage"] = api_plan["storage"]
    plan["mode"] = api_plan["mode"]
    plan["expected_schema_revision"] = api_plan["expected_schema_revision"]
    plan["preview_receipt_path"] = str(
        ROOT
        / "artifacts"
        / binding["candidate_commit"]
        / "operations"
        / api_context
        / "provider-receipt.json"
    )
    if phase == "preflight":
        print(
            json.dumps(
                {
                    "state": "PREREQUISITES_READY_NOT_QUALIFIED",
                    "provider_requests": 0,
                    "records_issued": 0,
                    "api_dependency": actual,
                }
            )
        )
        return
    chain = r.verify_invocation(binding, context, phase, plan)
    ci = next(row["details"]["ci"] for row in chain if row["kind"] == "context")
    plan["observed_ci_run_id"] = next(
        row["run_id"] for row in ci if row["workflow"] == "ci.yml"
    )
    select_preview(binding, api_binding, chain, phase, folder, plan)
    if phase == "staging":
        with _probe_plan(plan):
            details = r.probe(binding, "staging", context["context_id"], folder, plan)
    elif phase == "operations":
        details = {
            "api_dependency": actual,
            "protection_preserved": True,
            "current_backup": r.operational_observations(api_binding, api_plan),
        }
    elif phase == "deploy":
        receipt, _path = create(
            binding, "production", context["operation_id"], folder, plan
        )
        details = receipt
        plan["current_frontend_deployment_id"] = receipt["deployment_id"]
        try:
            with _probe_plan(plan):
                details["hosted_verification"] = r.probe(
                    binding, "production", context["operation_id"], folder, plan
                )
        except Exception as error:  # noqa: BLE001 -- Preserve actual provider receipt on failed verification.
            details["verification_state"] = "FAILED_OR_INTERRUPTED"
            details["failure_category"] = type(error).__name__
    else:
        receipt = r.read(
            folder / "operations" / context["operation_id"] / "provider-receipt.json"
        )
        dep = check_deployment(receipt["deployment_id"], binding, "production", plan)
        r.require(
            dep["readyState"] == "READY"
            and "platform.onesa.eu" in dep.get("alias", []),
            "ACTUAL_PRODUCTION_ALIAS_OR_STATE",
        )
        output = folder / "observations" / context["operation_id"]
        hosted = r.read(output / "receipt.json")
        r.require(
            hosted == r.read(output / "producer.stdout")
            and hosted["binding"] == binding
            and hosted["operation_id"] == context["operation_id"]
            and hosted["status"] == "PASS"
            and hosted["fixture_identities_disabled"] is True
            and hosted["existing_records_preserved"] is True
            and all(
                hosted["checks"].get(k) == "PASS"
                for k in plan["mandatory_probe_checks"]["production"]
            ),
            "FRONTEND_PRODUCTION_WORKFLOWS_UNVERIFIED",
        )
        plan["current_frontend_deployment_id"] = receipt["deployment_id"]
        observe_provider(binding, "production", plan, context["operation_id"])
        verify_static(folder, plan, dep)
        details = {
            "deployment_id": dep["id"],
            "runtime_source": binding["candidate_commit"],
            "artifact_sha256": receipt["artifact_sha256"],
            "hosted_receipt_sha256": r.sha(output / "receipt.json"),
            "read_only_observer": True,
        }
    print(
        json.dumps(
            {
                "binding": binding,
                "workflow_run_id": 0,
                "environment": "staging" if phase == "staging" else "production",
                "observed_at": r.now().isoformat(),
                "checks": {key: "PASS" for key in r.CHECKS[phase]},
                "observations": details,
                "operation_id": context.get("operation_id"),
                "deployment_id": details.get("deployment_id"),
            }
        )
    )


from contextlib import contextmanager


@contextmanager
def _probe_plan(plan):
    # Pinned shared observer, same application only; this selects a fixed
    # owner-installed plan rather than accepting a caller path.
    old = r.PLAN
    r.PLAN = PLAN
    try:
        yield
    finally:
        r.PLAN = old


def verify_static(folder, plan, dep):
    receipt = r.read(folder / plan["builds"]["production"]["receipt"])
    expected = receipt["served_static_files"]
    r.require(expected, "ACTUAL_SERVED_STATIC_ARTIFACT_REQUIRED")
    import hashlib

    for path, digest in expected.items():
        r.require(
            path.startswith("/_next/static/") and ".." not in path,
            "BOUNDED_SERVED_ASSET_PATH",
        )
        with urllib.request.urlopen(
            "https://platform.onesa.eu" + path, timeout=30
        ) as response:
            raw = response.read(8 * 1024 * 1024 + 1)
            r.require(
                len(raw) <= 8 * 1024 * 1024
                and hashlib.sha256(raw).hexdigest() == digest,
                "SERVED_STATIC_ARTIFACT_DIFFERS",
            )


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 -- Provider credentials and private build logs never reach CLI errors.
        raise SystemExit(
            "Oracle frontend release prerequisite failed; inspect retained private operation; no automatic create retry"
        ) from None
