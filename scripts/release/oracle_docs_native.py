"""Source-bound native evidence for the existing Oracle owner record store.

A generated producer key is untrusted until a separate owner commissioning action.
Native signatures bind one reserved context/challenge; neither these signatures nor
their imported receipts authorize a production deployment.
"""

import base64
import fcntl
import hashlib
import json
import os
from datetime import datetime, timedelta

import oracle_owner as owner

DOMAIN = "onesa-docs-native-attestation/v1"
REGISTER = "native-producer-registration"
COMMISSION = "native-producer-commission"
SESSION = "documentation-qualification-session"
CHALLENGE = "native-observation-challenge"
OBSERVATION = "native-observation"
COMPLETE = "documentation-qualification-completion-intent"


def scope(store, binding):
    owner.require(
        binding["repository"] == "DruHustle/onesa-ai-platform"
        and binding["component"] in {"docs-public", "docs-internal"},
        "DOCS_NATIVE_COMPONENT_SCOPE",
    )
    owner.binding_valid(binding, store.policy)
    pin = store.policy["toolchain"]["native_producer_sha256"]
    owner.require(
        isinstance(pin, str) and owner.HEX.fullmatch(pin),
        "COMMISSIONED_NATIVE_PRODUCER_PIN_REQUIRED",
    )
    return pin


def write(path, raw):
    with os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb"
    ) as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())


def public_key(raw):
    owner.require(
        isinstance(raw, str) and len(raw) <= 256, "BOUNDED_ED25519_PUBLIC_KEY_REQUIRED"
    )
    lines = raw.splitlines()
    owner.require(
        len(lines) == 3
        and lines[0] == "-----BEGIN PUBLIC KEY-----"
        and lines[-1] == "-----END PUBLIC KEY-----",
        "ONLY_NATIVE_PUBLIC_KEY_ACCEPTED",
    )
    try:
        der = base64.b64decode(lines[1], validate=True)
    except ValueError:
        raise owner.Rejected("INVALID_NATIVE_PUBLIC_KEY") from None
    owner.require(
        len(der) == 44 and der[:12] == bytes.fromhex("302a300506032b6570032100"),
        "ED25519_NATIVE_KEY_REQUIRED",
    )
    return ("\n".join(lines) + "\n").encode()


def register(store, binding, pem):
    pin = scope(store, binding)
    ci = store.github.qualify(binding)
    raw = public_key(pem)
    digest = hashlib.sha256(raw).hexdigest()
    owner.require(
        digest != store.trust["key_id"],
        "ISSUER_SIGNING_KEY_CANNOT_BE_A_NATIVE_PRODUCER",
    )
    parent = store.root / "native-producers"
    parent.mkdir(mode=0o700, exist_ok=True)
    owner.private(parent, directory=True, uid=store.root.stat().st_uid)
    with store.transaction():
        result = store.put(
            REGISTER,
            binding,
            {
                "state": "PENDING_EXPLICIT_OWNER_COMMISSION",
                "public_key_sha256": digest,
                "producer_sha256": pin,
                "purpose": DOMAIN,
                "ci": ci,
                "production_deployment_authorized": False,
            },
            ttl=86400,
        )
        write(parent / (result["record"]["id"] + ".pub.pem"), raw)
    return result


def possession(registration):
    return owner.canonical(
        {
            "purpose": DOMAIN + "/key-possession",
            "registration_id": registration["id"],
            "binding": registration["binding"],
            "producer_sha256": registration["details"]["producer_sha256"],
        }
    )


def verify_signature(store, registration, raw, signature):
    owner.require(
        isinstance(signature, str) and len(signature) <= 128,
        "BOUNDED_NATIVE_SIGNATURE_REQUIRED",
    )
    try:
        decoded = base64.b64decode(signature, validate=True)
    except ValueError:
        raise owner.Rejected("INVALID_NATIVE_SIGNATURE_ENCODING") from None
    owner.require(len(decoded) == 64, "ED25519_NATIVE_SIGNATURE_REQUIRED")
    key = store.root / "native-producers" / (registration["id"] + ".pub.pem")
    owner.private(key, uid=store.root.stat().st_uid)
    owner.require(
        owner.file_digest(key) == registration["details"]["public_key_sha256"],
        "NATIVE_PUBLIC_KEY_CHANGED",
    )
    owner.signed_bytes(None, key, raw, decoded)


