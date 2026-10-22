"""Versioned, original synthetic evidence; calculations never depend on model text."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Self

from pydantic import AwareDatetime, Field, field_validator, model_validator

from app.schemas import Strict

FIXTURE_VERSION: Literal["onesa-industrial-synthetic-v1"] = "onesa-industrial-synthetic-v1"
ASSETS = {
    "demo-press-01": {"name": "Demonstration press", "equipment_type": "synthetic press"},
    "demo-conveyor-02": {"name": "Demonstration conveyor", "equipment_type": "synthetic conveyor"},
}
Scenario = Literal[
    "reference", "no_stops", "overlap", "boundary", "open_event", "stale", "conflict"
]


def checksum(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class Window(Strict):
    start: AwareDatetime
    end: AwareDatetime

    @field_validator("start", "end")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if not timedelta(0) < self.end - self.start <= timedelta(days=1):
            raise ValueError("Window must be positive and at most 24 hours")
        return self


class Event(Strict):
    id: str = Field(min_length=1, max_length=80)
    asset_id: str
    start: AwareDatetime
    end: AwareDatetime | None
    kind: Literal["stop"] = "stop"
    source: Literal["synthetic-event-log"] = "synthetic-event-log"
    quality: Literal["good", "unknown", "bad"] = "good"
    version: Literal["1"] = "1"

    @field_validator("start", "end")
    @classmethod
    def utc(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(UTC) if value is not None else None

    @model_validator(mode="after")
    def interval(self) -> Self:
        if self.end is not None and self.end <= self.start:
            raise ValueError("Invalid event interval")
        return self


class Signal(Strict):
    id: str
    asset_id: str
    signal: Literal["pressure", "temperature"]
    unit: Literal["bar", "degC"]
    timestamp: AwareDatetime
    value: float = Field(allow_inf_nan=False)
    sample_seconds: int = Field(ge=1, le=3600)
    freshness_seconds: int = Field(ge=1, le=86400)
    quality: Literal["good", "unknown", "bad"] = "good"
    source: Literal["synthetic-sensors"] = "synthetic-sensors"
    version: Literal["1"] = "1"

    @field_validator("timestamp")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def units(self) -> Self:
        if (self.signal, self.unit) not in {("pressure", "bar"), ("temperature", "degC")}:
            raise ValueError("Incompatible unit; no implicit conversion")
        return self


class Reference(Strict):
    id: str
    version: str
    asset_id: str
    anchor: str
    title: str
    text: str = Field(max_length=4000)
    rights: Literal["Onesa original synthetic reference"] = "Onesa original synthetic reference"
    effective_start: AwareDatetime
    effective_end: AwareDatetime
    superseded: bool = False
    sha256: str

    @model_validator(mode="after")
    def provenance(self) -> Self:
        if self.sha256 != hashlib.sha256(self.text.encode()).hexdigest():
            raise ValueError("Reference hash mismatch")
        if self.effective_end <= self.effective_start:
            raise ValueError("Invalid reference dates")
        return self


class Evidence(Strict):
    fixture_version: Literal["onesa-industrial-synthetic-v1"] = FIXTURE_VERSION
    asset_id: str
    metadata_version: Literal["1"] = "1"
    events: list[Event] = Field(max_length=500)
    signals: list[Signal] = Field(max_length=500)
    references: list[Reference] = Field(max_length=20)

    @model_validator(mode="after")
    def boundary(self) -> Self:
        if (
            self.asset_id not in ASSETS
            or any(item.asset_id != self.asset_id for item in self.events)
            or any(item.asset_id != self.asset_id for item in self.signals)
            or any(item.asset_id != self.asset_id for item in self.references)
        ):
            raise ValueError("Evidence asset boundary mismatch")
        return self


def calculate(evidence: Evidence, window: Window) -> dict[str, Any]:
    """Intersect [start,end), dedupe IDs, union known good intervals; never fill gaps."""
    seen: dict[str, dict[str, Any]] = {}
    intervals: list[tuple[datetime, datetime, str]] = []
    timeline, incomplete, excluded = [], [], []
    for event in evidence.events:
        value = event.model_dump(mode="json")
        if event.id in seen:
            if seen[event.id] != value:
                raise ValueError("Conflicting duplicate event ID")
            continue
        seen[event.id] = value
        if event.start >= window.end or (event.end is not None and event.end <= window.start):
            continue
        if event.end is None:
            incomplete.append(event.id)
        elif event.quality != "good":
            excluded.append(event.id)
        else:
            start, end = max(event.start, window.start), min(event.end, window.end)
            intervals.append((start, end, event.id))
            timeline.append(
                {**value, "clipped_start": start.isoformat(), "clipped_end": end.isoformat()}
            )
    episodes: list[dict[str, Any]] = []
    for start, end, identifier in sorted(intervals):
        if episodes and start <= episodes[-1]["end"]:
            episodes[-1]["end"] = max(episodes[-1]["end"], end)
            episodes[-1]["event_ids"].append(identifier)
        else:
            episodes.append({"start": start, "end": end, "event_ids": [identifier]})
    seconds = sum((episode["end"] - episode["start"]).total_seconds() for episode in episodes)
    return {
        # Creation requests subclass Window; identity/selection fields are not
        # calculation inputs and must not alter preview-versus-saved facts.
        "window": window.model_dump(mode="json", include={"start", "end"}),
        "event_count": len(intervals) + len(incomplete) + len(excluded),
        "known_stop_events": len(intervals),
        "distinct_downtime_episodes": len(episodes),
        "known_downtime_seconds": seconds,
        "incomplete_event_ids": incomplete,
        "excluded_quality_event_ids": excluded,
        "downtime_complete": not incomplete and not excluded,
        "timeline": sorted(timeline, key=lambda event: event["clipped_start"]),
        "episodes": [
            {**item, "start": item["start"].isoformat(), "end": item["end"].isoformat()}
            for item in episodes
        ],
        "cause": "not_established",
        "availability": None,
        "oee": None,
    }


def coverage(evidence: Evidence, window: Window) -> dict[str, Any]:
    stale, usable, excluded = [], [], []
    for signal in evidence.signals:
        if not window.start <= signal.timestamp < window.end or signal.quality != "good":
            excluded.append(signal.id)
        elif (window.end - signal.timestamp).total_seconds() > signal.freshness_seconds:
            stale.append(signal.id)
        else:
            usable.append(signal.id)
    current = [
        ref
        for ref in evidence.references
        if not ref.superseded
        and ref.effective_start <= window.start
        and ref.effective_end >= window.end
    ]
    conflicts = len({ref.text for ref in current if ref.anchor == "pressure-review"}) > 1
    return {
        "usable_signal_ids": usable,
        "stale_signal_ids": stale,
        "excluded_signal_ids": excluded,
        "reference_conflict": conflicts,
        "permitted_reference_keys": [f"{ref.id}:{ref.version}:{ref.anchor}" for ref in current],
        "missing": [
            name
            for name, absent in [
                ("fresh signal coverage", not usable),
                ("applicable current reference", not current),
            ]
            if absent
        ],
        "signal_coverage": "Sparse synthetic samples; not continuous shift coverage",
    }


def fixture(asset_id: str, scenario: Scenario) -> Evidence:
    if asset_id not in ASSETS:
        raise ValueError("Unknown authorized demo asset")

    def at(time: str) -> datetime:
        return datetime.fromisoformat("2026-10-20T" + time + "+00:00")

    events = [
        Event(id=f"stop-{i}", asset_id=asset_id, start=at(start), end=at(end))
        for i, (start, end) in enumerate(
            [("09:12:00", "09:16:00"), ("09:31:00", "09:34:00"), ("09:48:00", "09:53:00")], 1
        )
    ]
    if scenario == "no_stops":
        events = []
    elif scenario == "overlap":
        events.append(
            Event(id="overlap", asset_id=asset_id, start=at("09:14:00"), end=at("09:18:00"))
        )
    elif scenario == "boundary":
        events = [
            Event(id="cross-start", asset_id=asset_id, start=at("08:58:00"), end=at("09:02:00")),
            Event(id="at-end", asset_id=asset_id, start=at("10:00:00"), end=at("10:02:00")),
        ]
    elif scenario == "open_event":
        events.append(Event(id="open", asset_id=asset_id, start=at("09:58:00"), end=None))
    text = (
        "Original synthetic training reference, not an equipment service manual. "
        "A pressure reading below 4 bar is an observation to compare with recorded stops. "
        "Sparse samples do not establish a causal link. A qualified person should review "
        "timestamp alignment, sensor quality and the actual equipment documentation "
        "before any action."
    )
    reference = Reference(
        id=f"{asset_id}-reference",
        version="1",
        asset_id=asset_id,
        anchor="pressure-review",
        title="Synthetic evidence review notes",
        text=text,
        sha256=hashlib.sha256(text.encode()).hexdigest(),
        effective_start=at("00:00:00") - timedelta(days=300),
        effective_end=at("00:00:00") + timedelta(days=300),
    )
    references = [reference]
    if scenario == "conflict":
        other = (
            "Conflicting synthetic reference: the review threshold is 6 bar. "
            "Resolve version authority first."
        )
        references.append(
            reference.model_copy(
                update={
                    "version": "2",
                    "text": other,
                    "sha256": hashlib.sha256(other.encode()).hexdigest(),
                }
            )
        )
    return Evidence(
        asset_id=asset_id,
        events=events,
        references=references,
        signals=[
            Signal(
                id="pressure-1",
                asset_id=asset_id,
                signal="pressure",
                unit="bar",
                value=3.5,
                timestamp=at("09:15:00" if scenario == "stale" else "09:59:00"),
                sample_seconds=60,
                freshness_seconds=300,
            )
        ],
    )
