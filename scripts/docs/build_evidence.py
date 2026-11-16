"""Upload local public checks separately from owner-run hosted evidence."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "release"))
import evidence as e
import free_gate as gate
import oracle_docs_build as builds


def checkout_source(environment, git):
    """Observe the exact canonical main checkout; no caller-selected source file."""
    repository = builds.owner.CONSOLIDATED_REPOSITORY
    sha = environment.get("GITHUB_SHA", "")
    e.require(
        environment.get("GITHUB_REPOSITORY") == repository
        and environment.get("GITHUB_REPOSITORY_ID")
        == str(builds.owner.CONSOLIDATED_REPOSITORY_ID)
        and environment.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
        and environment.get("GITHUB_REF") == "refs/heads/main"
        and environment.get("GITHUB_ACTOR") == e.OWNER
        and environment.get("GITHUB_TRIGGERING_ACTOR") == e.OWNER
        and environment.get("GITHUB_RUN_ATTEMPT") == "1"
        and environment.get("GITHUB_WORKFLOW_SHA") == sha
        and environment.get("GITHUB_WORKFLOW_REF")
        == repository + "/" + builds.CANONICAL_WORKFLOW + "@refs/heads/main",
        "Exact first-attempt canonical main Docs build required",
    )
    e.require(
        git("config", "--get", "remote.origin.url")
        in {
            "https://github.com/" + repository,
            "https://github.com/" + repository + ".git",
            "git@github.com:" + repository + ".git",
        }
        and git("rev-parse", "HEAD") == sha
        and not git("status", "--porcelain", "--untracked-files=normal"),
        "Clean canonical Docs checkout required",
    )
    source = {
        "schema_version": 2,
        "repository": repository,
        "repository_id": builds.owner.CONSOLIDATED_REPOSITORY_ID,
        "product": "platform",
        "source_path": "onesa-ai-platform",
        "candidate_commit": sha,
        "source_tree": git("rev-parse", sha + "^{tree}"),
        "product_source_tree": git("rev-parse", sha + ":onesa-ai-platform"),
        "branch": "main",
    }
    e.require(
        git("cat-file", "-t", source["product_source_tree"]) == "tree",
        "Exact Docs product tree required",
    )
    try:
        return builds.canonical_source(source)
    except builds.owner.Rejected as error:
        raise e.Rejected("Canonical Docs source identity refused") from error


def record(sha, run_id, checks, *, source=None):
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
    if source is not None:
        try:
            builds.canonical_source(source)
        except builds.owner.Rejected as error:
            raise e.Rejected("Canonical Docs source identity refused") from error
        e.require(
            source["candidate_commit"] == sha, "Docs check and source revisions differ"
        )
    return {
        "schema_version": 2 if source is not None else 1,
        "evidence_kind": "onesa-public-docs-local-build-checks",
        "repository": source["repository"] if source is not None else e.REPOSITORY,
        "candidate_commit": sha,
        "actions_build_run_id": run_id,
        "checks": checks,
        "checks_sha256": e.digest(checks),
        "hosted_qualification": False,
        "production_deployment_authorized": False,
        "application_deployment_authorized": False,
        "backend_deployment_authorized": False,
        **(
            {"source": source, "verification_only": True, "release_authorized": False}
            if source is not None
            else {}
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--production", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    consolidated = (
        os.environ.get("GITHUB_REPOSITORY") == builds.owner.CONSOLIDATED_REPOSITORY
    )
    e.require(
        (consolidated or os.environ.get("GITHUB_REPOSITORY") == e.REPOSITORY)
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
    source = None
    if consolidated:
        root = Path(__file__).resolve().parents[3]

        def git(*parts):
            return subprocess.check_output(
                [
                    "git",
                    "--no-replace-objects",
                    "--no-lazy-fetch",
                    "-C",
                    str(root),
                    *parts,
                ],
                text=True,
            ).strip()

        source = checkout_source(os.environ, git)
    value = record(
        os.environ["GITHUB_SHA"],
        int(os.environ["GITHUB_RUN_ID"]),
        checks,
        source=source,
    )
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    e.require(len(raw) <= 1024 * 1024, "Local Docs check artifact bound")
    with args.output.open("xb") as stream:
        stream.write(raw)


if __name__ == "__main__":
    main()
