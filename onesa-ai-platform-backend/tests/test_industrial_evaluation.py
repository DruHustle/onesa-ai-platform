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
    unsupported = next(case for case in result["cases"] if case["id"] == "unsupported-causal-claim")
    assert unsupported["observed"]["source_validation"] == "accepted_requires_human"
    assert unsupported["human_support_rating"] is None
