"""Read original protected Docs journals without executing a retained issuer.

This reader never opens a signing key, writes a ledger, issues a grant or retries
a provider request. Original installation custody and signed outcomes remain
mandatory even when a newer canonical controller inspects the same project.
"""

import base64
import json
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import oracle_ai_runner as source_parser
import oracle_install as installer
import oracle_owner as owner

# The retained private installations predate later application and canonical
# helpers. Require their closed Docs core, and verify every retained known file;
# never require an old installation to acquire a newer executable.
REQUIRED_HELPERS = frozenset(
    {
        "oracle_owner.py",
        "oracle_install.py",
        "oracle_docs_owner.py",
        "oracle_docs_native.py",
        "oracle_docs_driver.py",
        "oracle_docs_contract.py",
        "runners/oracle_docs_internal_runner.py",
        "runners/oracle_docs_internal_build.py",
        "runners/oracle_docs_internal_checks.py",
        "runners/oracle_docs_internal_access.py",
        "runners/oracle_docs_internal_provider.py",
        "runners/oracle_docs_internal_publish.py",
        "runners/oracle_docs_internal_conditional.py",
        "runners/oracle_cloudflare_transport_guard.cjs",
    }
)


def read(path, *, uid):
    owner.private(path, uid=uid)
    owner.require(
        path.stat().st_size <= 4 * 1024**2, "BOUNDED_PRIVATE_HISTORY_REQUIRED"
    )
    return json.loads(path.read_bytes())


def installation(binding, root, trust, *, uid):
    owner.require(
        owner.is_docs_binding(binding)
        and binding["component"] == "docs-internal"
        and binding.get("target_environment") == "production",
        "HISTORICAL_PROTECTED_DOCS_SCOPE_ONLY",
    )
    policy = read(root / "policy.json", uid=uid)
    owner.binding_valid(binding, policy)
    tool = policy["toolchain"]
    canonical = binding["repository"] == owner.CONSOLIDATED_REPOSITORY
    source = {
        "repository": binding["repository"],
        "candidate_commit": tool["source_commit"],
        "source_tree": tool["source_tree"],
    }
    if canonical:
        source = owner.docs_operational_source(binding)
        owner.require(
            tool["source_binding"] == source
            and tool["source_commit"] == source["candidate_commit"]
            and tool["source_tree"] == source["source_tree"]
            and tool["source_sha256"] == binding["source_sha256"],
            "HISTORICAL_CANONICAL_PRIVATE_SOURCE_CHANGED",
        )
    owner.require(
        set(policy["components"]) == {owner.component_scope(binding)}
        and all(
            isinstance(source[key], str) and re.fullmatch(r"[a-f0-9]{40}", source[key])
            for key in ("candidate_commit", "source_tree")
        )
        and owner.HEX.fullmatch(tool["source_sha256"]),
        "HISTORICAL_PRIVATE_POLICY_SOURCE_REQUIRED",
    )
    directory = installer.INSTALL_PARENT / (
        ("ai-docs-internal-canonical-" if canonical else "ai-docs-internal-")
        + source["source_tree"]
    )
    owner.private(directory, directory=True, uid=uid)
    owner.private(directory / "policy.json", uid=uid)
    owner.require(
        trust["runner_root"] == str(directory / "runners")
        and owner.file_digest(directory / "policy.json") == trust["policy_sha256"],
        "HISTORICAL_PRIVATE_INSTALLATION_POLICY_CHANGED",
    )
    receipt = read(directory / "installation.json", uid=uid)
    mapping = installer.PRIVATE_DOCS_ALLOWED
    files = receipt.get("files")
    owner.require(
        receipt.get("state") == "INSTALLED_NOT_COMMISSIONED"
        and receipt.get("repository") == binding["repository"]
        and receipt.get("source") == source["candidate_commit"]
        and receipt.get("source_tree") == source["source_tree"]
        and receipt.get("policy_sha256") == trust["policy_sha256"]
        and type(receipt.get("provider_requests")) is int
        and receipt["provider_requests"] == 0
        and (not canonical or receipt.get("source_binding") == source)
        and isinstance(files, dict)
        and REQUIRED_HELPERS <= set(files) <= set(mapping),
        "HISTORICAL_PRIVATE_INSTALLATION_RECEIPT_CHANGED",
    )
    profile = policy["components"][owner.component_scope(binding)]
    script = "runners/oracle_docs_internal_runner.py"
    owner.require(
        profile["publication_mechanism"]
        == "existing-isolated-owner-cloudflare-pages-cli"
        and set(profile["runners"]) == set(owner.PHASES)
        and all(
            item["path"] == str(directory / script) and item["sha256"] == files[script]
            for item in profile["runners"].values()
        ),
        "HISTORICAL_PRIVATE_RUNNER_CHANGED",
    )
    archive = directory / "tool-source.tar"
    owner.private(archive, uid=uid)
    owner.require(
        archive.stat().st_size <= 64 * 1024**2
        and owner.file_digest(archive) == tool["source_sha256"],
        "HISTORICAL_PRIVATE_TOOL_SOURCE_CHANGED",
    )
    _, upstream = source_parser.source_inventory(archive, source)
    for local, pin in files.items():
        path = directory / local
        owner.private(path, uid=uid)
        owner.require(
            isinstance(pin, str)
            and owner.HEX.fullmatch(pin)
            and pin == upstream.get(mapping[local])
            and owner.file_digest(path) == pin,
            "HISTORICAL_PRIVATE_HELPER_BYTES_CHANGED",
        )
    owner.require(
        files["oracle_owner.py"] == trust["verifier_sha256"],
        "HISTORICAL_PRIVATE_ORIGINAL_VERIFIER_CHANGED",
    )
    return policy


