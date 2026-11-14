"""Create a private, reproducible evidence index; never authorize a release."""

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

PRODUCTS = ("onesa-company-portal", "onesa-ai-platform", "onesa-ai-robot")


def git(root, *arguments):
    return subprocess.check_output(
        ["git", "-C", str(root), *arguments], text=True
    ).strip()


def project(root):
    if (
        root.is_symlink()
        or Path(git(root, "rev-parse", "--show-toplevel")).resolve() != root.resolve()
    ):
        raise ValueError("Independent expected repository required")
    files = git(root, "ls-files", "-z").split("\0")
    routes, workflows, inputs = [], [], []
    for name in sorted(filter(None, files)):
        path = root / name
        if path.is_symlink():
            continue
        if name.startswith(".github/workflows/") and name.endswith((".yml", ".yaml")):
            workflows.append(
                {
                    "source": name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
        if name.endswith("/page.tsx") and "/src/app/" in name:
            route = "/" + name.split("/src/app/", 1)[1].removesuffix("/page.tsx")
            if route == "/page.tsx":
                route = "/"
            routes.append(
                {
                    "pattern": route,
                    "source": name,
                    "dynamic": "[" in route,
                    "hosted_route_test": "NOT_ATTESTED_BY_SOURCE_DISCOVERY",
                }
            )
        if name.endswith("openapi.json") and "node_modules" not in name:
            contract = json.loads(path.read_text())
            operations = [
                {
                    "path": route,
                    "method": method.upper(),
                    "operation_id": operation.get("operationId"),
                    "test_status": "REQUIRES_MATCHED_EVIDENCE",
                }
                for route, definition in contract.get("paths", {}).items()
                for method, operation in definition.items()
                if method
                in {"get", "post", "put", "patch", "delete", "head", "options"}
            ]
            inputs.append(
                {
                    "source": name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "operations": operations,
                }
            )
    if root.name == "onesa-ai-robot":
        routes.append(
            {
                "pattern": "/",
                "source": "onesa-ai-robot-frontend/server.mjs",
                "dynamic": False,
                "states": ["login", "authenticated-operator", "stopped", "faulted"],
                "hosted_route_test": "REQUIRES_MATCHED_EVIDENCE",
            }
        )
    return {
        "repository": "DruHustle/" + root.name,
        "head_commit": git(root, "rev-parse", "HEAD"),
        "tree": git(root, "rev-parse", "HEAD^{tree}"),
        "branch": git(root, "branch", "--show-current"),
        "tracked_working_changes": bool(
            git(root, "status", "--porcelain", "--untracked-files=no")
        ),
        "frontend_routes": routes,
        "workflow_sources": workflows,
        "api_contracts": inputs,
    }


def artifacts(path, classification):
    if path.is_symlink():
        raise ValueError("Build symlink prohibited")
    provenance = json.loads((path / "generated/provenance.json").read_text())
    if provenance.get("classification") != classification:
        raise ValueError("Build classification mismatch")
    pages = []
    for file in sorted(path.rglob("*.html")):
        if file.is_symlink():
            raise ValueError("Artifact symlink prohibited")
        relative = file.relative_to(path).as_posix()
        pages.append(
            {
                "path": "/"
                if relative == "index.html"
                else "/" + relative.removesuffix(".html"),
                "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                "hosted_test_status": "NOT_INFERRED_FROM_BUILD",
            }
        )
    return {
        "classification": classification,
        "revision": provenance["revision"],
        "pages": pages,
    }


def build(workspace, output, public_build=None, internal_build=None):
    output = output.resolve()
    if output.exists() or any(
        output.is_relative_to(workspace / product)
        and "release-audit" not in output.parts
        for product in PRODUCTS
    ):
        raise ValueError("New restricted release-audit output required")
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "classification": "restricted-release-evidence",
        "independent_review_status": "PENDING_EXTERNAL_REVIEW",
        "package_status": "READY_FOR_INDEPENDENT_REVIEW",
        "authorizes_production": False,
        "projects": [project(workspace / product) for product in PRODUCTS],
        "documentation_builds": [],
        "assessment_limits": [
            "Discovery is not route coverage",
            "Build success is not hosted acceptance",
            "Local editable files are not approval authority",
            "External review and production gates require their own evidence",
        ],
    }
    for path, classification in [
        (public_build, "public"),
        (internal_build, "internal"),
    ]:
        if path:
            manifest["documentation_builds"].append(artifacts(path, classification))
    output.mkdir(parents=True, mode=0o700)
    target = output / "manifest.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n")
    target.chmod(0o600)
    index = output / "SHA256SUMS"
    index.write_text(
        hashlib.sha256(target.read_bytes()).hexdigest() + "  manifest.json\n"
    )
    index.chmod(0o600)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--public-build", type=Path)
    parser.add_argument("--internal-build", type=Path)
    args = parser.parse_args()
    previous = os.umask(0o077)
    try:
        result = build(
            args.workspace.resolve(),
            args.output,
            args.public_build,
            args.internal_build,
        )
        print(
            json.dumps(
                {
                    "package_status": result["package_status"],
                    "independent_review_status": result["independent_review_status"],
                    "projects": len(result["projects"]),
                    "authorizes_production": False,
                }
            )
        )
    finally:
        os.umask(previous)


if __name__ == "__main__":
    main()
