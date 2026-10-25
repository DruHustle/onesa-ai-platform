"""Version one twin requests; imported metadata never confers authority."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, Field, model_validator

from app.schemas import Strict


def aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("An explicit timezone is required")
    return value.astimezone(UTC)


Instant = Annotated[datetime, AfterValidator(aware)]
Number = Annotated[float, Field(allow_inf_nan=False, ge=-1e12, le=1e12)]
Text = Annotated[str, Field(min_length=1, max_length=120)]
Mode = Literal["live", "simulated", "replay"]


class Component(Strict):
    id: UUID
    name: Text
    parent_id: UUID | None = None
    external_id: str = Field(default="", max_length=200)
    semantic_reference: str = Field(default="", max_length=400)


class Relationship(Strict):
    source: UUID
    target: UUID
    kind: Literal["drives", "contains", "connected_to", "measures"]


class TemplateCreate(Strict):
    name: Text
    kind: str = Field(min_length=1, max_length=80)
    components: list[Component] = Field(min_length=1, max_length=100)
    relationships: list[Relationship] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def hierarchy(self) -> Self:
        ids = {c.id for c in self.components}
        if len(ids) != len(self.components):
            raise ValueError("Duplicate component identity")
        parents = {c.id: c.parent_id for c in self.components}
        for component in self.components:
            visited: set[UUID] = set()
            current: UUID | None = component.id
            while current is not None:
                if current not in ids or current in visited:
                    raise ValueError("Unresolved or cyclic component hierarchy")
                visited.add(current)
                current = parents[current]
        if any(r.source not in ids or r.target not in ids for r in self.relationships):
            raise ValueError("Relationship crosses template boundary")
        return self


class AssetCreate(Strict):
    template_id: UUID
    name: Text
    serial: Text
    external_id: str = Field(default="", max_length=200)
    aas_id: str = Field(default="", max_length=400)


class Mapping(Strict):
    node: str = Field(min_length=1, max_length=160)
    component_id: UUID


class ModelCreate(Strict):
    file_id: UUID
    template_id: UUID
    mappings: list[Mapping] = Field(min_length=1, max_length=100)
    unit: Literal["m", "mm", "cm"]
    meters_per_unit: Number = Field(gt=0, le=1000)
    frame: Literal["right-handed-y-up"] = "right-handed-y-up"
    transform: list[Number] = Field(
        default=[1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1], min_length=16, max_length=16
    )
    provenance: str = Field(min_length=1, max_length=1000)


class AssetChange(Strict):
    expected_revision: int = Field(ge=1)
    stage: Literal["identity", "model", "mapping", "documents", "signals", "preview", "active"]
    model_id: UUID | None = None


class DocumentLink(Strict):
    document_id: UUID
    component_id: UUID | None = None


class Binding(Strict):
    tag: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    component_id: UUID
    external_component_id: str = Field(default="", max_length=160)
    metric: Literal["temperature", "vibration", "pressure", "rpm", "power", "humidity"]
    unit: Literal["Cel", "K", "mm/s", "m/s", "bar", "Pa", "rpm", "W", "%"]
    sample_seconds: int = Field(default=10, ge=1, le=86400)
    stale_seconds: int = Field(default=60, ge=2, le=604800)
    high: Number | None = None
    hysteresis: Number = Field(default=0, ge=0)

    @model_validator(mode="after")
    def units(self) -> Self:
        valid = {
            "temperature": {"Cel", "K"},
            "vibration": {"mm/s", "m/s"},
            "pressure": {"bar", "Pa"},
            "rpm": {"rpm"},
            "power": {"W"},
            "humidity": {"%"},
        }
        if self.unit not in valid[self.metric] or self.stale_seconds < self.sample_seconds:
            raise ValueError("Incompatible engineering unit or sampling policy")
        return self


class SourceCreate(Strict):
    name: Text
    mode: Literal["live", "simulated"]
    external_system: str = Field(default="manual", min_length=1, max_length=80)
    external_asset_id: str = Field(default="", max_length=160)
    bindings: list[Binding] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def tags(self) -> Self:
        if len({b.tag for b in self.bindings}) != len(self.bindings):
            raise ValueError("Duplicate tag binding")
        return self


class Sample(Strict):
    message_id: str = Field(min_length=1, max_length=160)
    tag: str = Field(min_length=1, max_length=80)
    value: Number
    unit: str = Field(min_length=1, max_length=24)
    observed_at: Instant
    quality: Literal["good", "bad", "unknown"] = "good"


class Batch(Strict):
    mode: Mode
    samples: list[Sample] = Field(min_length=1, max_length=100)


class TimeWindow(Strict):
    start: Instant
    end: Instant
    mode: Mode = "simulated"

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if not timedelta(0) < self.end - self.start <= timedelta(days=7):
            raise ValueError("History window must be positive and at most seven days")
        return self


class ToolRequest(TimeWindow):
    component_id: UUID
    question: str = Field(default="Inspect this equipment", min_length=1, max_length=2000)
    use_model: bool = False


class ViewerAction(Strict):
    action: Literal["focus_component", "highlight_components"]
    component_ids: list[UUID] = Field(min_length=1, max_length=20)


class NoteCreate(Strict):
    kind: Literal["annotation", "viewpoint"]
    component_id: UUID
    text: str = Field(default="", max_length=2000)
    camera: list[Number] | None = Field(default=None, min_length=6, max_length=6)

    @model_validator(mode="after")
    def content(self) -> Self:
        if (self.kind == "viewpoint" and self.camera is None) or (
            self.kind == "annotation" and not self.text.strip()
        ):
            raise ValueError("A viewpoint needs a camera; an annotation needs text")
        return self


class ImportCommit(Strict):
    name: Text
    serial: Text
    geometry_file_id: UUID | None = None
    include_documents: bool = False


class Identifier(Strict):
    id: UUID


class Simulation(Strict):
    component_id: UUID
    scenario: Literal["cycle", "normal", "alarm", "recovery", "disconnect"] = "cycle"