def operation(root, binding, identifier, kind, *, uid=0):
    """Return authenticated historical facts, never an active release decision."""
    owner.require(
        kind in {"documentation-preview-intent", "deployment-intent"},
        "HISTORICAL_PRIVATE_OPERATION_KIND_REQUIRED",
    )
    owner.identifier(identifier)
    root = Path(root)
    owner.private(root, directory=True, uid=uid)
    trust = read(root / "trust.json", uid=uid)
    for name in ("public.pem", "policy.json", "records.sqlite"):
        owner.private(root / name, uid=uid)
    registry = read(owner.ANCHOR, uid=uid)
    owner.commissioned(registry, root, trust)
    owner.require(
        owner.file_digest(root / "public.pem") == trust["key_id"]
        and owner.file_digest(root / "policy.json") == trust["policy_sha256"]
        and owner.file_digest(owner.OPENSSL) == trust["openssl_sha256"],
        "HISTORICAL_PRIVATE_ISSUER_CUSTODY_CHANGED",
    )
    policy = installation(binding, root, trust, uid=uid)
    db = sqlite3.connect(
        (root / "records.sqlite").as_uri() + "?mode=ro", uri=True, timeout=20
    )
    db.execute("PRAGMA query_only=ON")
    db.execute(
        "BEGIN"
    )  # One read-only snapshot for indices, signatures and revocations.
    cache, active, revoked = {}, set(), set()

    def record(record_id, expected_kind=None):
        owner.identifier(record_id)
        owner.require(
            record_id not in active and len(cache) + len(active) < 32,
            "HISTORICAL_PRIVATE_CHAIN_CYCLE_OR_BOUND",
        )
        if record_id in cache:
            result = cache[record_id]
            owner.require(
                expected_kind is None or result["kind"] == expected_kind,
                "HISTORICAL_PRIVATE_RECORD_KIND_CHANGED",
            )
            return result
        active.add(record_id)
        row = db.execute(
            "SELECT envelope,revoked,parent,kind,scope,created FROM records WHERE id=?",
            (record_id,),
        ).fetchone()
        owner.require(
            row and len(row[0]) <= 1024**2, "HISTORICAL_PRIVATE_RECORD_MISSING"
        )
        envelope = json.loads(row[0])
        value, signature = envelope["record"], envelope["signature"]
        owner.require(
            signature["algorithm"] == "Ed25519"
            and signature["key_id"] == trust["key_id"],
            "HISTORICAL_PRIVATE_RECORD_SIGNER_CHANGED",
        )
        owner.signed_bytes(
            None,
            root / "public.pem",
            owner.canonical(value),
            base64.b64decode(signature["value"], validate=True),
        )
        owner.require(
            type(value.get("schema_version")) is int
            and value["schema_version"] == 1
            and value["id"] == record_id
            and value["kind"] == row[3]
            and value["parent"] == row[2]
            and value["issued_at"] == row[5]
            and value["binding"] == binding
            and owner.component_scope(binding) == row[4]
            and (expected_kind is None or value["kind"] == expected_kind)
            and type(value["workflow_run_id"]) is int
            and value["workflow_run_id"] == 0
            and value["owner_provenance"]
            == {
                "mechanism": "commissioned-pinned-OpenSSH-and-authenticated-owner",
                "owner": owner.OWNER,
                "installation_id": trust["installation_id"],
                "verifier_sha256": trust["verifier_sha256"],
            },
            "HISTORICAL_PRIVATE_SIGNED_INDEX_OR_SOURCE_CHANGED",
        )
        issued, expiry = (
            datetime.fromisoformat(value[key]) for key in ("issued_at", "expires_at")
        )
        owner.require(
            issued.utcoffset() == expiry.utcoffset() == timedelta()
            and timedelta() < expiry - issued <= timedelta(hours=24)
            and value["execution_context"]
            == (
                "owner-operated-oracle-staging"
                if value["kind"]
                in {
                    "context",
                    "qualification",
                    "documentation-preview-intent",
                    "documentation-preview-receipt",
                }
                else "owner-operated-oracle-release"
            ),
            "HISTORICAL_PRIVATE_RECORD_LIFETIME_OR_CONTEXT_CHANGED",
        )
        if row[1]:
            revoked.add(record_id)
        owner.binding_valid(value["binding"], policy)
        if value["parent"]:
            record(value["parent"])
        if value["kind"] == "authorization":
            owner.require(
                value["details"]["decision"] == "approve"
                and value["details"]["physical_hardware_authorized"] is False,
                "HISTORICAL_PRIVATE_AUTHORIZATION_CHANGED",
            )
            record(value["details"]["attempt_id"], "authorization-attempt")
        active.remove(record_id)
        cache[record_id] = value
        return value

    try:
        observed = record(identifier, kind)
        state, accepted_id = None, None
        if kind == "deployment-intent":
            row = db.execute(
                "SELECT state FROM deployments WHERE id=?", (identifier,)
            ).fetchone()
            owner.require(row, "HISTORICAL_PRIVATE_DEPLOYMENT_INDEX_MISSING")
            state = row[0]
            owner.require(
                state in {"request-recorded", "deployed-unverified", "accepted"},
                "HISTORICAL_PRIVATE_DEPLOYMENT_STATE_CHANGED",
            )
            if state == "accepted":
                ids = db.execute(
                    "SELECT id FROM records WHERE kind='production-verification' AND parent=? ORDER BY sequence DESC LIMIT 33",
                    (identifier,),
                ).fetchall()
                owner.require(
                    1 <= len(ids) <= 32, "HISTORICAL_PRIVATE_ACCEPTANCE_MISSING"
                )
                accepted = record(ids[0][0], "production-verification")
                receipts = db.execute(
                    "SELECT id FROM records WHERE kind='deployment-receipt' AND parent=? LIMIT 2",
                    (identifier,),
                ).fetchall()
                owner.require(
                    len(receipts) == 1, "HISTORICAL_PRIVATE_PROVIDER_RECEIPT_MISSING"
                )
                receipt = record(receipts[0][0], "deployment-receipt")
                accepted_id = accepted["details"]["observations"]["deployment_id"]
                owner.require(
                    isinstance(accepted_id, str)
                    and accepted_id
                    and receipt["details"]["observations"]["deployment_id"]
                    == accepted_id
                    and not revoked,
                    "HISTORICAL_PRIVATE_ACCEPTANCE_REVOKED_OR_CHANGED",
                )
        return {
            "record": observed,
            "state": state,
            "accepted_deployment_id": accepted_id,
            "historical_only": True,
            "release_authorized": False,
        }
    finally:
        db.close()
