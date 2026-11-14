"""CPU-safe provenance-aware preparation, configuration checks and artifact registry."""

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=32000)


class Example(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=100)
    language: str = Field(
        min_length=2, max_length=63, pattern=r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$"
    )
    domains: list[str] = Field(default_factory=list, max_length=32)
    messages: list[Turn] = Field(min_length=2, max_length=40)
    source: str = Field(min_length=1)
    license: str = Field(min_length=1)
    consent: bool
    reviewed: bool
    approved_for_training: bool = False

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str) -> str:
        # Extensible language tags; historical mixed/sn/nd records remain valid.
        return value.lower()

    @field_validator("domains")
    @classmethod
    def validate_domains(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 100 for value in values):
            raise ValueError("Domain labels must contain 1–100 characters")
        return sorted({value.strip() for value in values})

    @model_validator(mode="after")
    def validate_conversation(self) -> Self:
        turns = self.messages[1:] if self.messages[0].role == "system" else self.messages
        if not turns or turns[0].role != "user" or turns[-1].role != "assistant":
            raise ValueError("Training conversation must begin with user and end with assistant")
        for index, turn in enumerate(turns):
            if turn.role != ("user" if index % 2 == 0 else "assistant"):
                raise ValueError("User and assistant turns must alternate")
        if not self.consent or not self.reviewed:
            raise ValueError("Consent/provenance review is required")
        for turn in self.messages:
            turn.content = unicodedata.normalize("NFC", turn.content).strip()
            if not turn.content:
                raise ValueError("Empty content")
            if re.search(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}|(?:\+?\d[ -]?){10,}", turn.content):
                raise ValueError("Possible personal information requires redaction/review")
        if sum(len(turn.content) for turn in self.messages) > 96000:
            raise ValueError("Conversation exceeds text limit")
        return self


class TrainConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_name: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    dataset_dir: str
    output_dir: str
    method: Literal["lora", "qlora"] = "lora"
    rank: int = Field(default=16, ge=1, le=128)
    alpha: int = Field(default=32, ge=1, le=256)
    learning_rate: float = Field(default=0.0002, gt=0, le=0.01)
    max_length: int = Field(default=1024, ge=128, le=8192)
    max_steps: int = Field(default=100, ge=1, le=100000)
    seed: int = 42


def fingerprint(example: Example) -> str:
    payload = json.dumps(
        [turn.model_dump() for turn in example.messages],
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def prepare(source: Path, destination: Path, seed: int = 42) -> dict:
    if source.stat().st_size > 20 * 1024 * 1024:
        raise ValueError("Input limit is 20 MiB")
    examples = [
        Example.model_validate_json(line)
        for line in source.read_text().splitlines()
        if line.strip()
    ]
    if len(examples) < 3:
        raise ValueError("At least three distinct examples are required for nonempty splits")
    unique = {fingerprint(row): row for row in examples}
    if len(unique) != len(examples) or len({row.id for row in examples}) != len(examples):
        raise ValueError("Duplicate normalized content or IDs")
    ordered = sorted(
        examples,
        key=lambda row: hashlib.sha256(f"{seed}:{fingerprint(row)}".encode()).hexdigest(),
    )
    held = max(1, len(ordered) // 10)
    splits = {
        "test": ordered[:held],
        "validation": ordered[held : held * 2],
        "train": ordered[held * 2 :],
    }
    version = hashlib.sha256("".join(sorted(unique)).encode()).hexdigest()
    destination.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for name, rows in splits.items():
        content = "".join(row.model_dump_json() + "\n" for row in rows)
        (destination / f"{name}.jsonl").write_text(content)
        hashes[name] = hashlib.sha256(content.encode()).hexdigest()
    manifest = {
        "dataset_version": version,
        "seed": seed,
        "counts": {k: len(v) for k, v in splits.items()},
        "sha256": hashes,
        "languages": sorted({r.language for r in examples}),
        "domains": sorted({domain for row in examples for domain in row.domains}),
        "approved_for_training": all(r.approved_for_training for r in examples),
        "sources": sorted({r.source for r in examples}),
        "licenses": sorted({r.license for r in examples}),
        "pii_check": "Basic regex screen only; human review remains required",
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def verify_dataset(directory: Path) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text())
    contents = set()
    approved = True
    for split in ("train", "validation", "test"):
        data = (directory / f"{split}.jsonl").read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest["sha256"][split]:
            raise ValueError("Dataset content differs from manifest")
        rows = [
            Example.model_validate_json(line) for line in data.decode().splitlines() if line.strip()
        ]
        if len(rows) != manifest["counts"][split] or not rows:
            raise ValueError("Invalid split counts")
        for row in rows:
            approved = approved and row.approved_for_training
            key = fingerprint(row)
            if key in contents:
                raise ValueError("Data leakage between splits")
            contents.add(key)
    if (
        hashlib.sha256("".join(sorted(contents)).encode()).hexdigest()
        != manifest["dataset_version"]
    ):
        raise ValueError("Dataset version mismatch")
    if bool(manifest["approved_for_training"]) != approved:
        raise ValueError("Training approval does not match dataset records")
    return manifest


def check_config(path: Path, allow_existing_output: bool = False) -> TrainConfig:
    config = TrainConfig.model_validate_json(path.read_text())
    if config.model_revision == "main":
        raise ValueError("Pin an immutable model revision or use a versioned local artifact")
    verify_dataset(Path(config.dataset_dir))
    if Path(config.output_dir).exists() and not allow_existing_output:
        raise ValueError("Use a new output directory to preserve previous experiments")
    return config


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("source", type=Path)
    prep.add_argument("destination", type=Path)
    config = commands.add_parser("check-config")
    config.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        print(json.dumps(prepare(args.source, args.destination), indent=2))
    else:
        print(check_config(args.path).model_dump_json(indent=2))


if __name__ == "__main__":
    main()
