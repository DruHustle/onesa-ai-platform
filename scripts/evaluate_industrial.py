"""Finite, network-free synthetic evaluation. Never a production or real-model claim."""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from fastapi import Request

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "onesa-ai-platform-backend")
)
from app.config import Settings
from app.industrial import explain
from app.industrial_evidence import (
    FIXTURE_VERSION,
    Window,
    calculate,
    checksum,
    coverage,
    fixture,
)


async def evaluate() -> dict:
    window = Window.model_validate(
        {"start": "2026-10-20T09:00:00Z", "end": "2026-10-20T10:00:00Z"}
    )
    # Explicitly override provider selectors even if the developer has real-model configuration.
    settings = Settings(
        model_backend="mock",
        embedding_backend="lexical",
        environment="test",
        model_name="onesa-industrial-mock-v1",
        model_revision="1",
        public_origin="http://127.0.0.1:18310",
        secure_cookies=False,
        mail_provider="disabled",
        registration_mode="open",
    )
    request = Request(
        {
            "type": "http",
            "app": SimpleNamespace(state=SimpleNamespace(settings=settings)),
        }
    )
    cases = [
        ("reference", 3, 720, 3, False),
        ("no_stops", 0, 0, 0, True),
        ("overlap", 4, 840, 3, False),
        ("boundary", 1, 120, 1, False),
        ("open_event", 4, 720, 3, True),
        ("stale", 3, 720, 3, True),
        ("conflict", 3, 720, 3, True),
    ]
    outcomes = []
    for scenario, event_count, seconds, episodes, abstained in cases:
        evidence = fixture("demo-press-01", scenario)
        started = time.perf_counter()
        facts = calculate(evidence, window)
        fact_ms = (time.perf_counter() - started) * 1000
        payload = {
            "selection": window.model_dump(mode="json"),
            "evidence": evidence.model_dump(mode="json"),
            "facts": facts,
            "coverage": coverage(evidence, window),
        }
        result, generation = await explain(request, payload)
        correct = (
            facts["event_count"],
            facts["known_downtime_seconds"],
            facts["distinct_downtime_episodes"],
            result["abstained"],
        ) == (event_count, seconds, episodes, abstained)
        outcomes.append(
            {
                "scenario": scenario,
                "snapshot_sha256": checksum(payload["evidence"]),
                "facts_exact": correct,
                "abstained": result["abstained"],
                "calculation_latency_ms": round(fact_ms, 3),
                "generation": generation,
                "validated_citations": sum(
                    len(h["citations"]) for h in result["hypotheses"]
                ),
            }
        )
    return {
        "fixture_version": FIXTURE_VERSION,
        "repetitions": 1,
        "sample_size": len(cases),
        "scope": "Finite deterministic facts and explicitly mock/abstention generation; no provider requests",
        "result": "PASS" if all(case["facts_exact"] for case in outcomes) else "FAIL",
        "cases": outcomes,
        "real_model_calls": 0,
        "citation_support": "All accepted citations resolve to an applicable version/anchor and literal source quote; semantic entailment is not universally guaranteed",
        "cost_per_completed_task": None,
        "cost_status": "NOT_OBSERVED",
        "manual_lookup_comparison": "NOT_RUN",
        "general_assistant_comparison": "NOT_RUN",
        "human_reviewer_corrections": "NOT_MEASURED",
        "ownership_negative_tests": "Recorded separately in tests/test_industrial.py; this evaluator does not test authorization",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = asyncio.run(evaluate())
    raw = json.dumps(report, indent=2) + "\n"
    if args.output:
        with args.output.open("x") as stream:
            stream.write(raw)
        args.output.chmod(0o600)
    else:
        print(raw)
    raise SystemExit(0 if report["result"] == "PASS" else 1)


if __name__ == "__main__":
    main()
