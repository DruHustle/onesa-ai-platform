"""Locally owned ot-security-evidence/v1; strict wire types and bounded input."""

import json
import re
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, Self
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationInfo,
    field_validator,
    model_validator,
)

from app.schemas import Strict

RawIdentifier = Annotated[
    str, StringConstraints(strict=True, min_length=1, max_length=128, pattern=r"\S")
]
RawShort = Annotated[
    str, StringConstraints(strict=True, min_length=1, max_length=64, pattern=r"\S")
]
Hash = Annotated[str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{64}$")]
Mode = Literal["live", "simulated", "replay"]


def utc(value: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)", value
    ):
        raise ValueError("A real UTC RFC 3339 timestamp is required")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def clean(value: str) -> str:
    """Text stays inert. Common credential representations are never retained."""
    value = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", value)
    value = re.sub(r"(?i)bearer\s+[^\s]+", "Bearer [redacted]", value)
    value = re.sub(
        r"(?i)(password|passwd|secret|token|api[_-]?key|authorization)\s*[:=]\s*[^\s,;]+",
        r"\1=[redacted]",
        value,
    )
    value = re.sub(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^\s]+", "[connection redacted]", value)
    value = re.sub(r"-----BEGIN[^\n]*KEY-----.*", "[key redacted]", value, flags=re.S)
    return value.strip()


class Wire(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)


def safe_identifier(value: str) -> str:
    value.encode("utf-8")
    if "://" in value:
        parsed = urlsplit(value)
        if (
            not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "Opaque URI references cannot include credentials, queries or fragments"
            )
    elif clean(value) != value:
        raise ValueError("Use opaque references without credentials or control characters")
    if any(ord(char) < 32 or ord(char) == 127 for char in value) or not value.strip():
        raise ValueError("Use nonblank references without control characters")
    return value


Identifier = Annotated[RawIdentifier, AfterValidator(safe_identifier)]
Short = Annotated[RawShort, AfterValidator(safe_identifier)]


class AssetRef(Wire):
    namespace: Identifier
    assetId: Identifier
    componentId: Identifier | None


class AuthAttributes(Wire):
    service: Short
    outcome: Literal["denied", "rejected", "failed"]
    reasonCode: Short
    principalRef: Identifier | None = None


class CertificateAttributes(Wire):
    endpointRef: Identifier
    notBefore: str
    notAfter: str
    fingerprintSha256: Hash

    @model_validator(mode="after")
    def dates(self) -> Self:
        if utc(self.notBefore) >= utc(self.notAfter):
            raise ValueError("Certificate validity interval is invalid")
        return self


class ConfigAttributes(Wire):
    configRevision: Identifier
    baselineRevision: Identifier | None = None
    changedKeys: list[Short] = Field(min_length=1, max_length=32)


class IdentityAttributes(Wire):
    inputRef: Identifier
    observedIdentityRef: Identifier


class HealthAttributes(Wire):
    state: Literal["online", "offline", "degraded", "paused"]
    expectedIntervalSeconds: int | None = Field(default=None, ge=1, le=86400)


class SoftwareAttributes(Wire):
    inventoryRef: Identifier
    sha256: Hash


class IntegrityAttributes(Wire):
    previousSha256: Hash
    currentSha256: Hash
    evidenceBasis: Literal["self_reported", "collector_observed", "verified_artifact"]


ATTRIBUTE_TYPES: dict[str, type[Wire]] = {
    "auth.authentication_failed": AuthAttributes,
    "auth.authorization_denied": AuthAttributes,
    "tls.certificate_observed": CertificateAttributes,
    "config.changed": ConfigAttributes,
    "config.drift_observed": ConfigAttributes,
    "identity.unrecognized": IdentityAttributes,
    "collector.health": HealthAttributes,
    "software.inventory_observed": SoftwareAttributes,
    "integrity.change_observed": IntegrityAttributes,
}


