"""The documentation package is the canonical version; API/model versions are separate."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def documentation_version(root=ROOT):
    return json.loads(
        (root / "onesa-ai-platform-frontend/apps/docs/package.json").read_text()
    )["version"]


def sync_release_summary(root=ROOT):
    path = root / "docs/public/release-notes.md"
    text, count = re.subn(
        r"(?s)(<!-- documentation-version:start -->).*?(<!-- documentation-version:end -->)",
        lambda m: (
            m[1]
            + "\nDocumentation: "
            + documentation_version(root)
            + ". API contract: /api/v1. Application and model revisions are independent.\n"
            + m[2]
        ),
        path.read_text(),
    )
    if count != 1:
        raise ValueError("Expected one generated documentation release summary")
    path.write_text(text)


def validate_identity(root=ROOT, *, generated=True, scope="all"):
    if scope not in {"all", "public", "internal"}:
        raise ValueError("Unknown documentation validation scope")
    scopes = ["public", "internal"] if scope == "all" else [scope]
    version = documentation_version(root)
    summary = (root / "docs/public/release-notes.md").read_text()
    current = summary.split("<!-- documentation-version:start -->", 1)[1].split(
        "<!-- documentation-version:end -->", 1
    )[0]
    if "Documentation: " + version + "." not in current:
        raise ValueError("Current release summary documentation version mismatch")
    if generated:
        app = root / "onesa-ai-platform-frontend/apps/docs"
        paths = [app / ".cache/authoritative/provenance.json"] + [
            app / f".generated/{publication_scope}/static/generated/provenance.json"
            for publication_scope in scopes
        ]
        for path in paths:
            if json.loads(path.read_text()).get("documentation_version") != version:
                raise ValueError(
                    "Generated documentation version mismatch: " + path.name
                )
        for publication_scope in scopes:
            site = app / f"build-{publication_scope}/index.html"
            if site.exists():
                footer = re.search(
                    r"<footer\b.*?</footer>", site.read_text(), re.DOTALL
                )
                if not footer or "Documentation v" + version not in footer[0]:
                    raise ValueError("Site footer documentation version mismatch")
            manuals = (
                app / f".generated/{publication_scope}/static/generated/manuals.json"
            )
            if manuals.exists() and any(
                x.get("version") != version for x in json.loads(manuals.read_text())
            ):
                raise ValueError("Export documentation version mismatch")
    return version
