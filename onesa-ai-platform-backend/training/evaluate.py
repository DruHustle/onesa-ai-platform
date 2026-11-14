"""CPU-safe held-out prediction evaluation; no claims of linguistic validation."""

import argparse
import json
from pathlib import Path


def evaluate(cases: list[dict], predictions: list[dict]) -> dict:
    case_ids = [row["id"] for row in cases]
    prediction_ids = [row["id"] for row in predictions]
    if len(set(case_ids)) != len(case_ids) or len(set(prediction_ids)) != len(prediction_ids):
        raise ValueError("Duplicate IDs")
    if set(case_ids) != set(prediction_ids) or not cases:
        raise ValueError("Predictions must match the held-out case set exactly")
    lookup = {row["id"]: row["response"] for row in predictions}
    scores = {}
    for case in cases:
        response = lookup[case["id"]]
        tokens = case["required_terms"]
        if not isinstance(response, str) or not tokens:
            raise ValueError("Each case requires terms and a text prediction")
        score = sum(term.casefold() in response.casefold() for term in tokens) / len(tokens)
        scores.setdefault(case["language"], []).append(score)
    return {
        "method": "required-term recall (limited proxy, not factual/safety assessment)",
        "samples": len(cases),
        "by_language": {k: {"samples": len(v), "mean": sum(v) / len(v)} for k, v in scores.items()},
        "human_review_required": True,
    }


def compare(cases: list[dict], predictions: list[dict], baseline: list[dict]) -> dict:
    candidate_report = evaluate(cases, predictions)
    baseline_report = evaluate(cases, baseline)
    candidate_report["baseline"] = baseline_report
    candidate_report["regression_by_language"] = {
        language: {
            "samples": score["samples"],
            "mean_delta": score["mean"] - baseline_report["by_language"][language]["mean"],
        }
        for language, score in candidate_report["by_language"].items()
    }
    candidate_report["promotion_authorized"] = False
    return candidate_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cases", type=Path)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Use a new report path")
    cases = [json.loads(row) for row in args.cases.read_text().splitlines()]
    predictions = [json.loads(row) for row in args.predictions.read_text().splitlines()]
    result = (
        compare(
            cases,
            predictions,
            [json.loads(row) for row in args.baseline.read_text().splitlines()],
        )
        if args.baseline
        else evaluate(cases, predictions)
    )
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
