"""Runtime-validated public response shapes shared with generated browser contracts."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, JsonValue

from app.schemas import Strict


class DocumentMetadata(Strict):
    id: UUID
    title: str
    media_type: str
    embedding_version: str
    created_at: datetime


class DocumentDetail(DocumentMetadata):
    text: str


class DocumentList(Strict):
    next_cursor: str | None = None
    items: list[DocumentMetadata]
    limit: int
    offset: int


class KnowledgeSource(Strict):
    document_id: UUID
    title: str
    chunk: int = Field(ge=0)
    text: str
    distance: float = Field(allow_inf_nan=False)
    embedding_version: str


class KnowledgeResults(Strict):
    sources: list[KnowledgeSource]
    backend: Literal["lexical", "http", "cloudflare"]


class CompletedToolStep(Strict):
    tool: str
    status: Literal["completed"]
    result: dict[str, JsonValue]


class FailedToolStep(Strict):
    status: Literal["failed"]
    error: str


class AgentRunOut(Strict):
    id: UUID
    goal: str
    status: Literal["running", "completed", "failed", "cancelled"]
    steps: list[Annotated[CompletedToolStep | FailedToolStep, Field(discriminator="status")]]
    created_at: datetime


class AgentRunList(Strict):
    next_cursor: str | None = None
    items: list[AgentRunOut]


class ToolDescriptor(Strict):
    name: str
    schema_: dict[str, JsonValue] = Field(alias="schema")
    effect: Literal["local computation", "read-only owned evidence"]


class ToolList(Strict):
    items: list[ToolDescriptor]


class Activity(Strict):
    title: str = Field(min_length=1, max_length=200)
    notes: str = Field(min_length=1, max_length=2000)


class Day(Strict):
    day: int = Field(ge=1, le=14)
    activities: list[Activity] = Field(min_length=1, max_length=8)


class Itinerary(Strict):
    days: list[Day] = Field(min_length=1, max_length=14)
    assumptions: list[str] = Field(max_length=20)


class UnavailableTravelProvider(Strict):
    provider: Literal["weather", "maps", "flights", "accommodation", "places", "transport"]
    status: Literal["unavailable"]
    verified: Literal[False]


class PlannedItinerary(Itinerary):
    providers: list[UnavailableTravelProvider]
    backend: Literal["mock", "ollama", "vllm", "cloudflare"]


class TripOut(Strict):
    id: UUID
    destination: str
    duration: int
    budget: float = Field(allow_inf_nan=False)
    currency: str
    preferences: str
    revision: int
    itinerary: PlannedItinerary
    created_at: datetime
    updated_at: datetime
    live_data_verified: Literal[False]
    notice: str


class TripList(Strict):
    next_cursor: str | None = None
    items: list[TripOut]


class ModelOut(Strict):
    id: Literal["default"]
    name: str
    backend: Literal["mock", "ollama", "vllm", "cloudflare"]
    model_identifier: str
    context_tokens: int
    modalities: list[Literal["text", "vision", "speech"]]
    quantization: str | None
    revision: str | None
    real_inference: bool


class ModelList(Strict):
    items: list[ModelOut]
