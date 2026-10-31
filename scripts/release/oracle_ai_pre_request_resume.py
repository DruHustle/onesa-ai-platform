"""Owner-commissioned continuation before the original, never issued provider request.

This extension cannot renew a context or authorization, change a source binding,
or repeat a provider call. Installation alone grants no trust. A separate owner
commission must bind this file and the exact existing intent in the trust anchor.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path


def require(value, reason):
    if not value:
        raise ValueError(reason)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def private(path, directory=False):
    path = Path(path)
    require(
        not any(p.is_symlink() for p in [path, *path.parents]), "ALIASED_OWNER_CUSTODY"
    )
    st = path.stat()
    require(st.st_uid == 0 and st.st_mode & 0o077 == 0, "PRIVATE_ROOT_CUSTODY_REQUIRED")
    require(
        path.is_dir() if directory else path.is_file(), "EXACT_CUSTODY_TYPE_REQUIRED"
    )
    return path


def claim(db, operation, create_record):
    """A committed single-use claim precedes execution, including interruptions."""
    db.execute("BEGIN IMMEDIATE")
    try:
        require(
            db.execute(
                "SELECT state FROM deployments WHERE id=?", (operation,)
            ).fetchone()
            == ("request-recorded",),
            "INTENT_IS_NOT_UNISSUED",
        )
        require(
            not db.execute(
                "SELECT 1 FROM records WHERE kind='pre-request-resume-attempt' AND parent=?",
                (operation,),
            ).fetchone(),
            "CONTINUATION_ALREADY_RESERVED_INSPECT_ONLY",
        )
        record = create_record()
        db.execute("COMMIT")
        return record
    except BaseException:
        db.execute("ROLLBACK")
        raise


def zero_request_evidence(config, plan, failure, *, operation_exists, actual):
    require(digest(config["plan"]) == config["plan_sha256"], "SELECTED_PLAN_CHANGED")
    require(not operation_exists, "ANY_OPERATION_DIRECTORY_REQUIRES_INSPECTION_ONLY")
    require(
        failure["phase"] == "deploy"
        and failure["status"] == "FAILED_NOT_QUALIFIED"
        and failure["diagnostic_only"] is True
        and failure["provider_retry_allowed"] is False,
        "ORIGINAL_FAILURE_REQUIRED",
    )
    require(
        failure["failure_code"] == "OPERATIONS_ALERT_OR_UNQUALIFIED_SAMPLE",
        "ONLY_PROVEN_PRE_REQUEST_OPERATIONAL_FAILURE_SUPPORTED",
    )
    require(
        failure["candidate_commit"] == config["binding"]["candidate_commit"]
        and failure["component"] == "api",
        "FAILURE_SOURCE_SCOPE_CHANGED",
    )
    require(
        failure["record_ids"]
        == {
            "authorization_id": config["authorization"],
            "operation_id": config["operation"],
        },
        "FAILURE_INTENT_BINDING_CHANGED",
    )
    require(actual == plan["baseline"]["production"], "PRODUCTION_CHANGED_INSPECT_ONLY")
    return {
        "failure_sha256": config["failure_sha256"],
        "failure_observed_at": failure["observed_at"],
        "actual_retained_production": actual,
        "provider_operation_directory_absent": True,
        "prior_provider_requests": 0,
    }


def original_chain(store, config):
    """Read current signed records and the latest owner decision without renewing them."""
    intent = store.get(config["operation"], "deployment-intent", config["binding"])[
        "record"
    ]
    authorization = store.get(
        config["authorization"], "authorization", config["binding"]
    )["record"]
    qualification = store.get(
        config["qualification"], "qualification", config["binding"]
    )["record"]
    require(
        intent["parent"] == authorization["id"]
        and authorization["parent"] == qualification["id"],
        "ORIGINAL_QUALIFIED_AUTHORIZATION_CHAIN_REQUIRED",
    )
    require(
        intent["details"]
        == {
            "authorization": authorization["id"],
            "provider_request_budget": 1,
            "automatic_retry": False,
        },
        "ORIGINAL_SINGLE_REQUEST_BUDGET_REQUIRED",
    )
    require(
        store.db.execute(
            "SELECT state FROM contexts WHERE id=?", (qualification["parent"],)
        ).fetchone()
        == ("consumed",),
        "ORIGINAL_CONTEXT_MUST_REMAIN_CONSUMED",
    )
    latest = store.db.execute(
        "SELECT id FROM records WHERE kind='authorization-attempt' AND scope=? ORDER BY sequence DESC LIMIT 1",
        (config["binding"]["repository"] + ":api",),
    ).fetchone()
    require(
        latest == (authorization["details"]["attempt_id"],), "OWNER_DECISION_SUPERSEDED"
    )
    require(
        not store.db.execute(
            "SELECT 1 FROM records WHERE parent=? AND kind IN ('deployment-receipt','production-verification')",
            (intent["id"],),
        ).fetchone(),
        "EXISTING_PROVIDER_RECEIPT_REQUIRES_INSPECTION_ONLY",
    )
    return intent, authorization, qualification


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["inspect", "execute"])
    parser.add_argument("--store", type=Path, required=True)
    args = parser.parse_args()
    require(
        os.geteuid() == 0
        and os.getenv("SUDO_USER") == "ubuntu"
        and not os.getenv("GITHUB_ACTIONS"),
        "EXTERNAL_OWNER_SSH_REQUIRED",
    )
    registry = json.loads(private("/etc/onesa/oracle-release-trust.json").read_bytes())
    anchor = registry["installations"][str(args.store)]
    extension = anchor.get("pre_request_resume")
    require(
        anchor["active"] is True and extension and extension["active"] is True,
        "EXPLICIT_OWNER_EXTENSION_COMMISSION_REQUIRED",
    )
    require(
        str(Path(__file__).resolve()) == extension["path"]
        and digest(private(__file__)) == extension["sha256"],
        "COMMISSIONED_EXTENSION_BYTES_REQUIRED",
    )
    config = json.loads(private(extension["configuration"]).read_bytes())
    require(
        digest(extension["configuration"]) == extension["configuration_sha256"],
        "COMMISSIONED_CONTINUATION_SCOPE_CHANGED",
    )
    require(config["store"] == str(args.store), "WRONG_ISSUER_STORE")
    version = private(config["installation"], directory=True)
    for name, pin in config["files"].items():
        require(digest(private(version / name)) == pin, "ORIGINAL_PINNED_TOOL_CHANGED")
    sys.path[:0] = [str(version), str(version / "runners")]
    import oracle_ai_runner as runner
    import oracle_owner as owner

    request = json.load(sys.stdin)
    require(
        set(request) == {"owner_token"},
        "AUTHENTICATED_OWNER_ONLY_NO_CALLER_APPROVAL_JSON",
    )
    store = owner.Store(args.store, owner.GitHub(request.pop("owner_token")))
    intent, authorization, qualification = original_chain(store, config)
    folder, plan = runner.validate_plan(config["binding"])
    require(
        plan["mode"] == "foundation" and plan["verifier_store"] == str(store.root),
        "FOUNDATION_ONLY_SCOPE",
    )
    failure_path = private(config["failure"])
    require(
        digest(failure_path) == config["failure_sha256"],
        "ORIGINAL_FAILURE_BYTES_CHANGED",
    )
    failure = json.loads(failure_path.read_bytes())
    actual = runner.summary(runner.inventory()[runner.TARGET["production"]])
    proof = zero_request_evidence(
        config,
        plan,
        failure,
        operation_exists=(folder / "operations" / intent["id"]).exists(),
        actual=actual,
    )
    if args.action == "inspect":
        print(
            json.dumps(
                {
                    "state": "PROVEN_ZERO_PROVIDER_REQUEST_NOT_AUTHORIZATION",
                    "operation": intent["id"],
                    "proof": proof,
                    "provider_requests": 0,
                }
            )
        )
        return
    # Fresh source/CI, signatures, expiry, revocation and operational gates remain
    # mandatory. The original runner rechecks them again before activation.
    store.github.qualify(config["binding"])
    store.runner(
        "operations",
        config["binding"],
        {"authorization_id": authorization["id"], "before_deployment": True},
    )
    metrics = runner.read(Path("/var/lib/onesa/operations/metrics.json"))
    require(
        dt.datetime.fromisoformat(metrics["checked_at"])
        > dt.datetime.fromisoformat(failure["observed_at"]),
        "FRESH_RESOLVED_OPERATIONAL_SAMPLE_REQUIRED",
    )

    def reserve():
        # CI and operations checks may have waited while the owner changed their
        # decision. Re-read signatures, expiry/revocation, chain and latest attempt
        # while the write lock prevents another decision from racing this claim.
        current = original_chain(store, config)
        require(
            current == (intent, authorization, qualification),
            "ORIGINAL_AUTHORIZATION_CHAIN_CHANGED",
        )
        require(
            not (folder / "operations" / intent["id"]).exists(),
            "PROVIDER_ACTIVITY_APPEARED",
        )
        return store.put(
            "pre-request-resume-attempt",
            config["binding"],
            {
                "decision": "continue-original-unissued-provider-request",
                "original_authorization": authorization["id"],
                "original_qualification": qualification["id"],
                "proof": proof,
                "extension_sha256": extension["sha256"],
                "provider_request_budget": 1,
                "automatic_retry": False,
            },
            parent=intent["id"],
        )

    claim(store.db, intent["id"], reserve)
    receipt = store.runner(
        "deploy",
        config["binding"],
        {"operation_id": intent["id"], "authorization_id": authorization["id"]},
    )
    require(
        isinstance(receipt["observations"].get("deployment_id"), str)
        and receipt["observations"]["deployment_id"],
        "ACTUAL_PROVIDER_RECEIPT_REQUIRED_INSPECT_ONLY",
    )
    with store.transaction():
        store.put("deployment-receipt", config["binding"], receipt, parent=intent["id"])
        changed = store.db.execute(
            "UPDATE deployments SET state='deployed-unverified' WHERE id=? AND state='request-recorded'",
            (intent["id"],),
        ).rowcount
        require(changed == 1, "CONCURRENT_STATE_CHANGED_INSPECT_ONLY")
    print(json.dumps(store.inspect(intent["id"], observe=True)))


if __name__ == "__main__":
    main()
