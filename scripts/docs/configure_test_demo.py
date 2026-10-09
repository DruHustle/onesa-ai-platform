"""Grant only the explicitly requested synthetic docs test account in private local config."""

import argparse
import json
import os
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--grant-test-demo", action="store_true", required=True)
    parser.parse_args()
    demo = json.loads((ROOT / "data/runtime/docs/demo.json").read_text())
    assert demo["email"] == "documentation-demo@example.com"
    identifier = str(UUID(demo["id"]))
    path = ROOT / ".env"
    lines = path.read_text().splitlines()
    key = "ONESA_DOCUMENTATION_ENGINEERING_USER_IDS="
    previous = next((line[len(key) :] for line in lines if line.startswith(key)), "[]")
    grants = json.loads(previous)
    if identifier not in grants:
        grants.append(identifier)
    lines = [line for line in lines if not line.startswith(key)]
    lines.append(key + json.dumps(grants, separators=(",", ":")))
    path.write_text("\n".join(lines) + "\n")
    os.chmod(path, 0o600)
    print("Configured the synthetic documentation test account; restart API to apply.")
