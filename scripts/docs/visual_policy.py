"""Validate classified visual navigation against maintained source and diagram files."""

import json
import re
from pathlib import Path


def validate_navigation(root: Path, catalog: list[dict]) -> dict:
    navigation = json.loads(
        (root / "docs/ecosystem/visual-navigation.json").read_text()
    )
    if navigation.get("classification") != "internal":
        raise ValueError("Engineering navigation must be internal")
    required_architecture = {
        "infrastructure-architecture",
        "company-portal-architecture",
        "system-overview",
        "monitoring-operations",
        "development-phases-roadmap",
        "privacy-governance",
        "ai-inference-rag-workflows",
        "robotics-ros-2-workflows",
        "backup-disaster-recovery",
        "ai-platform-architecture",
        "ai-robot-architecture",
        "ci-cd-deployment-pipeline",
        "data-flow-database-schemas",
        "authentication-authorization",
        "security-architecture",
        "complete-onesa-ecosystem",
        "portal-jobs-document-scanning",
    }
    architecture_ids = [entry.get("id") for entry in navigation.get("architecture", [])]
    if (
        not required_architecture.issubset(architecture_ids)
        or len(architecture_ids) != len(set(architecture_ids))
        or len(navigation.get("chapters", [])) != 17
    ):
        raise ValueError(
            "Required architecture and onboarding navigation is incomplete"
        )
    if [day["id"] for day in navigation.get("days", [])] != ["1", "2", "3", "4"]:
        raise ValueError("Four ordered engineering learning days are required")
    identifiers = {diagram["id"] for diagram in catalog}
    if len(identifiers) != len(catalog):
        raise ValueError("Duplicate diagram identity")
    for diagram in catalog:
        source = root / diagram["source"]
        if (
            not source.is_file()
            or source.is_symlink()
            or not source.resolve().is_relative_to(root / "docs/diagrams")
        ):
            raise ValueError("Diagram source must be a maintained regular definition")
        if not diagram.get("status"):
            raise ValueError("Every diagram needs an implementation status")
    for entry in (
        navigation["architecture"] + navigation["chapters"] + navigation["days"]
    ):
        if not re.fullmatch(r"/docs/[A-Za-z0-9_/-]+", entry["url"]):
            raise ValueError(
                "Engineering references must be local documentation routes"
            )
        source = root / (entry["url"].lstrip("/") + ".md")
        if not source.is_file() or source.is_symlink():
            raise ValueError("Navigation reference does not exist: " + entry["url"])
        if "diagram" in entry and entry["diagram"] not in identifiers:
            raise ValueError("Navigation references an unknown diagram")
    for day in navigation["days"]:
        if not all(day.get(key) for key in ["objectives", "checkpoints", "references"]):
            raise ValueError("Each learning day needs objectives, tasks and references")
        for reference in day["references"]:
            if not (root / (reference["url"].lstrip("/") + ".md")).is_file():
                raise ValueError("Learning reference does not exist")
    return navigation
