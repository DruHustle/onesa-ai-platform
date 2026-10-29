"""Owner-run Docs Preview preparation using the existing commissioned record store.

Preview receipts retain run ID zero and genuine positive build/CI references.
They never authorize production. Qualification, authorization, deployment and
production observation remain the existing oracle_owner commands and safeguards.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "runners"))
import oracle_docs_runner as docs
import oracle_owner as owner

INTENT = "documentation-preview-intent"
RECEIPT = "documentation-preview-receipt"


def component_scope(store, binding):
    owner.require(
        binding["repository"] == "DruHustle/onesa-ai-platform"
        and binding["component"] in {"docs-public", "docs-internal"},
        "EXACT_DOCS_COMPONENT_REQUIRED",
    )
    owner.binding_valid(binding, store.policy)
    return binding["repository"] + ":" + binding["component"]


def receipt_for(store, intent, *, reconcile=False):
    original = store.get(intent, INTENT)["record"]
    binding = original["binding"]
    component_scope(store, binding)
    # Inspection resolves the already recorded operation; it never invokes create.
    observation = docs.inspect_preview(store, original)
    owner.require(
        observation["operation_id"] == intent
        and observation["binding"] == binding
        and type(observation["workflow_run_id"]) is int
        and observation["workflow_run_id"] == 0
        and observation["environment"] == "staging"
        and observation["production_deployment_authorized"] is False,
        "ACTUAL_OWNER_PREVIEW_SCOPE_REQUIRED",
    )
    with store.transaction():
        existing = store.db.execute(
            "SELECT id FROM records WHERE kind=? AND parent=?", (RECEIPT, intent)
        ).fetchall()
        owner.require(len(existing) <= 1, "DUPLICATE_PREVIEW_RECEIPTS_REFUSED")
        if existing:
            result = store.get(existing[0][0], RECEIPT, binding)
            owner.require(
                result["record"]["details"]["observation"]["deployment_id"]
                == observation["deployment_id"],
                "PREVIEW_PROVIDER_IDENTITY_CHANGED_INSPECT_ONLY",
            )
            return result
        return store.put(
            RECEIPT,
            binding,
            {
                "observation": observation,
                "reconciled_read_only": reconcile,
                "hosted_acceptance": "PENDING_NATIVE_OWNER_OBSERVATION",
                "production_deployment_authorized": False,
            },
            parent=intent,
            ttl=21600,
        )


def publish_preview(store, binding):
    scope = component_scope(store, binding)
    ci = store.github.qualify(binding)
    prepared = docs.prepare(store, binding)
    with store.transaction():
        rows = store.db.execute(
            "SELECT envelope FROM records WHERE kind=? AND scope=?", (INTENT, scope)
        ).fetchall()
        previous = [
            json.loads(row[0])["record"]
            for row in rows
            if json.loads(row[0])["record"]["binding"] == binding
        ]
        owner.require(len(previous) <= 1, "DUPLICATE_PREVIEW_INTENTS_REFUSED")
        if previous:
            return {
                "state": "EXISTING_PREVIEW_OPERATION_INSPECT_ONLY_NO_DUPLICATE_REQUEST",
                "operation_id": previous[0]["id"],
                "production_deployment_authorized": False,
            }
        # This durable owner-signed intent commits before the first provider request.
        intent = store.put(
            INTENT,
            binding,
            {
                "ci": ci,
                "build": prepared,
                "provider_create_budget": 1,
                "automatic_retry": False,
                "production_deployment_authorized": False,
            },
            ttl=21600,
        )
    operation = intent["record"]["id"]
    docs.create_preview(store, intent["record"])
    return receipt_for(store, operation)


def native_preflight(store, binding):
    """Issue bounded target data for full preflight; never qualification or a PASS."""
    component_scope(store, binding)
    store.github.qualify(binding)
    preview = docs.preview_for_binding(store, binding)
    target = docs.target_for_observation(
        store, binding, preview["parent"], production=False
    )
    with store.transaction():
        store.get(preview["id"], RECEIPT, binding)
        return store.put(
            "native-preflight-target",
            binding,
            {
                "target": target,
                "environment": "staging",
                "qualification_reserved": False,
                "hosted_acceptance": "NOT_PERFORMED",
                "production_deployment_authorized": False,
            },
            parent=preview["id"],
            # The complete read-only native matrix has a twelve-minute deadline.
            # This target grants no qualification, signature or deployment right.
            ttl=900,
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=[
            "publish-preview",
            "inspect-preview",
            "inspect-publications",
            "preflight",
            "register-native",
            "commission-native",
            "begin-qualification",
            "import-native",
            "complete-qualification",
            "production-challenge",
            "native-preflight",
        ],
    )
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--component", choices=["docs-public", "docs-internal"])
    parser.add_argument("--record")
    parser.add_argument("--registration")
    args = parser.parse_args()
    owner.require(
        os.geteuid() == 0
        and os.getenv("SUDO_USER") == "ubuntu"
        and not os.getenv("GITHUB_ACTIONS"),
        "EXTERNAL_OWNER_SSH_SUDO_REQUIRED",
    )
    raw = sys.stdin.buffer.read(1024 * 1024 + 32769)
    owner.require(
        0 < len(raw) <= 1024 * 1024 + 32768, "BOUNDED_PRIVATE_OWNER_REQUEST_REQUIRED"
    )
    request = json.loads(raw)
    token = request.pop("owner_token", None)
    store = owner.Store(args.store, owner.GitHub(token))
    import oracle_docs_native as native

    fields = {
        "register-native": {"public_key"},
        "commission-native": {"possession_signature"},
        "import-native": {"native_envelope"},
    }.get(args.action, set())
    owner.require(set(request) == fields, "NO_CALLER_PASS_OR_AUTHORIZATION_ACCEPTED")
    if args.action == "inspect-publications":
        owner.require(
            not any([args.record, args.registration, args.component]),
            "READ_ONLY_RETAINED_PUBLICATION_INSPECTION_ONLY",
        )
        with docs.component_lock():
            result = {
                "state": "RETAINED_PROVIDER_OUTCOMES_OBSERVED_NOT_ACCEPTANCE",
                "observations": docs.inspect_retained_publications(store),
                "provider_writes": 0,
                "production_deployment_authorized": False,
            }
    elif args.action == "register-native":
        owner.require(
            args.component and not args.record and not args.registration,
            "EXACT_NATIVE_REGISTRATION_SCOPE_REQUIRED",
        )
        result = native.register(
            store, docs.plan_binding(store, args.component), request["public_key"]
        )
    elif args.action == "commission-native":
        owner.require(
            args.record and not args.component and not args.registration,
            "EXACT_NATIVE_COMMISSION_RECORD_REQUIRED",
        )
        result = native.commission(store, args.record, request["possession_signature"])
    elif args.action == "begin-qualification":
        owner.require(
            args.record and args.registration and not args.component,
            "EXACT_NATIVE_CONTEXT_AND_PRODUCER_REQUIRED",
        )
        result = native.begin_qualification(store, args.record, args.registration)
    elif args.action == "production-challenge":
        owner.require(
            args.record and args.registration and not args.component,
            "EXACT_PRODUCTION_OPERATION_AND_PRODUCER_REQUIRED",
        )
        result = native.production_challenge(store, args.record, args.registration)
    elif args.action == "import-native":
        owner.require(
            not any([args.record, args.registration, args.component]),
            "SIGNED_NATIVE_ENVELOPE_ONLY",
        )
        result = native.import_observation(
            store, owner.canonical(request["native_envelope"])
        )
    elif args.action == "complete-qualification":
        owner.require(
            args.record and not any([args.registration, args.component]),
            "EXACT_RESERVED_CONTEXT_REQUIRED",
        )
        result = native.complete_qualification(store, args.record)
    elif args.action == "inspect-preview":
        owner.require(
            args.record and not any([args.component, args.registration]),
            "EXACT_PREVIEW_RECORD_REQUIRED",
        )
        result = receipt_for(store, owner.identifier(args.record), reconcile=True)
    else:
        owner.require(
            args.component and not any([args.record, args.registration]),
            "EXACT_DOCS_COMPONENT_REQUIRED",
        )
        binding = docs.plan_binding(store, args.component)
        result = (
            publish_preview(store, binding)
            if args.action == "publish-preview"
            else native_preflight(store, binding)
            if args.action == "native-preflight"
            else docs.preflight(store, binding)
        )
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except (owner.Rejected, OSError, ValueError, KeyError, TypeError):
        raise SystemExit(
            "DOCS_OWNER_OPERATION_REFUSED_INSPECT_PRIVATE_STATE_NO_RETRY"
        ) from None
