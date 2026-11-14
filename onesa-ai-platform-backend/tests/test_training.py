import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from training.evaluate import evaluate
from training.pipeline import Example, check_config, prepare, verify_dataset


def sample(identifier: str, text: str) -> dict:
    return {
        "id": identifier,
        "language": "en",
        "messages": [
            {"role": "user", "content": text},
            {"role": "assistant", "content": "Example answer"},
        ],
        "source": "synthetic-test",
        "license": "test-only",
        "consent": True,
        "reviewed": True,
        "approved_for_training": False,
    }


def test_prepare_reproducible_splits_and_tamper_detection(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    source.write_text(
        "".join(json.dumps(sample(str(i), f"Question {i}")) + "\n" for i in range(10))
    )
    first = prepare(source, tmp_path / "first")
    second = prepare(source, tmp_path / "second")
    assert first == second and not first["approved_for_training"]
    assert verify_dataset(tmp_path / "first") == first
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "model_name": "/models/base",
                "model_revision": "immutable-test-revision",
                "dataset_dir": str(tmp_path / "first"),
                "output_dir": str(tmp_path / "run"),
            }
        )
    )
    assert check_config(config).method == "lora"
    (tmp_path / "first" / "train.jsonl").write_text("tampered")
    with pytest.raises(ValueError):
        verify_dataset(tmp_path / "first")


def test_reject_pii_duplicates_and_unreviewed_data(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        Example.model_validate(sample("pii", "Contact person@example.com"))
    row = sample("one", "Question")
    row["reviewed"] = False
    with pytest.raises(ValueError):
        Example.model_validate(row)
    source = tmp_path / "duplicates.jsonl"
    source.write_text("".join(json.dumps(sample(str(i), "Same question")) + "\n" for i in range(3)))
    with pytest.raises(ValueError):
        prepare(source, tmp_path / "bad")


def test_evaluation_case_alignment() -> None:
    cases = [{"id": "one", "language": "en", "required_terms": ["hello"]}]
    result = evaluate(cases, [{"id": "one", "response": "Hello there"}])
    assert result["by_language"]["en"]["mean"] == 1
    with pytest.raises(ValueError):
        evaluate(cases, [])


def test_training_execution_requires_approved_data(tmp_path: Path) -> None:
    import os
    import subprocess

    source = tmp_path / "source.jsonl"
    source.write_text("".join(json.dumps(sample(str(i), f"Question {i}")) + "\n" for i in range(3)))
    prepare(source, tmp_path / "prepared")
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "model_name": "/no-model",
                "model_revision": "immutable-test-revision",
                "dataset_dir": str(tmp_path / "prepared"),
                "output_dir": str(tmp_path / "run"),
            }
        )
    )
    result = subprocess.run(
        [sys.executable, "-m", "training.train", str(config), "--execute"],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "ONESA_ALLOW_TRAINING": "1"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "human-approved dataset" in result.stderr
    assert not (tmp_path / "run").exists()


def test_registry_records_hashes_and_refuses_overwrite(tmp_path: Path) -> None:
    from training.registry import Artifact, register

    adapter = tmp_path / "adapter"
    adapter.mkdir()
    (adapter / "adapter_config.json").write_text("{}")
    (adapter / "adapter_model.safetensors").write_bytes(b"synthetic-test-bytes-not-model-weights")
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"samples": 1, "method": "synthetic test fixture"}))
    config = tmp_path / "config.json"
    config.write_text("{}")
    metadata = Artifact(
        version="test-v1",
        base_model="test-base",
        base_revision="test-revision",
        dataset_version="a" * 64,
        adapter_path=str(adapter),
        training_config=str(config),
        evaluation_report=str(report),
    )
    target = register(metadata, tmp_path / "registry")
    record = json.loads(target.read_text())
    assert (
        record["status"] == "candidate" and record["artifact_sha256"]["adapter_model.safetensors"]
    )
    with pytest.raises(FileExistsError):
        register(metadata, tmp_path / "registry")


def test_extensible_languages_and_domains_preserve_existing_records(tmp_path: Path) -> None:
    languages = ["en", "DE-de", "fr", "es", "sn", "nd", "mixed", "ja", "zh-Hant-TW"]
    source = tmp_path / "international.jsonl"
    rows = []
    for index, language in enumerate(languages):
        row = sample(str(index), f"Distinct question {index}")
        row.update(language=language, domains=["engineering", "enterprise", "engineering"])
        normalized = Example.model_validate(row)
        assert normalized.language == language.lower()
        assert normalized.domains == ["engineering", "enterprise"]
        rows.append(row)
    source.write_text("".join(json.dumps(row) + "\n" for row in rows))
    manifest = prepare(source, tmp_path / "prepared")
    assert manifest["languages"] == sorted(language.lower() for language in languages)
    assert manifest["domains"] == ["engineering", "enterprise"]
    assert verify_dataset(tmp_path / "prepared") == manifest
    for invalid in ["", "de_DE", "<script>", "x" * 64]:
        with pytest.raises(ValueError):
            Example.model_validate({**rows[0], "language": invalid})


def test_baseline_comparison_detects_general_assistant_regression() -> None:
    from training.evaluate import compare

    cases = [
        {"id": "general", "language": "en", "required_terms": ["correct"]},
        {"id": "domain", "language": "de", "required_terms": ["technik"]},
    ]
    baseline = [{"id": "general", "response": "correct"}, {"id": "domain", "response": "unknown"}]
    candidate = [{"id": "general", "response": "unknown"}, {"id": "domain", "response": "Technik"}]
    report = compare(cases, candidate, baseline)
    assert report["regression_by_language"]["en"]["mean_delta"] == -1
    assert report["regression_by_language"]["de"]["mean_delta"] == 1
    assert report["human_review_required"] and not report["promotion_authorized"]
    with pytest.raises(ValueError):
        compare(cases, candidate, baseline[:-1])


def test_model_profiles_are_metadata_not_deployments() -> None:
    from training.registry import Artifact

    legacy = dict(
        version="test-v1",
        base_model="base",
        base_revision="revision",
        dataset_version="a" * 64,
        adapter_path="adapter",
        training_config="config",
        evaluation_report="evaluation",
    )
    assert Artifact(**legacy).languages == []
    for family in ["general", "enterprise", "industrial", "travel", "multilingual", "regional"]:
        artifact = Artifact(
            **legacy,
            family=family,
            purpose="Synthetic metadata fixture",
            languages=["de-DE", "fr", "sn"],
            domains=["manufacturing"],
            license="test-only",
            provenance="synthetic test, not a trained model",
        )
        assert artifact.family == family and artifact.deployment_status == "not_deployed"
        assert artifact.languages == ["de-de", "fr", "sn"]
    with pytest.raises(ValueError):
        Artifact(**legacy, deployment_status="deployed")
    with pytest.raises(ValueError):
        Artifact(**legacy, languages=["de_DE"])
