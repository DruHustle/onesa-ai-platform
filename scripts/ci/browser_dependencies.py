"""Prepare signed Ubuntu browser dependencies on disposable GitHub runners only."""

import hashlib
import json
import os
import platform
import re
import secrets
import stat
import tempfile
from contextlib import ExitStack
from dataclasses import dataclass
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
PROTECTED_KEYRING = "/etc/apt/onesa-ci-keyrings/ubuntu-noble-2023.11.28.1.gpg"
KEYRING_SIZE = 3607
KEYRING_SHA256 = "80a36b0a6de2f69f49d2df75ef473ccde121e9e190b9ea01d20a4f63778d5c31"
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC


@dataclass(frozen=True)
class SourcePlan:
    text: str
    uris: int = 0
    indirections: int = 0
    bindings: int = 0
    key_required: bool = False


@dataclass(frozen=True)
class KeyDestination:
    parent_fd: int
    directory_fd: int | None
    exists: bool


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
            if "mirror+" in content or PROTECTED_KEYRING in content:
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
    if not any(
        "mirror+" in line or PROTECTED_KEYRING in line
        for line in lines
        if not line.startswith("#")
    ):
        updated, count = rewrite_sources(original, True)
        return SourcePlan(updated, count)
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
    endpoint = (
        "https://security.ubuntu.com/ubuntu/"
        if suites == {"noble-security"}
        else "https://archive.ubuntu.com/ubuntu/"
    )
    uris = " ".join(fields["uris"]).split()
    keys = " ".join(fields["signed-by"]).split()
    initial = uris == [ARCHIVE_LIST] and keys == [UBUNTU_KEYRING]
    rebound = uris == [endpoint] and keys == [PROTECTED_KEYRING]
    if not (initial or rebound):
        raise ValueError("Exact Ubuntu archive URI and signing-key binding required")
    if enabled_values == ["no"]:
        return SourcePlan(original)
    output = list(lines)
    if initial:
        for index in uri_lines:
            output[index] = output[index].replace(ARCHIVE_LIST, endpoint)
        field = ""
        for index, line in enumerate(output):
            if line.startswith("#"):
                continue
            header = re.match(r"^([A-Za-z][A-Za-z0-9-]*):", line)
            if header:
                field = header[1].lower()
            if field == "signed-by":
                output[index] = line.replace(UBUNTU_KEYRING, PROTECTED_KEYRING)
    remaining, _, _ = deb822_fields(output)
    if " ".join(remaining["uris"]).split() != [endpoint] or " ".join(
        remaining["signed-by"]
    ).split() != [PROTECTED_KEYRING]:
        raise ValueError("Active Ubuntu archive binding was not replaced")
    return SourcePlan("".join(output), int(initial), int(initial), int(initial), True)


def rewrite_deb822(text, root):
    output = []
    stanza = []
    changes = 0
    indirections = 0
    bindings = 0
    key_required = False
    for line in [*text.splitlines(keepends=True), ""]:
        stanza.append(line)
        if not line.strip():
            plan = rewrite_ubuntu_stanza(stanza, root)
            output.append(plan.text)
            changes += plan.uris
            indirections += plan.indirections
            bindings += plan.bindings
            key_required |= plan.key_required
            stanza = []
    return SourcePlan("".join(output), changes, indirections, bindings, key_required)


