"""Offline source-identity regressions; no database, model or provider requests."""

import hashlib
from copy import deepcopy
from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.industrial_evidence import Evidence, Window, calculate, coverage, fixture

WINDOW = Window(start="2026-10-20T09:00:00Z", end="2026-10-20T10:00:00Z")


@pytest.mark.parametrize("field", ["value", "timestamp", "quality", "freshness_seconds"])
def test_conflicting_signal_identity_is_rejected(field):
    data = fixture("demo-press-01", "reference").model_dump()
    repeated = deepcopy(data["signals"][0])
    changes = {
        "value": 9.0,
        "timestamp": repeated["timestamp"] - timedelta(minutes=20),
        "quality": "bad",
        "freshness_seconds": 60,
    }
    repeated[field] = changes[field]
    data["signals"].append(repeated)
    with pytest.raises(ValidationError, match="Conflicting duplicate signal ID"):
        Evidence.model_validate(data)


@pytest.mark.parametrize("field", ["text", "title", "effective_end", "superseded"])
def test_conflicting_reference_identity_is_rejected(field):
    data = fixture("demo-press-01", "reference").model_dump()
    repeated = deepcopy(data["references"][0])
    changes = {
        "text": "Different original synthetic source text for the same citation key.",
        "title": "Different source title",
        "effective_end": repeated["effective_end"] - timedelta(days=1),
        "superseded": True,
    }
    repeated[field] = changes[field]
    if field == "text":
        # Both references have internally valid hashes. The ambiguity is their shared key.
        repeated["sha256"] = hashlib.sha256(repeated["text"].encode()).hexdigest()
    data["references"].append(repeated)
    with pytest.raises(ValidationError, match="Conflicting duplicate reference key"):
        Evidence.model_validate(data)


def test_exact_repeats_remain_valid_without_rewriting_the_snapshot():
    data = fixture("demo-press-01", "reference").model_dump(mode="json")
    data["signals"].append(deepcopy(data["signals"][0]))
    data["references"].append(deepcopy(data["references"][0]))
    snapshot = deepcopy(data)
    accepted = Evidence.model_validate(data)
    assert data == snapshot
    assert accepted.model_dump(mode="json") == snapshot
    assert calculate(accepted, WINDOW)["known_downtime_seconds"] == 720


@pytest.mark.parametrize("field,new_value", [("version", "2"), ("anchor", "other-section")])
def test_distinct_reference_versions_and_sections_remain_valid(field, new_value):
    data = fixture("demo-press-01", "reference").model_dump()
    additional = deepcopy(data["references"][0])
    additional[field] = new_value
    additional["text"] = "A distinct original synthetic reference, not equipment instructions."
    additional["sha256"] = hashlib.sha256(additional["text"].encode()).hexdigest()
    data["references"].append(additional)
    accepted = Evidence.model_validate(data)
    assert len(accepted.references) == 2
    keys = coverage(accepted, WINDOW)["permitted_reference_keys"]
    assert len(set(keys)) == 2


def test_equivalent_signal_timezone_is_not_a_conflicting_identity():
    data = fixture("demo-press-01", "reference").model_dump(mode="json")
    repeated = deepcopy(data["signals"][0])
    repeated["timestamp"] = "2026-10-20T11:59:00+02:00"
    data["signals"].append(repeated)
    accepted = Evidence.model_validate(data)
    assert accepted.signals[0].timestamp == accepted.signals[1].timestamp


@pytest.mark.parametrize("asset", ["demo-press-01", "demo-conveyor-02"])
@pytest.mark.parametrize(
    "scenario,seconds",
    [
        ("reference", 720),
        ("no_stops", 0),
        ("overlap", 840),
        ("boundary", 120),
        ("open_event", 720),
        ("stale", 720),
        ("conflict", 720),
    ],
)
def test_bundled_scenarios_preserve_facts_and_version_conflict(asset, scenario, seconds):
    evidence = fixture(asset, scenario)
    validated = Evidence.model_validate(evidence.model_dump(mode="json"))
    assert calculate(validated, WINDOW)["known_downtime_seconds"] == seconds
    assert coverage(validated, WINDOW)["reference_conflict"] is (scenario == "conflict")
