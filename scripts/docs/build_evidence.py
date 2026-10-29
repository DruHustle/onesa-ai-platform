"""Upload local public checks separately from owner-run hosted evidence."""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "release"))
import evidence as e
import free_gate as gate


def record(sha, run_id, checks):
    e.require(
        len(sha) == 40
        and all(c in "0123456789abcdef" for c in sha)
        and type(run_id) is int
        and run_id > 0
        and checks.keys() == {"staging", "production"},
        "Exact local Docs build source/run required",
    )
    for environment, check in checks.items():
        e.require(
            check.get("result") == "PASS"
            and check.get("environment_context") == environment
            and check.get("provenance")
            == {"revision": sha, "classification": "public"},
            "Successful source-bound local public Docs checks required",
        )
        gate.docs_acceptance_schema(check)
    return {
        "schema_version": 1,
        "evidence_kind": "onesa-public-docs-local-build-checks",
        "repository": e.REPOSITORY,
        "candidate_commit": sha,
        "actions_build_run_id": run_id,
        "checks": checks,
        "checks_sha256": e.digest(checks),
        "hosted_qualification": False,
        "production_deployment_authorized": False,
        "application_deployment_authorized": False,
        "backend_deployment_authorized": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--production", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    e.require(
        os.environ.get("GITHUB_REPOSITORY") == e.REPOSITORY
        and os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
        and os.environ.get("GITHUB_ACTOR") == e.OWNER,
        "Owner-dispatched credential-free Docs build required",
    )
    checks = {}
    for environment in ["staging", "production"]:
        file = getattr(args, environment)
        e.require(
            file.is_file()
            and not file.is_symlink()
            and file.stat().st_size <= 512 * 1024,
            "Bounded local Docs check file required",
        )
        checks[environment] = json.loads(file.read_bytes())
    value = record(os.environ["GITHUB_SHA"], int(os.environ["GITHUB_RUN_ID"]), checks)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    e.require(len(raw) <= 1024 * 1024, "Local Docs check artifact bound")
    with args.output.open("xb") as stream:
        stream.write(raw)


if __name__ == "__main__":
    main()
