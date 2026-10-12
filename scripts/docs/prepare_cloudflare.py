"""Prepare a harmless bootstrap or Access-wrapped Pages output; never upload."""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def prepare(output: Path, *, placeholder: bool = False):
    source = ROOT / "onesa-ai-platform-frontend/apps/docs/build-internal"
    output = output.resolve()
    if (
        output.exists()
        or output.is_relative_to(source.resolve())
        or source.resolve().is_relative_to(output)
    ):
        raise ValueError("New isolated private output directory required")
    if placeholder:
        output.mkdir(parents=True, mode=0o700)
        (output / "index.html").write_text(
            '<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta name="robots" content="noindex,nofollow,noarchive">'
            "<title>Onesa engineering documentation</title>"
            "<h1>Onesa engineering documentation</h1>"
            "<p>Documentation is not available yet.</p></html>\n"
        )
        (output / "_headers").write_text(
            "/*\n  Cache-Control: no-store\n"
            "  X-Robots-Tag: noindex, nofollow, noarchive\n"
            "  X-Content-Type-Options: nosniff\n"
            "  Referrer-Policy: no-referrer\n"
        )
        (output / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
        for file in output.iterdir():
            file.chmod(0o600)
        return {
            "prepared": True,
            "scope": "placeholder",
            "contains_engineering_content": False,
            "deployment_requested": False,
            "hosted_access_verified": False,
        }
    if source.is_symlink() or any(file.is_symlink() for file in source.rglob("*")):
        raise ValueError("Documentation build must not contain symlinks")
    provenance = json.loads((source / "generated/provenance.json").read_text())
    if provenance.get("classification") != "internal":
        raise ValueError("Classified internal build required")
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    if provenance.get("revision") != revision:
        raise ValueError(
            "Internal build revision is stale; rebuild the reviewed current source"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, output)
    output.chmod(0o700)
    shutil.copyfile(ROOT / "infra/cloudflare-docs/worker.mjs", output / "_worker.js")
    (output / "_routes.json").write_text(
        json.dumps({"version": 1, "include": ["/*"], "exclude": []})
    )
    (output / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
    for file in output.rglob("*"):
        if file.is_file():
            file.chmod(0o600)
    return {
        "prepared": True,
        "scope": "internal",
        "deployment_requested": False,
        "hosted_access_verified": False,
        "required_owner_controls": [
            "Access policies for origin/previews/custom hostname",
            "Pages Functions fail closed",
            "approved engineering identities",
            "all server-side Access bindings",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--placeholder",
        action="store_true",
        help="Create only a harmless placeholder for configuring Access before uploading docs",
    )
    args = parser.parse_args()
    previous = os.umask(0o077)
    try:
        print(json.dumps(prepare(args.output, placeholder=args.placeholder), indent=2))
    finally:
        os.umask(previous)


if __name__ == "__main__":
    main()