class SecurityEvent(Wire):
    schemaVersion: Literal["ot-security-evidence/v1"]
    producerNamespace: Short
    sourceEventId: Identifier
    occurredAt: str
    mode: Mode
    eventType: str
    assetRef: AssetRef | None
    summary: str = Field(max_length=512)
    quality: Literal["good", "uncertain", "bad", "unknown"]
    producerVersion: Short
    attributes: dict[str, Any]
    scenarioRunId: Identifier | None = None
    replayRunId: Identifier | None = None
    producerReceivedAt: str | None = None
    sessionId: Identifier | None = None
    sequence: int | None = Field(default=None, ge=0, le=9007199254740991)
    correlationId: Identifier | None = None

    def wire(self) -> dict[str, Any]:
        result = self.model_dump(exclude_none=True)
        # Required nullable fields remain explicit; optional context is omitted.
        result["assetRef"] = self.assetRef.model_dump() if self.assetRef else None
        return result

    @model_validator(mode="after")
    def contract(self) -> Self:
        utc(self.occurredAt)
        if self.producerReceivedAt is not None:
            utc(self.producerReceivedAt)
        if (self.mode == "simulated" and not self.scenarioRunId) or (
            self.mode == "replay" and not self.replayRunId
        ):
            raise ValueError("Simulated and replay evidence require their own run identity")
        if self.mode != "simulated" and self.scenarioRunId is not None:
            raise ValueError("Scenario identity belongs only to simulated evidence")
        if self.mode != "replay" and self.replayRunId is not None:
            raise ValueError("Replay identity belongs only to replay evidence")
        profile = ATTRIBUTE_TYPES.get(self.eventType)
        if profile is None:
            raise ValueError("Unsupported event type")
        self.attributes = profile.model_validate(self.attributes).model_dump(exclude_none=True)
        if len(json.dumps(self.wire(), ensure_ascii=False, separators=(",", ":")).encode()) > 8192:
            raise ValueError("Event exceeds 8192 UTF-8 bytes")
        return self


def bounded_json(raw: bytes, maximum: int = 1048576) -> Any:
    if len(raw) > maximum:
        raise ValueError("Body exceeds the documented byte limit")
    # Depth is checked before the JSON decoder traverses attacker-controlled structures.
    depth = 0
    quoted = escaped = False
    for char in raw.decode("utf-8"):
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > 12:
                raise ValueError("JSON nesting exceeds 12 levels")
        elif char in "]}":
            depth -= 1

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON fields are not supported")
            result[key] = value
        return result

    def invalid(_value: str) -> None:
        raise ValueError("Nonfinite JSON numbers are not supported")

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)

    def valid_unicode(item: Any) -> None:
        if isinstance(item, str):
            item.encode("utf-8")
        elif isinstance(item, list):
            for child in item:
                valid_unicode(child)
        elif isinstance(item, dict):
            for key, child in item.items():
                key.encode("utf-8")
                valid_unicode(child)

    valid_unicode(value)
    return value


def parse_batch(raw: bytes, ndjson: bool = False) -> list[SecurityEvent]:
    if len(raw) > 1048576:
        raise ValueError("Body exceeds 1048576 bytes")
    if ndjson:
        lines = [line for line in raw.splitlines() if line.strip()]
        if not 1 <= len(lines) <= 100 or any(len(line) > 8192 for line in lines):
            raise ValueError("Use 1–100 events of at most 8192 UTF-8 bytes")
        items = [bounded_json(line, 8192) for line in lines]
    else:
        batch = bounded_json(raw)
        if not isinstance(batch, dict) or set(batch) != {"events"}:
            raise ValueError("A batch must contain only events")
        items = batch["events"]
        if not isinstance(items, list) or not 1 <= len(items) <= 100:
            raise ValueError("Use 1–100 events")
    return [SecurityEvent.model_validate(item) for item in items]


def inline_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Publish this implementation's contract without unresolved local references."""
    schema = model.model_json_schema()
    definitions = schema.pop("$defs", {})

    def resolve(value: Any) -> Any:
        if isinstance(value, list):
            return [resolve(item) for item in value]
        if isinstance(value, dict):
            if "$ref" in value:
                return resolve(definitions[value["$ref"].removeprefix("#/$defs/")])
            return {key: resolve(item) for key, item in value.items()}
        return value

    return dict(resolve(schema))


