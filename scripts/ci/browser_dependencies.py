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
ARCHIVE_LIST = "mirror+file:/etc/apt/apt-mirrors.txt"
UBUNTU_KEYRING = "/usr/share/keyrings/ubuntu-archive-keyring.gpg"


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
            if "mirror+" in content:
                raise ValueError(
                    "Archive indirection requires a validated Ubuntu stanza"
                )
            line = re.sub(r"https?://[^\s]+", replace, content) + marker + comment
        result.append(line)
    return "".join(result), changes


def deb822_fields(lines):
    """Read a bounded stanza without treating inline comments as legacy syntax."""
    fields = {}
    uri_lines = []
    current = None
    ambiguous = False
    for index, line in enumerate(lines):
        if not line.strip() or line.startswith("#"):
            continue
        header = re.fullmatch(
            r"([A-Za-z][A-Za-z0-9-]*):[ \t]*(.*)", line.rstrip("\r\n")
        )
        if header:
            current = header[1].lower()
            if current in fields:
                ambiguous = True
            fields.setdefault(current, []).append(header[2])
        elif line.startswith((" ", "\t")) and current is not None:
            fields[current].append(line.strip(" \t\r\n"))
        else:
            ambiguous = True
            current = None
        if current == "uris":
            uri_lines.append(index)
    return fields, uri_lines, ambiguous


def bounded_values(fields, name, allowed):
    values = " ".join(fields.get(name, [])).split()
    if not values or len(values) != len(set(values)) or not set(values) <= allowed:
        raise ValueError("Unexpected Ubuntu archive field")
    return set(values)


def rewrite_ubuntu_stanza(lines, root):
    """Select official HTTPS archives only from an unambiguous signed noble stanza."""
    original = "".join(lines)
    if not any("mirror+" in line for line in lines if not line.startswith("#")):
        updated, count = rewrite_sources(original, True)
        return updated, count, 0
    fields, uri_lines, ambiguous = deb822_fields(lines)
    required = {"types", "uris", "suites", "components", "signed-by"}
    if (
        ambiguous
        or not required <= fields.keys()
        or not fields.keys() <= required | {"architectures", "enabled"}
        or any(
            "#" in value
            or not value.isascii()
            or any(ord(char) < 32 and char != "\t" for char in value)
            for values in fields.values()
            for value in values
        )
    ):
        raise ValueError("Ambiguous Ubuntu archive stanza")
    bounded_values(fields, "types", {"deb", "deb-src"})
    bounded_values(
        fields, "components", {"main", "restricted", "universe", "multiverse"}
    )
    suites = bounded_values(
        fields,
        "suites",
        {"noble", "noble-updates", "noble-backports", "noble-security"},
    )
    if "noble-security" in suites and len(suites) != 1:
        raise ValueError("Archive and security suites require separate stanzas")
    if "architectures" in fields:
        architectures = bounded_values(fields, "architectures", {"amd64", "i386"})
        if "amd64" not in architectures:
            raise ValueError("Ubuntu archive stanza must retain amd64")
    enabled_values = " ".join(fields.get("enabled", ["yes"])).split()
    if len(enabled_values) != 1 or enabled_values[0] not in {"yes", "no"}:
        raise ValueError("Ambiguous Ubuntu archive activation")
    if " ".join(fields["uris"]).split() != [ARCHIVE_LIST]:
        raise ValueError("Only the exact runner archive indirection is supported")
    if " ".join(fields["signed-by"]).split() != [UBUNTU_KEYRING]:
        raise ValueError("Canonical Ubuntu archive keyring required")
    if regular(root / UBUNTU_KEYRING.lstrip("/")).st_size == 0:
        raise ValueError("Empty Ubuntu archive keyring")
    if enabled_values == ["no"]:
        return original, 0, 0
    endpoint = (
        "https://security.ubuntu.com/ubuntu/"
        if suites == {"noble-security"}
        else "https://archive.ubuntu.com/ubuntu/"
    )
    output = list(lines)
    for index in uri_lines:
        output[index] = output[index].replace(ARCHIVE_LIST, endpoint)
    remaining, _, _ = deb822_fields(output)
    if " ".join(remaining["uris"]).split() != [endpoint]:
        raise ValueError("Active archive indirection was not removed")
    return "".join(output), 1, 1


def rewrite_deb822(text, root):
    output = []
    stanza = []
    changes = 0
    indirections = 0
    for line in [*text.splitlines(keepends=True), ""]:
        stanza.append(line)
        if not line.strip():
            updated, count, selected = rewrite_ubuntu_stanza(stanza, root)
            output.append(updated)
            changes += count
            indirections += selected
            stanza = []
    return "".join(output), changes, indirections


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
    indirections = 0
    for path in files:
        before = regular(path)
        text = path.read_bytes().decode("utf-8")
        if path.suffix == ".sources":
            updated, count, selected = rewrite_deb822(text, root)
            indirections += selected
        else:
            updated, count = rewrite_sources(text)
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
        "mirror_list_files_updated": 0,
        "archive_indirections_replaced": indirections,
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
