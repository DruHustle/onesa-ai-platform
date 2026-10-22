"""Prepare signed Ubuntu browser dependencies on disposable GitHub runners only."""

import json
import os
import platform
import re
import stat
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

NETWORK = (
    'Acquire::http::Timeout "20";\n'
    'Acquire::https::Timeout "20";\n'
    'Acquire::Retries "1";\n'
    'APT::Update::Error-Mode "any";\n'
)


def rewrite_sources(text, deb822=False):
    """Change only the observed Azure mirror URI; retain trust and suite fields."""
    changes = 0

    def replace(match):
        nonlocal changes
        value = match.group(0)
        uri = urlsplit(value)
        if uri.hostname != "azure.archive.ubuntu.com":
            return value
        if (
            uri.username
            or uri.password
            or uri.port
            or uri.query
            or uri.fragment
            or uri.path not in {"/ubuntu", "/ubuntu/"}
        ):
            raise ValueError("Unexpected Ubuntu mirror URI; no rewrite performed")
        changes += 1
        return "https://archive.ubuntu.com" + uri.path

    result = []
    field = ""
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("#"):
            result.append(line)
            continue
        if deb822:
            header = re.match(r"^([A-Za-z-]+):", line)
            if header:
                field = header.group(1).lower()
            elif not line.strip():
                field = ""
            active = field == "uris"
        else:
            active = bool(re.match(r"^\s*deb(?:-src)?\s", line))
        if active:
            content, marker, comment = line.partition("#")
            line = re.sub(r"https?://[^\s]+", replace, content) + marker + comment
        result.append(line)
    return "".join(result), changes


def regular(path):
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError("APT source aliases are not accepted")
    value = path.stat()
    if (
        not stat.S_ISREG(value.st_mode)
        or value.st_uid != os.geteuid()
        or value.st_mode & 0o022
        or value.st_size > 256 * 1024
    ):
        raise ValueError("Unexpected APT source custody")
    return value


def atomic(path, text, mode):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as file:
        pending = Path(file.name)
        try:
            os.fchmod(file.fileno(), mode)
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        except BaseException:
            pending.unlink(missing_ok=True)
            raise
    try:
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)


def prepare(root):
    apt = root / "etc/apt"
    parts = apt / "sources.list.d"
    files = ([apt / "sources.list"] if (apt / "sources.list").exists() else []) + [
        path for path in sorted(parts.iterdir()) if path.suffix in {".list", ".sources"}
    ]
    if not 1 <= len(files) <= 32:
        raise ValueError("Bounded existing APT source inventory required")
    replacements = []
    for path in files:
        before = regular(path)
        text = path.read_text()
        updated, count = rewrite_sources(text, path.suffix == ".sources")
        if count:
            replacements.append((path, updated, stat.S_IMODE(before.st_mode), count))
    config = apt / "apt.conf.d/99-onesa-ci-network"
    if config.exists():
        regular(config)
        if config.read_text() != NETWORK:
            raise ValueError("Preserve conflicting existing APT configuration")
    elif config.is_symlink() or any(p.is_symlink() for p in config.parents):
        raise ValueError("APT configuration aliases are not accepted")
    for path, updated, mode, _ in replacements:
        atomic(path, updated, mode)
    atomic(config, NETWORK, 0o644)
    return {
        "source_files_updated": len(replacements),
        "mirror_URIs_updated": sum(row[3] for row in replacements),
        "request_timeout_seconds": 20,
        "APT_file_retries": 1,
        "repository_update_errors": "fail",
        "signing_and_suite_fields_changed": False,
    }


def require_runner():
    if not (
        platform.system() == "Linux"
        and os.geteuid() == 0
        and os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"
        and os.environ.get("RUNNER_OS") == "Linux"
        and os.environ.get("GITHUB_REPOSITORY") == "DruHustle/onesa-ai-platform"
    ):
        raise ValueError("Only the disposable GitHub-hosted Linux CI runner is allowed")


if __name__ == "__main__":
    require_runner()
    print(json.dumps(prepare(Path("/"))))
