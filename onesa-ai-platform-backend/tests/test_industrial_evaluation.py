"""The versioned evaluator retains frozen expectations and honest scoring categories."""

import asyncio
import importlib.util
from pathlib import Path


def test_versioned_holdout_and_semantic_limit_are_explicit():
    path = Path(__file__).resolve().parents[2] / "scripts/evaluate_industrial.py"
    spec = importlib.util.spec_from_file_location("industrial_evaluation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = asyncio.run(module.evaluate())
    assert result["sample_size"] >= 30 and result["result"] == "PASS"
    assert result["splits"]["development"] and result["splits"]["held_out"]
    assert len({case["id"] for case in result["cases"]}) == result["sample_size"]
    assert result["real_model_calls"] == 0
    assert result["cost_per_useful_completed_task"] is None
    assert result["human_rated_support"]["status"] == "NOT_RUN"
    assert result["import_evaluation"]["result"] == "PASS"
    assert result["import_evaluation"]["sample_size"] == 14
    assert result["import_evaluation"]["split"] == "visible_held_out_regression"
    unsupported = next(case for case in result["cases"] if case["id"] == "unsupported-causal-claim")
    assert unsupported["observed"]["source_validation"] == "accepted_requires_human"
    assert unsupported["human_support_rating"] is None


def test_import_downstream_failure_is_not_input_rejection(monkeypatch):
    import json

    path = Path(__file__).resolve().parents[2] / "scripts/evaluate_industrial.py"
    spec = importlib.util.spec_from_file_location("industrial_import_failure", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def unavailable(*args):
        raise ValueError("private-error-marker")

    monkeypatch.setattr(module, "calculate", unavailable)
    result = module.evaluate_imports()
    assert result["result"] == "FAIL"
    valid = result["cases"][0]
    assert valid["pass"] is False
    assert valid["observed"] == {"input_rejected": False, "failure": "downstream_evaluation_error"}
    assert "private-error-marker" not in json.dumps(result)


def test_changed_parent_expectations_fail_before_evaluation(tmp_path):
    import json

    import pytest

    path = Path(__file__).resolve().parents[2] / "scripts/evaluate_industrial.py"
    spec = importlib.util.spec_from_file_location("industrial_frozen_evaluation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    latest = json.loads(module.MANIFEST.read_text())
    manifest = tmp_path / module.MANIFEST.name
    manifest.write_text(json.dumps(latest))
    (tmp_path / latest["extends"]["file"]).write_text('{"changed": true}')
    module.MANIFEST = manifest
    with pytest.raises(ValueError, match="Frozen parent expectations changed"):
        asyncio.run(module.evaluate())
