"""Keep private release evidence out of all documentation site artifacts."""

from pathlib import Path

DENIED = {
    "release-audit",
    "private",
    "confidential",
    "corporate-records",
    "records",
    "secrets",
    "backups",
    "data",
}


def sources(root: Path) -> list[Path]:
    docs = root / "docs"
    return [
        file
        for file in sorted(docs.rglob("*.md"))
        if file.is_file()
        and not file.is_symlink()
        and not DENIED.intersection(file.relative_to(docs).parts)
    ]