def commission(store, registration_id, signature):
    registered = store.get(registration_id, REGISTER)["record"]
    binding = registered["binding"]
    pin = scope(store, binding)
    store.github.qualify(binding)
    owner.require(
        registered["details"]["producer_sha256"] == pin,
        "REGISTERED_NATIVE_SOURCE_CHANGED",
    )
    verify_signature(store, registered, possession(registered), signature)
    lock = store.root / "native-trust.lock"
    with os.fdopen(
        os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600), "r+"
    ) as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        path = store.root / "native-trust.json"
        if path.exists():
            owner.private(path, uid=store.root.stat().st_uid)
        previous = path.read_bytes() if path.exists() else None
        anchor = (
            json.loads(previous)
            if previous
            else {
                "installation_id": store.trust["installation_id"],
                "issuer_key_id": store.trust["key_id"],
                "producers": {},
            }
        )
        owner.require(
            anchor["installation_id"] == store.trust["installation_id"]
            and anchor["issuer_key_id"] == store.trust["key_id"],
            "NATIVE_TRUST_INSTALLATION_CHANGED",
        )
        if registration_id in anchor["producers"]:
            return active(store, registration_id, binding)
        with store.transaction():
            result = store.put(
                COMMISSION,
                binding,
                {
                    "registration_id": registration_id,
                    "public_key_sha256": registered["details"]["public_key_sha256"],
                    "producer_sha256": pin,
                    "purpose": DOMAIN,
                    "explicit_owner_commission": True,
                    "production_deployment_authorized": False,
                },
                parent=registration_id,
                ttl=86400,
            )
        anchor["producers"][registration_id] = {
            "active": True,
            "commission_record_id": result["record"]["id"],
        }
        temporary = store.root / (".native-trust-" + result["record"]["id"] + ".json")
        write(temporary, owner.canonical(anchor))
        owner.require(
            (path.read_bytes() if path.exists() else None) == previous,
            "CONCURRENT_NATIVE_TRUST_CHANGE",
        )
        os.replace(temporary, path)
        fd = os.open(store.root, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    return result


def active(store, registration_id, binding):
    pin = scope(store, binding)
    path = store.root / "native-trust.json"
    owner.require(
        path.exists() and not path.is_symlink(), "NATIVE_PRODUCER_NOT_COMMISSIONED"
    )
    owner.private(path, uid=store.root.stat().st_uid)
    anchor = json.loads(path.read_bytes())
    owner.require(
        anchor["installation_id"] == store.trust["installation_id"]
        and anchor["issuer_key_id"] == store.trust["key_id"],
        "NATIVE_TRUST_INSTALLATION_CHANGED",
    )
    entry = anchor["producers"].get(registration_id)
    owner.require(entry and entry["active"] is True, "NATIVE_PRODUCER_NOT_COMMISSIONED")
    registration = store.get(registration_id, REGISTER, binding)["record"]
    commissioned = store.get(entry["commission_record_id"], COMMISSION, binding)[
        "record"
    ]
    owner.require(
        commissioned["parent"] == registration_id
        and commissioned["details"]["registration_id"] == registration_id
        and commissioned["details"]["producer_sha256"]
        == registration["details"]["producer_sha256"]
        == pin
        and commissioned["details"]["public_key_sha256"]
        == registration["details"]["public_key_sha256"]
        and commissioned["details"]["explicit_owner_commission"] is True,
        "NATIVE_PRODUCER_COMMISSION_MISMATCH",
    )
    return registration


def begin_qualification(store, context_id, registration_id):
    import oracle_docs_runner as docs

    context = store.get(context_id, "context")["record"]
    binding = context["binding"]
    active(store, registration_id, binding)
    ci = store.github.qualify(binding)
    preview = docs.preview_for_binding(store, binding)
    target = docs.target_for_observation(
        store, binding, preview["parent"], production=False
    )
    with store.transaction():
        store.get(context_id, "context", binding)
        changed = store.db.execute(
            "UPDATE contexts SET state='reserved' WHERE id=? AND state='issued'",
            (context_id,),
        ).rowcount
        owner.require(
            changed == 1, "NATIVE_CONTEXT_ALREADY_RESERVED_OR_CONSUMED_INSPECT_ONLY"
        )
        session = store.put(
            SESSION,
            binding,
            {
                "ci": ci,
                "preview_receipt_id": preview["id"],
                "registration_id": registration_id,
                "production_deployment_authorized": False,
            },
            parent=context_id,
        )
        challenge = store.put(
            CHALLENGE,
            binding,
            {
                "registration_id": registration_id,
                "environment": "staging",
                "context_id": context_id,
                "preview_receipt_id": preview["id"],
                "session_id": session["record"]["id"],
                "target": target,
                "production_deployment_authorized": False,
            },
            parent=session["record"]["id"],
        )
    return challenge


def decode(raw):
    owner.require(
        isinstance(raw, bytes) and 0 < len(raw) <= 1024 * 1024,
        "BOUNDED_NATIVE_RECEIPT_REQUIRED",
    )

    def unique(pairs):
        result = {}
        for key, value in pairs:
            owner.require(key not in result, "DUPLICATE_NATIVE_JSON_KEY")
            result[key] = value
        return result

    value = json.loads(raw, object_pairs_hook=unique)
    owner.require(
        isinstance(value, dict) and set(value) == {"payload", "signature"},
        "SIGNED_NATIVE_ENVELOPE_REQUIRED",
    )
    return value


def import_observation(store, raw):
    import oracle_docs_runner as docs

    envelope = decode(raw)
    payload = envelope["payload"]
    owner.require(
        isinstance(payload, dict)
        and set(payload)
        == {
            "purpose",
            "schema_version",
            "receipt_id",
            "challenge_id",
            "registration_id",
            "binding",
            "workflow_run_id",
            "environment",
            "observed_at",
            "producer_sha256",
            "evidence",
        },
        "EXACT_NATIVE_PAYLOAD_REQUIRED",
    )
    owner.require(
        payload["purpose"] == DOMAIN
        and type(payload["schema_version"]) is int
        and payload["schema_version"] == 1
        and type(payload["workflow_run_id"]) is int
        and payload["workflow_run_id"] == 0,
        "NATIVE_OWNER_RUN_ZERO_WITH_PROVENANCE_REQUIRED",
    )
    owner.identifier(payload["receipt_id"])
    binding = payload["binding"]
    challenge = store.get(payload["challenge_id"], CHALLENGE, binding)["record"]
    owner.require(
        challenge["details"]["registration_id"] == payload["registration_id"]
        and challenge["details"]["environment"] == payload["environment"],
        "NATIVE_CHALLENGE_SCOPE_CHANGED",
    )
    registration = active(store, payload["registration_id"], binding)
    owner.require(
        payload["producer_sha256"] == registration["details"]["producer_sha256"],
        "NATIVE_PRODUCER_PIN_CHANGED",
    )
    verify_signature(
        store, registration, owner.canonical(payload), envelope["signature"]
    )
    observed = datetime.fromisoformat(payload["observed_at"])
    owner.require(
        observed.utcoffset() == timedelta()
        and timedelta() <= store.clock() - observed < timedelta(minutes=5),
        "NATIVE_OBSERVATION_EXPIRED_OR_FUTURE",
    )
    docs.validate_native(store, challenge, payload)
    with store.transaction():
        store.get(challenge["id"], CHALLENGE, binding)
        active(store, payload["registration_id"], binding)
        if payload["environment"] == "staging":
            row = store.db.execute(
                "SELECT state FROM contexts WHERE id=?",
                (challenge["details"]["context_id"],),
            ).fetchone()
            owner.require(
                row and row[0] == "reserved",
                "NATIVE_QUALIFICATION_SESSION_NO_LONGER_RESERVED",
            )
        previous = store.db.execute(
            "SELECT id,envelope FROM records WHERE kind=? AND parent=?",
            (OBSERVATION, challenge["id"]),
        ).fetchall()
        owner.require(len(previous) <= 1, "DUPLICATE_NATIVE_OBSERVATIONS")
        if previous:
            record = store.get(previous[0][0], OBSERVATION, binding)
            owner.require(
                record["record"]["details"]["native_payload_sha256"]
                == owner.digest(payload),
                "NATIVE_CHALLENGE_ALREADY_USED_WITH_DIFFERENT_EVIDENCE",
            )
            return record
        return store.put(
            OBSERVATION,
            binding,
            {
                "native_payload": payload,
                "native_payload_sha256": owner.digest(payload),
                "registration_id": payload["registration_id"],
                "production_deployment_authorized": False,
            },
            parent=challenge["id"],
        )


def complete_qualification(store, context_id):
    context = store.get(context_id, "context")["record"]
    binding = context["binding"]
    scope(store, binding)
    staging_observation(store, context_id)
    with store.transaction():
        row = store.db.execute(
            "SELECT state FROM contexts WHERE id=?", (context_id,)
        ).fetchone()
        owner.require(row and row[0] == "reserved", "NATIVE_CONTEXT_NOT_RESERVED")
        sessions = store.db.execute(
            "SELECT id FROM records WHERE kind=? AND parent=?", (SESSION, context_id)
        ).fetchall()
        owner.require(len(sessions) == 1, "EXACT_NATIVE_QUALIFICATION_SESSION_REQUIRED")
        previous = store.db.execute(
            "SELECT id FROM records WHERE kind=? AND parent=?", (COMPLETE, context_id)
        ).fetchall()
        owner.require(
            not previous, "NATIVE_QUALIFICATION_COMPLETION_ALREADY_STARTED_INSPECT_ONLY"
        )
        store.put(COMPLETE, binding, {"automatic_retry": False}, parent=context_id)
    ci = store.github.qualify(binding)
    stage = store.runner("staging", binding, {"context_id": context_id})
    operations = store.runner("operations", binding, {"context_id": context_id})
    with store.transaction():
        store.get(context_id, "context", binding)
        result = store.put(
            "qualification",
            binding,
            {"ci": ci, "staging": stage, "operations": operations},
            parent=context_id,
        )
        changed = store.db.execute(
            "UPDATE contexts SET state='consumed' WHERE id=? AND state='reserved'",
            (context_id,),
        ).rowcount
        owner.require(changed == 1, "NATIVE_CONTEXT_CONCURRENT_COMPLETION_REFUSED")
    return result


def observation_for_challenge(store, challenge):
    """Read one currently valid signed observation; do not repeat native tests."""
    binding = challenge["binding"]
    rows = store.db.execute(
        "SELECT id FROM records WHERE kind=? AND parent=?",
        (OBSERVATION, challenge["id"]),
    ).fetchall()
    owner.require(len(rows) == 1, "CURRENT_SIGNED_NATIVE_OBSERVATION_REQUIRED")
    observed = store.get(rows[0][0], OBSERVATION, binding)["record"]
    payload = observed["details"]["native_payload"]
    owner.require(
        payload["challenge_id"] == challenge["id"]
        and owner.digest(payload) == observed["details"]["native_payload_sha256"],
        "SIGNED_NATIVE_OBSERVATION_SCOPE_CHANGED",
    )
    active(store, payload["registration_id"], binding)
    import oracle_docs_runner as docs

    docs.validate_native(store, challenge, payload)
    return observed


def staging_observation(store, context_id):
    context = store.get(context_id, "context")["record"]
    sessions = store.db.execute(
        "SELECT id FROM records WHERE kind=? AND parent=?", (SESSION, context_id)
    ).fetchall()
    owner.require(len(sessions) == 1, "EXACT_NATIVE_QUALIFICATION_SESSION_REQUIRED")
    session = store.get(sessions[0][0], SESSION, context["binding"])["record"]
    challenges = store.db.execute(
        "SELECT id FROM records WHERE kind=? AND parent=?", (CHALLENGE, session["id"])
    ).fetchall()
    owner.require(len(challenges) == 1, "EXACT_STAGING_NATIVE_CHALLENGE_REQUIRED")
    challenge = store.get(challenges[0][0], CHALLENGE, context["binding"])["record"]
    owner.require(
        challenge["details"]["environment"] == "staging"
        and challenge["details"]["context_id"] == context_id,
        "STAGING_NATIVE_CONTEXT_CHANGED",
    )
    return observation_for_challenge(store, challenge)


def production_challenge(store, operation_id, registration_id):
    import oracle_docs_runner as docs

    operation = store.get(operation_id, "deployment-intent")["record"]
    binding = operation["binding"]
    active(store, registration_id, binding)
    scope(store, binding)
    store.get(operation["parent"], "authorization", binding)
    provider = docs.inspect_production(store, operation)
    target = docs.target_for_observation(store, binding, operation_id, production=True)
    with store.transaction():
        store.get(operation_id, "deployment-intent", binding)
        active(store, registration_id, binding)
        previous = store.db.execute(
            "SELECT id FROM records WHERE kind=? AND parent=?",
            (CHALLENGE, operation_id),
        ).fetchall()
        owner.require(len(previous) <= 1, "DUPLICATE_PRODUCTION_CHALLENGES_REFUSED")
        if previous:
            return store.get(previous[0][0], CHALLENGE, binding)
        return store.put(
            CHALLENGE,
            binding,
            {
                "registration_id": registration_id,
                "environment": "production",
                "operation_id": operation_id,
                "provider": provider,
                "target": target,
                "production_deployment_authorized": False,
            },
            parent=operation_id,
        )


def production_observation(store, operation_id):
    operation = store.get(operation_id, "deployment-intent")["record"]
    rows = store.db.execute(
        "SELECT id FROM records WHERE kind=? AND parent=?", (CHALLENGE, operation_id)
    ).fetchall()
    owner.require(len(rows) == 1, "EXACT_PRODUCTION_NATIVE_CHALLENGE_REQUIRED")
    challenge = store.get(rows[0][0], CHALLENGE, operation["binding"])["record"]
    owner.require(
        challenge["details"]["environment"] == "production"
        and challenge["details"]["operation_id"] == operation_id,
        "PRODUCTION_NATIVE_OPERATION_CHANGED",
    )
    return observation_for_challenge(store, challenge)
