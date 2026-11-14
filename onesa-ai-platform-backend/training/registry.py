"""Immutable local model-artifact metadata; no deployment or promotion side effect."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Artifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str = Field(pattern=r"^[a-zA-Z0-9._-]+$")
    base_model: str = Field(min_length=1)
    base_revision: str = Field(min_length=1)
    dataset_version: str = Field(pattern=r"^[a-f0-9]{64}$")
    adapter_path: str
    training_config: str
    evaluation_report: str
    family: Literal["general", "enterprise", "industrial", "travel", "multilingual", "regional"] = (
        "general"
    )
    purpose: str | None = Field(default=None, min_length=1, max_length=2000)
    languages: list[str] = Field(default_factory=list, max_length=128)
    domains: list[str] = Field(default_factory=list, max_length=64)
    license: str | None = Field(default=None, min_length=1, max_length=2000)
    provenance: str | None = Field(default=None, min_length=1, max_length=4000)
    deployment_status: Literal["not_deployed"] = "not_deployed"
    status: str = Field(default="candidate", pattern=r"^candidate$")

    @field_validator("languages")
    @classmethod
    def language_tags(cls, values: list[str]) -> list[str]:
        import re

        if any(
            len(v) > 63 or not re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", v)
            for v in values
        ):
            raise ValueError("Invalid language tag")
        return sorted({value.lower() for value in values})

    @field_validator("domains")
    @classmethod
    def domain_labels(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 100 for value in values):
            raise ValueError("Invalid domain label")
        return sorted({value.strip() for value in values})


def register(metadata: Artifact, directory: Path) -> Path:
    if not Path(metadata.adapter_path).is_dir():
        raise ValueError("Adapter directory is missing")
    adapter = Path(metadata.adapter_path)
    if not (adapter / "adapter_config.json").is_file() or not list(
        adapter.glob("adapter_model*.safetensors")
    ):
        raise ValueError("A PEFT adapter config and safetensors weights are required")
    report = json.loads(Path(metadata.evaluation_report).read_text())
    if not report.get("samples"):
        raise ValueError("Evaluation report has no samples")
    if not Path(metadata.training_config).is_file():
        raise ValueError("Training config is missing")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{metadata.version}.json"
    hashes = {}
    for artifact in sorted(Path(metadata.adapter_path).rglob("*")):
        if artifact.is_symlink():
            raise ValueError("Artifact symlinks are not accepted")
        if artifact.is_file():
            digest = hashlib.sha256()
            with artifact.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            hashes[str(artifact.relative_to(metadata.adapter_path))] = digest.hexdigest()
    if not hashes:
        raise ValueError("Adapter directory is empty")
    with target.open("x") as file:
        file.write(
            json.dumps(
                {
                    **metadata.model_dump(),
                    "artifact_sha256": hashes,
                    "evaluation_results": report,
                    "evaluation_sha256": hashlib.sha256(
                        Path(metadata.evaluation_report).read_bytes()
                    ).hexdigest(),
                    "training_config_sha256": hashlib.sha256(
                        Path(metadata.training_config).read_bytes()
                    ).hexdigest(),
                },
                indent=2,
            )
            + "\n"
        )
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata", type=Path)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(register(Artifact.model_validate_json(args.metadata.read_text()), args.directory))


if __name__ == "__main__":
    main()