def regular(path, *, ubuntu_keyring=False):
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError("APT source aliases are not accepted")
    value = path.stat()
    failures = [
        code
        for code, refused in (
            ("not_regular", not stat.S_ISREG(value.st_mode)),
            ("owner_uid", value.st_uid != os.geteuid()),
            ("group_or_other_writable", bool(value.st_mode & 0o022)),
            ("size_bound", value.st_size > 256 * 1024),
        )
        if refused
    ]
    if failures:
        if ubuntu_keyring:
            kind = {
                stat.S_IFREG: "regular",
                stat.S_IFDIR: "directory",
                stat.S_IFLNK: "symlink",
                stat.S_IFIFO: "fifo",
                stat.S_IFSOCK: "socket",
                stat.S_IFCHR: "character",
                stat.S_IFBLK: "block",
            }.get(stat.S_IFMT(value.st_mode), "unknown")
            raise ValueError(
                "Unexpected APT keyring custody: "
                + json.dumps(
                    {
                        "role": "ubuntu_archive_keyring",
                        "type": kind,
                        "uid": value.st_uid,
                        "gid": value.st_gid,
                        "mode": f"{stat.S_IMODE(value.st_mode):04o}",
                        "size": value.st_size,
                        "size_bound": 256 * 1024,
                        "failed_conditions": failures,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        raise ValueError("Unexpected APT source custody")
    return value


def directory_custody(fd, *, traversable=False):
    value = os.fstat(fd)
    if (
        not stat.S_ISDIR(value.st_mode)
        or value.st_uid != os.geteuid()
        or value.st_gid != os.getegid()
        or value.st_mode & 0o022
        or (traversable and not value.st_mode & 0o001)
    ):
        raise ValueError("Unexpected protected APT directory custody")
    return value


def open_directories(root, components, stack, *, protected):
    """Hold each exact directory without following aliases in either key path."""
    fd = os.open(root, DIRECTORY_FLAGS)
    stack.callback(os.close, fd)
    if protected:
        # Actual / must be traversable; a fixture root is an isolation boundary.
        directory_custody(fd, traversable=root == Path("/"))
    for component in components:
        fd = os.open(component, DIRECTORY_FLAGS, dir_fd=fd)
        stack.callback(os.close, fd)
        if protected:
            directory_custody(fd, traversable=True)
    return fd


def pinned_key_bytes(parent_fd, name, *, modes):
    """Read one held descriptor once; only the reviewed public key is accepted."""
    fd = os.open(name, READ_FLAGS, dir_fd=parent_fd)
    try:
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.geteuid()
            or before.st_gid != os.getegid()
            or before.st_nlink != 1
            or stat.S_IMODE(before.st_mode) not in modes
            or before.st_size != KEYRING_SIZE
        ):
            raise ValueError("Unsupported pinned Ubuntu keyring metadata")
        captured = os.read(fd, KEYRING_SIZE + 1)
        after = os.fstat(fd)
        stable_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_gid",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if (
            any(getattr(before, name) != getattr(after, name) for name in stable_fields)
            or len(captured) != KEYRING_SIZE
            or hashlib.sha256(captured).hexdigest() != KEYRING_SHA256
        ):
            raise ValueError("Reviewed Ubuntu public-key bytes required")
        return captured
    finally:
        os.close(fd)


def plan_key_copy(root, stack):
    original = Path(UBUNTU_KEYRING)
    original_parent = open_directories(
        root, original.parts[1:-1], stack, protected=False
    )
    # 0644 is the verified Noble package; 0777 is the observed hosted image.
    # Neither grants APT authority: captured bytes must match the reviewed pin.
    captured = pinned_key_bytes(original_parent, original.name, modes={0o644, 0o777})
    protected = Path(PROTECTED_KEYRING)
    parent_fd = open_directories(root, protected.parts[1:-2], stack, protected=True)
    try:
        directory_fd = os.open(protected.parent.name, DIRECTORY_FLAGS, dir_fd=parent_fd)
    except FileNotFoundError:
        return captured, KeyDestination(parent_fd, None, False)
    stack.callback(os.close, directory_fd)
    value = directory_custody(directory_fd, traversable=True)
    if stat.S_IMODE(value.st_mode) != 0o755:
        raise ValueError("APT-readable protected key directory required")
    copy_path = root / PROTECTED_KEYRING.lstrip("/")
    try:
        os.stat(protected.name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return captured, KeyDestination(parent_fd, directory_fd, False)
    regular(copy_path, ubuntu_keyring=True)
    if pinned_key_bytes(directory_fd, protected.name, modes={0o644}) != captured:
        raise ValueError("Conflicting protected Ubuntu public key")
    return captured, KeyDestination(parent_fd, directory_fd, True)


def install_key_copy(captured, destination, stack):
    """Publish only captured, pinned bytes after all preparation plans validate."""
    if destination.exists:
        return False
    protected = Path(PROTECTED_KEYRING)
    directory_fd = destination.directory_fd
    if directory_fd is None:
        os.mkdir(protected.parent.name, 0o755, dir_fd=destination.parent_fd)
        directory_fd = os.open(
            protected.parent.name, DIRECTORY_FLAGS, dir_fd=destination.parent_fd
        )
        stack.callback(os.close, directory_fd)
        os.fchmod(directory_fd, 0o755)
        directory_custody(directory_fd, traversable=True)
    pending = ".onesa-keyring-" + secrets.token_hex(12) + ".tmp"
    fd = os.open(
        pending,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o600,
        dir_fd=directory_fd,
    )
    try:
        remaining = memoryview(captured)
        while remaining:
            written = os.write(fd, remaining)
            if written <= 0:
                raise OSError("Incomplete protected key write")
            remaining = remaining[written:]
        os.fchmod(fd, 0o644)
        os.fsync(fd)
        # An existing/concurrently created final name is never replaced. Only
        # complete, synced bytes become visible under the APT binding.
        os.link(
            pending,
            protected.name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
            follow_symlinks=False,
        )
    finally:
        os.close(fd)
        os.unlink(pending, dir_fd=directory_fd)
    os.fsync(directory_fd)
    return True


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
    bindings = 0
    key_required = False
    for path in files:
        before = regular(path)
        text = path.read_bytes().decode("utf-8")
        if path.suffix == ".sources":
            plan = rewrite_deb822(text, root)
            indirections += plan.indirections
            bindings += plan.bindings
            key_required |= plan.key_required
        else:
            updated, count = rewrite_sources(text)
            plan = SourcePlan(updated, count)
        if plan.text != text:
            replacements.append(
                (path, plan.text, stat.S_IMODE(before.st_mode), plan.uris)
            )
    config = apt / "apt.conf.d/99-onesa-ci-network"
    if config.exists():
        regular(config)
        if config.read_text() != NETWORK:
            raise ValueError("Preserve conflicting existing APT configuration")
    elif config.is_symlink() or any(p.is_symlink() for p in config.parents):
        raise ValueError("APT configuration aliases are not accepted")
    key_created = False
    with ExitStack() as stack:
        if key_required:
            # A known-invalid configuration destination must fail before the key
            # or any source is published, even when the config file is absent.
            open_directories(root, ("etc", "apt", "apt.conf.d"), stack, protected=True)
            captured, destination = plan_key_copy(root, stack)
            key_created = install_key_copy(captured, destination, stack)
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
        "signed_by_paths_rebound": bindings,
        "protected_keyring_created": key_created,
        "signer_bytes_changed": False,
        "suites_or_components_changed": False,
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
