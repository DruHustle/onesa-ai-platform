"""Fault-injected evaluator scoring; doubles isolate the harness from provider/DB work."""

import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def evaluator(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[2] / "scripts/evaluate_industrial.py"
    spec = importlib.util.spec_from_file_location("industrial_evaluation_scoring", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    case = {
        "id": "scoring-control",
        "split": "held_out",
        "semantic_policy": "scoring-only",
        "expected": {
            "events": 3,
            "seconds": 720,
            "episodes": 3,
            "complete": True,
            "abstained": False,
        },
    }
    parent = tmp_path / "parent.json"
    parent.write_text(
        json.dumps({"version": "scoring-parent", "cases": [], "integration_cases": []})
    )
    manifest = tmp_path / "manifest.json"

    def select(**changes):
        manifest.write_text(
            json.dumps(
                {
                    "version": "scoring-control",
                    "extends": {
                        "file": parent.name,
                        "version": "scoring-parent",
                        "sha256": hashlib.sha256(parent.read_bytes()).hexdigest(),
                    },
                    "cases": [{**case, **changes}],
                }
            )
        )

    select()
    monkeypatch.setattr(module, "MANIFEST", manifest)
    # These fault injections exercise the original scoring boundary only. The
    # independent import suite has its own real-input and fault-injection cases.
    monkeypatch.setattr(
        module, "evaluate_imports", lambda: {"result": "PASS", "scope": "unit double"}
    )
    monkeypatch.setattr(module, "Settings", lambda **kwargs: SimpleNamespace(**kwargs))
    record = SimpleNamespace(model_dump=lambda **kwargs: {})
    monkeypatch.setattr(module, "input_case", lambda case: {})
    monkeypatch.setattr(module, "Evidence", SimpleNamespace(model_validate=lambda value: record))
    monkeypatch.setattr(module, "Window", SimpleNamespace(model_validate=lambda value: record))
    monkeypatch.setattr(
        module,
        "calculate",
        lambda *args: {
            "event_count": 3,
            "known_downtime_seconds": 720,
            "distinct_downtime_episodes": 3,
            "downtime_complete": True,
        },
    )
    monkeypatch.setattr(module, "coverage", lambda *args: {})
    monkeypatch.setattr(module, "checksum", lambda *args: "synthetic-control")
    calls = []

    async def generation(*args):
        calls.append(True)
        return {"abstained": False, "hypotheses": []}, {"mode": "mock"}

    monkeypatch.setattr(module, "explain", generation)
    return module, select, calls


def test_missing_input_rejection_fails_before_generation(evaluator):
    module, select, calls = evaluator
    select(reject=True)
    result = asyncio.run(module.evaluate())
    assert result["result"] == "FAIL"
    assert not calls
    assert result["cases"][0]["observed"] == {
        "input_rejected": False,
        "failure": "expected_input_rejection_missing",
    }


@pytest.mark.parametrize("layer", ["coverage", "explain", "checksum"])
def test_downstream_failure_cannot_rescue_a_missed_input_rejection(evaluator, monkeypatch, layer):
    module, select, calls = evaluator
    select(reject=True)

    def rejected(*args):
        calls.append(layer)
        raise ValueError("private-error-marker")

    async def rejected_generation(*args):
        return rejected(*args)

    monkeypatch.setattr(module, layer, rejected_generation if layer == "explain" else rejected)
    result = asyncio.run(module.evaluate())
    assert result["result"] == "FAIL"
    assert not calls
    assert result["cases"][0]["observed"]["input_rejected"] is False
    assert "private-error-marker" not in json.dumps(result)


@pytest.mark.parametrize("expected_rejection", [True, False])
@pytest.mark.parametrize("layer", ["Evidence", "Window", "calculate"])
def test_actual_input_rejection_is_scored_at_its_boundary(
    evaluator, monkeypatch, layer, expected_rejection
):
    module, select, calls = evaluator
    select(reject=expected_rejection)

    def rejected(*args):
        raise ValueError("synthetic-input-rejection")

    monkeypatch.setattr(
        module,
        layer,
        rejected if layer == "calculate" else SimpleNamespace(model_validate=rejected),
    )
    result = asyncio.run(module.evaluate())
    assert result["result"] == ("PASS" if expected_rejection else "FAIL")
    assert result["cases"][0]["observed"]["input_rejected"] is True
    assert not calls


def test_fixture_construction_error_is_not_expected_input_rejection(evaluator, monkeypatch):
    module, select, _ = evaluator
    select(reject=True)

    def malformed_fixture(*args):
        raise ValueError("fixture-construction-failed")

    monkeypatch.setattr(module, "input_case", malformed_fixture)
    with pytest.raises(ValueError, match="fixture-construction-failed"):
        asyncio.run(module.evaluate())


def test_downstream_failure_for_valid_input_is_reported_as_downstream(evaluator, monkeypatch):
    module, _, _ = evaluator

    async def unavailable(*args):
        raise ValueError("private-error-marker")

    monkeypatch.setattr(module, "explain", unavailable)
    result = asyncio.run(module.evaluate())
    assert result["result"] == "FAIL"
    assert result["cases"][0]["observed"] == {
        "input_rejected": False,
        "failure": "downstream_evaluation_error",
    }
    assert "private-error-marker" not in json.dumps(result)


def test_successful_valid_case_remains_successful(evaluator):
    module, _, calls = evaluator
    result = asyncio.run(module.evaluate())
    assert result["result"] == "PASS" and len(calls) == 1
    assert result["cases"][0]["observed"]["seconds"] == 720
    assert result["real_model_calls"] == 0
    assert result["human_rated_support"]["status"] == "NOT_RUN"


@pytest.mark.parametrize(
    "xml,code,status",
    [
        (
            '<testsuites><testsuite><testcase name="ok"/></testsuite></testsuites>',
            0,
            "PASS",
        ),
        ("<testsuites><testsuite/></testsuites>", 0, "FAIL"),
        (
            '<testsuites><testsuite><testcase name="bad"><failure/>'
            "</testcase></testsuite></testsuites>",
            0,
            "FAIL",
        ),
        (
            '<testsuites><testsuite><testcase name="bad"><error/>'
            "</testcase></testsuite></testsuites>",
            0,
            "FAIL",
        ),
        (
            '<testsuites><testsuite><testcase name="skip"><skipped/>'
            "</testcase></testsuite></testsuites>",
            0,
            "FAIL",
        ),
        (
            '<testsuites><testsuite><testcase name="ok"/></testsuite></testsuites>',
            1,
            "FAIL",
        ),
    ],
)
def test_database_receipt_needs_nonempty_clean_results(evaluator, monkeypatch, xml, code, status):
    module, _, _ = evaluator
    monkeypatch.setenv("ONESA_TEST_DATABASE_URL", "postgresql://localhost/scoring_test")

    def completed(command, **kwargs):
        receipt = next(
            value.split("=", 1)[1] for value in command if value.startswith("--junitxml=")
        )
        Path(receipt).write_text(xml)
        return SimpleNamespace(returncode=code)

    monkeypatch.setattr(module.subprocess, "run", completed)
    assert module.database_cases()["status"] == status
