"""Validate reviewed cross-project contract/schema snapshots without live services."""

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOTS = ROOT / "docs/ecosystem"


def validate_portal_diagrams(schema, diagrams):
    """Reject stale schema provenance, omitted tables and invented table entities."""
    digest = hashlib.sha256(schema.encode()).hexdigest()
    expected = set(
        re.findall(
            r"CREATE TABLE(?: IF NOT EXISTS)?\s+([a-z_]+)", schema, re.IGNORECASE
        )
    )
    covered = set()
    files = list(diagrams.glob("portal-database-*.mmd"))
    assert files and expected, "Portal schema/diagram sources missing"
    for file in files:
        text = file.read_text()
        assert text.startswith("%% Portal source schema SHA256: " + digest + "\n"), (
            "Portal ERD schema provenance is stale: " + file.name
        )
        covered.update(re.findall(r"^\s+([a-z_]+) \{$", text, re.MULTILINE))
    assert covered == expected, (
        "Portal ERD table coverage differs from pinned migrations"
    )


def validate(portal=None, robot=None):
    manifest = json.loads((SNAPSHOTS / "source-revisions.json").read_text())
    for name, folder in [("onesa-company-portal", portal), ("onesa-ai-robot", robot)]:
        record = manifest[name]
        assert len(record["commit"]) == 40
        if folder:
            folder = Path(folder)
            for source, expected in record["sources"].items():
                assert (
                    hashlib.sha256((folder / source).read_bytes()).hexdigest()
                    == expected
                ), f"{name} source drift: {source}; regenerate and review snapshots"
    integrity = json.loads((SNAPSHOTS / "snapshot-hashes.json").read_text())
    for source, digest in integrity.items():
        assert (
            hashlib.sha256((SNAPSHOTS / source).read_bytes()).hexdigest() == digest
        ), f"Cross-project snapshot drift: {source}"
    public = json.loads((SNAPSHOTS / "contracts/portal-public.json").read_text())
    assert public["paths"] and all(
        p.startswith("/api/v1/public/") for p in public["paths"]
    )
    assert not public.get("servers")
    assert not any(p.startswith("/api/v1/admin/") for p in public["paths"])
    validate_portal_diagrams(
        (SNAPSHOTS / "portal-schema.sql").read_text(), ROOT / "docs/diagrams"
    )
    print(
        "Pinned cross-project schemas, source identities and public Portal API boundary verified."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--portal")
    parser.add_argument("--robot")
    args = parser.parse_args()
    validate(args.portal, args.robot)