def event_request_contract() -> dict[str, Any]:
    schema = inline_schema(SecurityEvent)
    schema["properties"]["eventType"] = {"type": "string", "enum": list(ATTRIBUTE_TYPES)}
    schema["allOf"] = [
        {
            "oneOf": [
                {
                    "properties": {
                        "eventType": {"const": name},
                        "attributes": inline_schema(profile),
                    },
                    "required": ["eventType", "attributes"],
                }
                for name, profile in ATTRIBUTE_TYPES.items()
            ]
        }
    ]
    return {
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["events"],
                        "properties": {
                            "events": {
                                "type": "array",
                                "minItems": 1,
                                "maxItems": 100,
                                "items": schema,
                            }
                        },
                    }
                },
                "application/x-ndjson": {
                    "schema": {
                        "type": "string",
                        "maxLength": 1048576,
                        "description": "One event per line; 1–100 events, at most 8192 UTF-8 bytes "
                        "per event and 1048576 bytes total",
                    },
                },
            },
        }
    }


class MetadataInput(Strict):
    @field_validator("name", "zone", "review_note", "note", "title", check_fields=False)
    @classmethod
    def safe_text(cls, value: str, info: ValidationInfo) -> str:
        normalized = clean(value)
        normalized.encode("utf-8")
        minimum = 8 if info.field_name in {"review_note", "note"} else 1
        if len(normalized) < minimum:
            raise ValueError("Provide meaningful nonsecret text")
        return normalized


class AssetCreate(MetadataInput):
    name: str = Field(min_length=1, max_length=120, pattern=r"\S")
    identity: Identifier
    zone: str = Field(min_length=1, max_length=80, pattern=r"\S")
    criticality: Literal["low", "medium", "high", "unknown"] = "unknown"
    review_note: str = Field(min_length=8, max_length=1000)
    twin_asset_id: UUID | None = None
    twin_component_id: UUID | None = None


class SourceCreate(MetadataInput):
    name: str = Field(min_length=1, max_length=120, pattern=r"\S")
    namespace: Short
    modes: list[Mode] = Field(min_length=1, max_length=3)
    endpoint_refs: list[Identifier] = Field(default_factory=list, max_length=20)
    expected_interval_seconds: int = Field(default=300, ge=10, le=86400, strict=True)
    review_note: str = Field(min_length=8, max_length=1000)


class MappingCreate(MetadataInput):
    asset_id: UUID
    namespace: Identifier
    external_asset: Identifier
    external_component: Identifier | None = None
    review_note: str = Field(min_length=8, max_length=1000)


class PolicyCreate(MetadataInput):
    auth_threshold: int = Field(default=5, ge=2, le=100, strict=True)
    denial_threshold: int = Field(default=3, ge=2, le=100, strict=True)
    window_seconds: int = Field(default=300, ge=30, le=3600, strict=True)
    certificate_warning_days: int = Field(default=30, ge=1, le=90, strict=True)
    review_note: str = Field(min_length=8, max_length=1000)


class BaselineCreate(MetadataInput):
    revision: Identifier
    relevant_keys: list[Short] = Field(default_factory=list, max_length=32)
    allowed_identities: list[Identifier] = Field(default_factory=list, max_length=100)
    input_refs: list[Identifier] = Field(default_factory=list, max_length=20)
    review_note: str = Field(min_length=8, max_length=1000)


class InvestigationCreate(MetadataInput):
    finding_id: UUID
    title: str = Field(min_length=1, max_length=160, pattern=r"\S")


class Decision(MetadataInput):
    revision: int = Field(ge=1, strict=True)
    action: Literal[
        "note", "acknowledge", "investigate", "resolve", "dismiss", "accept_risk", "reopen"
    ]
    note: str = Field(min_length=8, max_length=2000, pattern=r"\S")
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=20)
    acceptance_until: str | None = None


class EvidenceRequest(Strict):
    investigation_id: UUID
    expected_sha256: Hash


class SummaryRequest(EvidenceRequest):
    assist: bool = False
    question: str = Field(default="Prepare a review checklist from this evidence", max_length=1000)
    document_ids: list[UUID] = Field(default_factory=list, max_length=3)

    @field_validator("question")
    @classmethod
    def question_text(cls, value: str) -> str:
        value.encode("utf-8")
        return clean(value)


class Demonstration(Strict):
    mode: Literal["simulated", "replay"]
    run_id: Identifier
