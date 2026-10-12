"""Validate reviewed cross-project contract/schema snapshots without live services."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOTS = ROOT / "docs/ecosystem"


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
    print(
        "Pinned cross-project schemas, source identities and public Portal API boundary verified."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--portal")
    parser.add_argument("--robot")
    args = parser.parse_args()
    validate(args.portal, args.robot)
